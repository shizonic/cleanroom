# -*- coding: utf-8 -*-
"""The class that holds context data for the executor.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from __future__ import annotations

from .printer import debug, h2, trace
from .execobject import ExecObject

import os
import os.path
import pickle
import string
import typing


def _unpickle(pickle_jar: str) -> SystemContext:
    """Create a new system_context by unpickling a file."""
    with open(pickle_jar, 'rb') as pj:
        base_context = pickle.load(pj)
    trace('Base context was unpickled.')

    return base_context


class SystemContext:
    """Context data for the execution os commands."""

    def __init__(self, *,
                 system_name: str,
                 base_system_name: str,
                 scratch_directory: str,
                 systems_definition_directory: str,
                 repository_base_directory: str,
                 storage_directory: str,
                 timestamp: str) -> None:
        """Constructor."""
        assert scratch_directory
        assert systems_definition_directory
        assert repository_base_directory

        self._system_name = system_name
        self._timestamp = timestamp
        self._repository_base_directory = repository_base_directory
        self._scratch_directory = scratch_directory
        self._systems_definition_directory = systems_definition_directory
        self._system_storage_directory = os.path.join(storage_directory,
                                                      system_name)
        self._base_storage_directory = ''

        self._base_context: typing.Optional[SystemContext] = None
        self._hooks: typing.Dict[str, typing.List[ExecObject]] = {}
        self._hooks_that_already_ran: typing.List[str] = []
        self._substitutions: typing.MutableMapping[str, str] = {}

        if base_system_name:
            self._base_storage_directory \
                = os.path.join(storage_directory, base_system_name)
            self._install_base_context()

        self._setup_core_substitutions()

    def __enter__(self) -> typing.Any:
        h2('Creating system {}'.format(self._system_name))
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        return False

    @property
    def timestamp(self) -> str:
        return self._timestamp

    @property
    def repository_base_directory(self) -> str:
        return self._repository_base_directory

    @property
    def system_name(self) -> str:
        return self._system_name

    @property
    def systems_definition_directory(self) -> str:
        return self._systems_definition_directory

    @property
    def system_helper_directory(self) -> str:
        return os.path.join(self._systems_definition_directory,
                            self.system_name)

    @property
    def system_tests_directory(self) -> str:
        return os.path.join(self._systems_definition_directory, 'tests')

    @property
    def scratch_directory(self) -> str:
        return self._scratch_directory

    @property
    def fs_directory(self) -> str:
        return os.path.join(self._scratch_directory, 'fs')

    @property
    def boot_directory(self) -> str:
        return os.path.join(self._scratch_directory, 'boot')

    @property
    def meta_directory(self) -> str:
        return os.path.join(self._scratch_directory, 'meta')

    @property
    def cache_directory(self) -> str:
        return os.path.join(self._scratch_directory, 'cache')

    @property
    def system_storage_directory(self) -> str:
        return self._system_storage_directory

    @property
    def base_storage_directory(self) -> str:
        return self._base_storage_directory

    def __collect_bases(self) -> typing.List[str]:
        bases: typing.List[str] = []
        base_context = self.base_context
        while base_context:
            bases.append(base_context.system_name)
            base_context = base_context.base_context

        return bases

    def _setup_core_substitutions(self) -> None:
        """Core substitutions that may not get overridden by base system."""
        bases: typing.List[str] = self.__collect_bases()

        self.set_substitution('BASE_SYSTEM_NAME',
                              bases[0] if bases else '')
        self.set_substitution('BASE_SYSTEM_LIST',
                              ';'.join(bases) if bases else '')

        self.set_substitution('SCRATCH_DIR', self.scratch_directory)
        self.set_substitution('ROOT_DIR', self.fs_directory)
        self.set_substitution('META_DIR', self.meta_directory)
        self.set_substitution('CACHE_DIR', self.cache_directory)
        self.set_substitution('SYSTEMS_DEFINITION_DIR',
                              self.systems_definition_directory)
        self.set_substitution('SYSTEM_HELPER_DIR', self.system_helper_directory)
        self.set_substitution('SYSTEM_NAME', self.system_name)
        ts = 'unknown' if self.timestamp is None else self.timestamp
        self.set_substitution('TIMESTAMP', ts)

        self.set_substitution('DISTRO_NAME', 'cleanroom')
        self.set_substitution('DISTRO_PRETTY_NAME', 'cleanroom')
        self.set_substitution('DISTRO_ID', 'clrm')
        self.set_substitution('DISTRO_VERSION', ts)
        self.set_substitution('DISTRO_VERSION_ID', ts)

        self.set_substitution('DEFAULT_VG', '')

        self.set_substitution('IMAGE_FS', 'btrfs')
        self.set_substitution('IMAGE_OPTIONS', 'rw,subvol=/.images')
        self.set_substitution('IMAGE_DEVICE', '/dev/disk/by-label/fs_btrfs')

    # Handle Hooks:
    def add_hook(self, hook: str, exec_obj: ExecObject) -> None:
        """Add a hook."""
        self._hooks.setdefault(hook, []).append(exec_obj)
        trace('Added hook "{}": It now has {} entries.'
              .format(hook, len(self._hooks[hook])))

    def hooks(self, hook_name: str) -> typing.Sequence[ExecObject]:
        """Run all the registered hooks."""
        self._hooks_that_already_ran.append(hook_name)
        return self._hooks.get(hook_name, [])

    def hooks_were_run(self, hook_name: str) -> bool:
        return hook_name in self._hooks_that_already_ran

    # Handle substitutions:
    @property
    def substitutions(self) -> typing.Mapping[str, str]:
        return self._substitutions

    def set_substitution(self, key: str, value: str) -> None:
        """Add a substitution to the substitution table."""
        self._substitutions[key] = value
        debug('Added substitution: "{}"="{}".'.format(key, value))

    def substitution(self, key: str,
                     default_value: typing.Optional[str] = None) -> typing.Any:
        """Get substitution value."""
        return self.substitutions.get(key, default_value)

    def has_substitution(self, key: str) -> bool:
        """Check wether a substitution is defined."""
        return key in self.substitutions

    def substitute(self, text: str) -> str:
        """Substitute variables in text."""
        return string.Template(text).substitute(**self.substitutions)

    def file_name(self, path: str) -> str:
        result = os.path.join(self.fs_directory,
                              os.path.relpath(path, '/') \
                                  if os.path.isabs(path) else path)
        trace('Mapped system path "{}" to "{}".'.format(path, result))
        return result

    @property
    def base_context(self) -> typing.Optional[SystemContext]:
        return self._base_context

    # Store/Restore a system:
    def _install_base_context(self) -> None:
        """Set up base context."""
        base_context = _unpickle(os.path.join(self.base_storage_directory,
                                              'meta', 'pickle_jar.bin'))

        self._base_context = base_context
        self._timestamp = base_context._timestamp
        self._hooks = base_context._hooks
        self._substitutions = base_context._substitutions

    def pickle(self) -> None:
        """Pickle this system_context."""
        pickle_jar = os.path.join(self.meta_directory, 'pickle_jar.bin')

        # Remember stuff that should not get saved:
        hooks_that_ran = self._hooks_that_already_ran
        self._hooks_that_already_ran = []

        trace('Pickling system_context into {}.'.format(pickle_jar))
        with open(pickle_jar, 'wb') as pj:
            pickle.dump(self, pj)

        # Restore state that should not get saved:
        self._hooks_that_already_ran = hooks_that_ran
