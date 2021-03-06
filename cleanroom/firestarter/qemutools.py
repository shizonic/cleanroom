#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Qemu related tool functions.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


import cleanroom.firestarter.tools as tools
import os
from shutil import copyfile
import typing


def _append_network(hostname, *, hostfwd=[], mac='', net='', host=''):
    hostfwd_args = ['hostfwd={}'.format(p) for p in hostfwd]

    hostfwd_str = ',' + ','.join(hostfwd_args) if hostfwd_args else ''
    mac_str = ',mac={}'.format(mac) if mac else ''
    host_str = ',host={}'.format(host) if host else ''
    net_str = ',net={}'.format(net) if net else ''

    # -netdev bridge,id=bridge1,br=qemubr0
    # -device virtio-net,netdev=bridge1,mac=52:54:00:12:01:c1

    return ['-netdev', 'user,id=nic0,hostname={}{}{}{}'
            .format(hostname, hostfwd_str, net_str, host_str),
            '-device', 'virtio-net,netdev=nic0{}'.format(mac_str)]


def _append_hdd(bootindex, disk):
    disk_parts = disk.split(':')
    if len(disk_parts) < 2:
        disk_parts.append('qcow2')
    assert len(disk_parts) == 2

    c = _append_hdd.counter;
    _append_hdd.counter += 1

    return ['-drive', 'file={},format={},if=none,id=disk{}'
                      .format(disk_parts[0], disk_parts[1], c),
            '-device', 'virtio-blk-pci,drive=disk{},bootindex={}'
                       .format(c, bootindex)]


_append_hdd.counter = 0


def _append_fs(fs, *, read_only=False):
    fs_parts = fs.split(':')
    assert len(fs_parts) == 2

    ro = ',read-only' if read_only else ''

    return ['-virtfs',
            'local,id={0},path={1},mount_tag={0},security_mode=passthrough{2}'
            .format(fs_parts[0], fs_parts[1], ro)]


def _append_efi(efivars):
    if not os.path.exists(efivars):
        copyfile('/usr/share/ovmf/x64/OVMF_VARS.fd', efivars)
    return ['-drive', 'if=pflash,format=raw,readonly,'
            'file=/usr/share/ovmf/x64/OVMF_CODE.fd', '-drive',
            'if=pflash,format=raw,file={}'.format(efivars)]


def setup_parser_for_qemu(parser: typing.Any) -> None:
    parser.add_argument('--bios', dest='use_bios', action='store_true',
                        help='Use BIOS over EFI')

    parser.add_argument('--no-graphic', dest='no_graphic',
                        action='store_true', help='Use no-graphics mode')

    parser.add_argument('--cores', action='store', nargs='?', default=2,
                        help='Number of cores to use.')
    parser.add_argument('--memory', action='store', nargs='?',
                        default='4G', help='Memory')
    parser.add_argument('--mac', dest='mac', action='store',
                        nargs='?', default='',
                        help='MAC address of main network card')
    parser.add_argument('--net', dest='net', action='store',
                        nargs='?', default='',
                        help='Network address of main network card')
    parser.add_argument('--host', dest='host', action='store',
                        nargs='?', default='',
                        help='Host address of main network card')

    parser.add_argument('--hostname', dest='hostname', action='store',
                        nargs='?', default='unknown',
                        help='Hostname to use for NIC')
    parser.add_argument('--hostfwd', dest='hostfwd',
                        default=[], action='append',
                        help='Port spec to forward from host to guest')

    parser.add_argument('--disk', dest='disks',
                        default=[], action='append',
                        help='Extra disks to add (file[:format])')

    parser.add_argument('--ro-fs', dest='ro_fses',
                        default=[], action='append',
                        help='Host folders to make available to guest -- '
                             'read-only (id:path)')
    parser.add_argument('--fs', dest='fses',
                        default=[], action='append',
                        help='Host folder to make available to guest (id:path)')

    parser.add_argument('--verbatim', dest='verbatim', action='append',
                        help='Argument to copy verbatim to qemu.')


def run_qemu(parse_result: typing.Any, *,
             drives: typing.List[str] = [],
             work_directory: str) -> typing.List[str]:
    qemu_args = ['/usr/bin/qemu-system-x86_64',
                 '--enable-kvm',
                 '-cpu', 'host',
                 '-smp', 'cores={}'.format(parse_result.cores),
                 '-machine', 'pc-q35-2.12',
                 '-accel', 'kvm',
                 '-m', 'size={}'.format(parse_result.memory),  # memory
                 '-object', 'rng-random,filename=/dev/urandom,id=rng0',
                 '-device',
                 'virtio-rng-pci,rng=rng0,max-bytes=512,period=1000',
                 # Random number generator
                 ]

    qemu_args += _append_network(parse_result.hostname,
                                 hostfwd=parse_result.hostfwd,
                                 mac=parse_result.mac,
                                 net=parse_result.net,
                                 host=parse_result.host)

    boot_index = 0
    for disk in drives:
        qemu_args += _append_hdd(boot_index, disk)
        boot_index += 1
    for disk in parse_result.disks:
        qemu_args += _append_hdd(boot_index, disk)
        boot_index += 1

    for fs in parse_result.ro_fses:
        qemu_args += _append_fs(fs, read_only=True)
    for fs in parse_result.fses:
        qemu_args += _append_fs(fs, read_only=False)

    if parse_result.no_graphic:
        qemu_args.append('-nographic')

    if not parse_result.use_bios:
        qemu_args += _append_efi(os.path.join(work_directory, 'vars.fd'))

    if parse_result.verbatim:
        qemu_args += parse_result.verbatim

    result = tools.run(*qemu_args, work_directory=work_directory, check=False)

    if result.returncode != 0:
        print("Qemu run Failed with return code {}.".format(result.returncode))
        print("Qemu stdout: {}".format(result.stdout))
        print("Qemu stderr: {}".format(result.stderr))
