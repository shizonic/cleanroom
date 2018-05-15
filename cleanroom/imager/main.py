#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Main CleanRoom functionality.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""

from ..helper import disc
from ..helper.run import run as helper_run
from ..printer import (debug, fail, Printer, trace, verbose,)

from argparse import ArgumentParser
import collections
import json
import os
import re
import shutil
import sys
import tempfile


ExtraPartition = collections.namedtuple('ExtraPartition',
                                        ['size', 'filesystem', 'label', 'contents'])
ImageConfig = collections.namedtuple('ImageConfig',
                                     ['path', 'force', 'repartition', 'efi_size',
                                      'swap_size', 'extra_partitions'])


def _parse_commandline(arguments):
    """Parse the command line options."""
    parser = ArgumentParser(description='Cleanroom OS image writer',
                            prog=arguments[0])
    parser.add_argument('--verbose', action='count', default=0,
                        help='Be verbose')

    parser.add_argument('--repository', dest='repository', action='store',
                        help='Borg repository to extract filesystems from.')

    parser.add_argument('--force', dest='force', action='store_true',
                        help='Overwrite existing image file.')
    parser.add_argument('--repartition', dest='repartition', action='store_true',
                        help='Repartition device or file.')

    parser.add_argument('--efi-size', dest='efi_size', action='store',
                        nargs='?', default='512M',
                        help='Size of EFI partition.')
    parser.add_argument('--swap-size', dest='swap_size', action='store',
                        nargs='?', default='2G',
                        help='Size of swap partition (0 to avoid creation).')
    parser.add_argument('--extra-partition', dest='extra_partitions', action='append',
                        help='Add an extra partition (SIZE:FILESYSTEM:LABEL:TARBALL).')

    # FIXME: Add option to override format

    parser.add_argument('--timestamp', dest='timestamp', action='store',
                        nargs='?', default=None,
                        help='Timestamp of system to install (latest if none given).')

    parser.add_argument(dest='system',  metavar='<system>',
                        help='system to turn into an image.')

    parser.add_argument(dest='image', metavar='<image>',
                        help='name of the image file or device.')

    parse_result = parser.parse_args(arguments[1:])

    return parse_result


def run():
    """Run image installer with command line arguments."""
    main(*sys.argv)


def _parse_extra_partition_value(value):
    parts = value.split(':')
    while len(parts) < 4:
        parts.append(None)

    size = disc.mib_ify(disc.normalize_size(parts[0]))
    assert size is not None

    return ExtraPartition(size=size, filesystem=parts[1], label=parts[2],
                          contents=parts[3])


def main(*args):
    """Run image installer with arguments."""
    args = _parse_commandline(args)

    if not args.system:
        print('No system to process.')
        sys.exit(1)

    if not args.repository:
        print('No repository given.')
        sys.exit(2)

    # Set up printing:
    pr = Printer.Instance()
    pr.set_verbosity(args.verbose)
    pr.show_verbosity_level()

    trace('Setup done.')

    extra_partitions = tuple(map(_parse_extra_partition_value, args.extra_partitions))

    system = args.system
    image_config = ImageConfig(args.image, args.force, args.repartition,
                               disc.mib_ify(disc.normalize_size(args.efi_size)),
                               disc.mib_ify(disc.normalize_size(args.swap_size)),
                               extra_partitions)

    _root_only_part(image_config, system, args.timestamp, args.repository)


def _root_only_part(image_config, system, timestamp, repository):
    if os.geteuid() != 0:
        fail('Not running as root.')

    trace('Running as root.')

    trace('Validating inputs.')
    _validate_image_config_path(image_config.path, image_config.force)

    if timestamp is None:
        (full_system_name, timestamp) = _find_latest_system_timestamp(repository, system)
        if full_system_name is None:
            fail('Could not find system "{}" in repository "{}".'
                 .format(system, repository))
    else:
        full_system_name = _find_system_with_timestamp(repository, system, timestamp)
        if full_system_name is None:
            fail('Could not find system "{}" with timestamp "{}" in repository "{}".'
                 .format(system, timestamp, repository))

    debug('Creating image from "{}".'.format(full_system_name))
    _validate_full_system(repository, full_system_name)

    kernel_size = _get_size(_backup_name(repository, full_system_name),
                            _kernel_name(timestamp))
    root_size = _get_size(_backup_name(repository, full_system_name),
                          _root_name(timestamp))
    verity_size = _get_size(_backup_name(repository, full_system_name),
                            _verity_name(timestamp))

    extra_text = 'extra: '
    extra_total = 0
    for ep in image_config.extra_partitions:
        extra_total += ep.size
        extra_text += '{}b, '.format(ep.size)
    extra_text += 'Total: {}b'
    trace('External sizes: EFI: {}b, Swap: {}b, extra: {}'
          .format(image_config.efi_size, image_config.swap_size, extra_text))

    min_device_size = _calculate_minimum_size(kernel_size, root_size, verity_size,
                                              image_config.efi_size, image_config.swap_size,
                                              image_config.extra_partitions)

    verbose('Sizes: kernel: {}b, root: {}b, verity: {}b => min device size: {}b'
            .format(kernel_size, root_size, verity_size, min_device_size))

    with _find_or_create_device_node(image_config.path, min_device_size) as device:

        partition_devices = _repartition(device, image_config.repartition, timestamp,
                                         efi_size=image_config.efi_size, root_size=root_size,
                                         verity_size=verity_size, swap_size=image_config.swap_size,
                                         extra_partitions=image_config.extra_partitions)
        for name, dev in partition_devices.items():
            trace('Created partition "{}": {}.'.format(name, dev))

        if 'swap' in partition_devices:
            helper_run('/usr/bin/mkswap', '-L', 'main', partition_devices['swap'])
        assert 'root' in partition_devices
        _write_to_partition(partition_devices['root'],
                            _backup_name(repository, full_system_name),
                            _root_name(timestamp))
        assert 'verity' in partition_devices
        _write_to_partition(partition_devices['verity'],
                            _backup_name(repository, full_system_name),
                            _verity_name(timestamp))
        assert 'efi' in partition_devices
        _prepare_efi_partition(partition_devices['efi'], partition_devices['root'],
                               _backup_name(repository, full_system_name),
                               timestamp)
        for i in range(len(image_config.extra_partitions)):
            ep = image_config.extra_partitions[i]
            _prepare_extra_partition(partition_devices['extra{}'.format(i+1)],
                                     filesystem=ep.filesystem, label=ep.label,
                                     contents=ep.contents)

    sys.exit(0)


def _backup_name(repository, full_system_name):
    return '{}::{}'.format(repository, full_system_name)


def _kernel_name(timestamp):
    return 'linux-{}-partlabel.efi'.format(timestamp)


def _root_name(timestamp):
    return 'root_{}'.format(timestamp)


def _verity_name(timestamp):
    return _root_name(timestamp) + '_verity'


def _run_borg(*args, **kwargs):
    env = os.environ
    env['LC_ALL'] = 'C'
    print(*args)
    result = helper_run('/usr/bin/borg', *args,
                        env=env, trace_output=trace, **kwargs)
    if result.returncode != 0:
        fail('Failed to retrieve data from borg.')

    return result


def _parse_borg_list(repository):
    trace('Running borg list on repository "{}".'.format(repository))
    result = _run_borg('list', repository)

    pattern = re.compile('(([a-zA-Z][a-zA-Z0-9_-]*)-([0-9]+-[0-9]+))\s+(.*) \\[([a-fA-F0-9]+)\\]')

    for line in result.stdout.splitlines():
        if not line:
            continue

        match = pattern.search(line)
        if match is None:
            fail('Failed to parse borg list output.')

        yield match.groups()


def _find_latest_system_timestamp(repository, system):
    latest_timestamp = '00000000-000000'
    full_system_name = None
    for (current_full_name, current_system, current_timestamp, _, _) in _parse_borg_list(repository):
        if system != current_system:
            continue

        if current_timestamp > latest_timestamp:
            latest_timestamp = current_timestamp
            full_system_name = current_full_name

    return full_system_name, latest_timestamp


def _find_system_with_timestamp(repository, system, timestamp):
    for (current_full_name, current_system, current_timestamp, _, _) in _parse_borg_list(repository):
        if system == current_system and timestamp == current_timestamp:
            return current_full_name

    return None


def _get_size(backup, file_name):
    result = _run_borg('list', '--json-lines', backup, file_name)
    for line in result.stdout.splitlines():
        json_data = json.loads(line)
        assert json_data.get('path') == file_name
        assert json_data.get('type') == '-'
        assert json_data.get('healthy', False)
        return json_data.get('size')


def _calculate_minimum_size(kernel_size, root_size, verity_size,
                            efi_size, swap_size, extra_partitions):
    mib = 1024 * 1024
    bootloader_size = 1 * mib  # size of systemd-boot (+ some spare)

    if (kernel_size + 2 * bootloader_size) * 1.1 > efi_size:
        fail('EFI partition is too small to hold the kernel.')

    total_extra_size = 0
    for ep in extra_partitions:
        total_extra_size += ep.size

    return (2 * mib +      # Blank space in front
            efi_size +     # EFI partition
            swap_size +    # Swap partition
            root_size +    # Squashfs root partition
            verity_size +  # Verity root partition
            total_extra_size +
            2 * mib)       # Blank space in back


def _validate_full_system(repository, full_system_name):
    debug('Validating system: {}.'.format(full_system_name))

    borg_path = _backup_name(repository, full_system_name)
    borg_extract_result = _run_borg('extract', '--stdout', borg_path, 'export_type')

    if borg_extract_result.stdout != 'export_squashfs':
        fail('{} is not a squashfs filesystem export.'.format(full_system_name))


def _validate_image_config_path(path, force):
    if disc.is_block_device(path):
        return _validate_device(path, force)
    return _validate_image_file(path, force)


def _validate_device(path, force):
    if not force:
        fail('You need to --force to work with block device "{}".'
             .format(path))


def _validate_image_file(path, force):
    if os.path.exists(path):
        if not force:
            fail('You need to --force override of existing image file "{}".'
                 .format(path))


def  _find_or_create_device_node(path, min_device_size):
    if disc.is_block_device(path):
        _validate_size_of_block_device(path, min_device_size)
        return disc.Device(path)
    return _create_nbd_device(path, min_device_size)


def _validate_size_of_block_device(path, min_device_size):
    result = helper_run('/usr/bin/blockdev', '--getsize64', path, trace_output=trace)
    if int(result.stdout) < min_device_size:
        fail('"{}" is too small for image data. Minimum size is {}b.'
             .format(path, min_device_size))


def _create_nbd_device(path, min_device_size):
    return disc.NbdDevice.NewImageFile(path, min_device_size)


def _repartition(device, repartition, timestamp, *,
                 efi_size, root_size, verity_size, swap_size=0, extra_partitions=[]):
    partitioner = disc.Partitioner(device)

    if partitioner.is_partitioned() and not repartition:
        fail('"{}" is already partitioned, use --repartition to force repartitioning.'
             .format(device.device()))

    partitions = [partitioner.efi_partition(start='2m', size=efi_size),
                  partitioner.data_partition(size=root_size,
                                             name='clrm-{}'.format(timestamp)),
                  partitioner.data_partition(size=verity_size,
                                             name='vrty-{}'.format(timestamp))]
    devices = {'efi': device.device(1), 'root': device.device(2),
               'verity': device.device(3)}
    if swap_size > 0:
        partitions.append(partitioner.swap_partition(size=swap_size))
        devices['swap'] = device.device(4)

    extra_counter = 0
    print('Adding extra partitions: {}.'.format(extra_partitions))
    for ep in extra_partitions:
        extra_counter += 1

        name = 'extra{}'.format(extra_counter)

        label = name if ep.label is None else ep.label
        partitions.append(partitioner.data_partition(size=ep.size, name=label))
        devices[name] = device.device(4 + extra_counter)

    partitioner.repartition(partitions)

    return devices


def _copy_efi_file(source, destination):
    shutil.copyfile(source, destination)
    os.chmod(destination, 0o755)


def _prepare_efi_partition(device, root_dev, backup, timestamp):
    helper_run('/usr/bin/mkfs.vfat', device, trace_output=trace)

    cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as mnt_point:
        boot_mnt = os.path.join(mnt_point, 'boot')
        root_mnt = os.path.join(mnt_point, 'root')
        try:
            os.makedirs(boot_mnt)
            helper_run('/usr/bin/mount', '-t', 'vfat', device, boot_mnt, trace_output=trace)
            os.makedirs(root_mnt)
            helper_run('/usr/bin/mount', '-t', 'squashfs', root_dev, root_mnt, trace_output=trace)

            loader = os.path.join(root_mnt, 'usr/lib/systemd/boot/efi/systemd-bootx64.efi')
            os.makedirs(os.path.join(boot_mnt, 'EFI/Boot'))
            _copy_efi_file(loader, os.path.join(boot_mnt, 'EFI/Boot/BOOTX64.EFI'))
            os.makedirs(os.path.join(boot_mnt, 'EFI/systemd'))
            _copy_efi_file(loader, os.path.join(boot_mnt, 'EFI/systemd/systemd-bootx64.efi'))
            os.makedirs(os.path.join(boot_mnt, 'loader/entries'))
            with open(os.path.join(boot_mnt, 'loader/loader.conf'), 'w') as lc:
                lc.write('#timeout 3\n')
                lc.write('default linux-*\n')

            linux_dir = os.path.join(boot_mnt, 'EFI/Linux')
            os.makedirs(linux_dir)
            _run_borg('extract', backup, _kernel_name(timestamp),
                      work_directory=linux_dir)
            input_kernel = os.path.join(linux_dir, _kernel_name(timestamp))
            kernel = os.path.join(linux_dir, 'linux-{}.efi'.format(timestamp))
            _copy_efi_file(input_kernel, kernel)
            os.remove(input_kernel)

        finally:
            os.chdir(cwd)
            helper_run('/usr/bin/umount', boot_mnt, trace_output=trace, returncode=None)
            helper_run('/usr/bin/umount', root_mnt, trace_output=trace, returncode=None)


def _write_to_partition(device, backup, file_name):
    _run_borg('extract', '--stdout', backup, file_name, stdout=device)


def _format_partition(device, filesystem, *label_args):
    helper_run('/usr/bin/mkfs.{}'.format(filesystem), *label_args, device)


def _prepare_extra_partition(device, *, filesystem=None, label=None, contents=None):
    if filesystem is None:
        assert contents is None
        return

    label_args = ()
    if label is not None:
        if filesystem == 'fat' or filesystem == 'vfat':
            label_args = ('-n', label)
        if filesystem.startswith('ext') or filesystem == 'btrfs' or filesystem == 'xfs':
            label_args = ('-L', label)

    _format_partition(device, filesystem, *label_args)

    if contents is not None:
        return

