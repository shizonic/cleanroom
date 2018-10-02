# -*- coding: utf-8 -*-
"""Base class for commands usable in the system definition files.

The Command class will be used to derive all system definition file commands
from.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from __future__ import annotations

from .execobject import ExecObject
from ..exceptions import ParseError
from ..location import Location
from ..printer import trace

import os
import os.path
import typing


class Command:
    """A command that can be used in to set up machines."""

    def __init__(self, name: str, *, syntax: str='', help: str, file: str) -> None:
        """Constructor."""
        assert(name)
        self._name = name
        self._syntax_string = syntax
        self._help_string = help
        self._base_directory = os.path.dirname(os.path.realpath(file))

    def name(self) -> str:
        """Return the command name."""
        return self._name

    def helper_directory(self) -> typing.Optional[str]:
        """Return the helper directory."""
        full_path = os.path.join(self._base_directory, 'helper', self.name())
        if os.path.isdir(full_path):
            return full_path
        return None

    def validate_arguments(self, location: Location,
                           *args: typing.Any, **kwargs: typing.Any) -> typing.Optional[str]:
        """Validate all arguments.

        Validate all arguments and optionally return a dependency for
        the system.
        """
        print('Command "{}"" called validate_arguments illegally!'
              .format(self.name()))
        assert(False)
        return None

    def _validate_no_arguments(self, location: Location,
                               *args: typing.Any, **kwargs: typing.Any) -> None:
        self._validate_no_args(location, *args)
        self._validate_kwargs(location, (), **kwargs)

    def _validate_arguments_exact(self, location: Location, arg_count: int, message: str,
                                  *args: typing.Any, **kwargs: typing.Any) -> None:
        self._validate_args_exact(location, arg_count, message, *args)
        self._validate_kwargs(location, (), **kwargs)

    def _validate_arguments_at_least(self, location: Location, arg_count: int, message: str,
                                     *args: typing.Any, **kwargs: typing.Any) -> None:
        self._validate_args_at_least(location, arg_count, message, *args)
        self._validate_kwargs(location, (), **kwargs)

    def _validate_no_args(self, location: Location, *args: typing.Any) -> None:
        if args is list:
            trace('Validating arguments: "{}".'.format('", "'.join(str(args))))
        else:
            trace('Validating argument: "{}".'.format(args))
        self._validate_args_exact(location, 0,
                                  '"{}" does not take arguments.', *args)

    def _validate_args_exact(self, location: Location, arg_count: int,
                             message: str, *args: typing.Any) -> None:
        if args is list:
            trace('Validating arguments: "{}".'.format('", "'.join(str(args))))
        else:
            trace('Validating argument: "{}".'.format(args))
        if len(args) != arg_count:
            raise ParseError(message.format(self.name()), location=location)

    def _validate_args_at_least(self, location: Location, arg_count: int,
                                message: str, *args: typing.Any) -> None:
        if args is list:
            trace('Validating arguments: "{}".'.format('", "'.join(str(args))))
        else:
            trace('Validating argument: "{}".'.format(args))
        if len(args) < arg_count:
            raise ParseError(message.format(self.name()), location=location)

    def _validate_kwargs(self, location: Location, known_kwargs: typing.Tuple[str, ...],
                         **kwargs: typing.Any) -> None:
        trace('Validating keyword arguments: "{}"'.format('", "'.join([ '{}={}'.format(k, str(kwargs[k])) for k in kwargs.keys()])))
        if not known_kwargs:
            if kwargs:
                raise ParseError('"{}" does not accept keyword arguments.'
                                 .format(self.name()), location=location)
        else:
            for key, value in kwargs.items():
                if key not in known_kwargs:
                    raise ParseError('"{}" does not accept the keyword '
                                        'arguments "{}".'
                                     .format(self.name(), key),
                                     location=location)

    def _require_kwargs(self, location: Location, required_kwargs: typing.Tuple[str, ...],
                        **kwargs: typing.Any) -> None:
        for key in required_kwargs:
            if key not in kwargs:
                raise ParseError('"{}" requires the keyword '
                                    'arguments "{}" to be passed.'
                                 .format(self.name(), key),
                                 location=location)

    def __call__(self, location: Location, system_context: SystemContext,
                 *args: typing.Any, **kwargs: typing.Any) -> bool:
        """Execute command."""
        assert(False)
        return True

    def config_directory(self, system_context: SystemContext) -> str:
        return os.path.join(system_context.ctx.systems_directory(), 'config',
                            self.name())

    def syntax(self) -> str:
        """Return syntax description."""
        if self._syntax_string:
            return '{} {}'.format(self._name, self._syntax_string)
        return self._name

    def help(self) -> str:
        """Print help string."""
        return self._help_string

    def exec_object(self, location: Location,
                    *args: typing.Any, **kwargs: typing.Any) -> ExecObject:
        dependency = self.validate_arguments(location, *args, **kwargs)
        return ExecObject(location, dependency, self.name(), *args, **kwargs)
