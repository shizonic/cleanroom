# -*- coding: utf-8 -*-
"""useradd command.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from cleanroom.generator.command import Command
from cleanroom.generator.helper.generic.user import useradd

from cleanroom.exceptions import ParseError


class UseraddCommand(Command):
    """The useradd command."""

    def __init__(self):
        """Constructor."""
        super().__init__('useradd',
                         syntax='<NAME> [comment=<COMMENT>] [home=<HOMEDIR>] '
                         '[gid=<GID>] [uid=<UID>] [groups=<GROUP1>,<GROUP2>] '
                         '[lock=False] [password=<CRYPTED_PASSWORD>] '
                         '[shell=<PATH>] [expire=<EXPIRE_DATE>]',
                         help='Modify an existing user.', file=__file__)

    def validate_arguments(self, location, *args, **kwargs):
        """Validate the arguments."""
        self._validate_args_exact(location, 1, '"{}" needs a username.', *args)
        if len(kwargs) == 0:
            raise ParseError('useradd needs keyword arguments', location=location)

        lock = kwargs.get('lock', None)
        if lock not in (True, None, False):
            raise ParseError('"lock" must be either True, False or None.',
                             location=location)

    def __call__(self, location, system_context, *args, **kwargs):
        """Execute command."""
        useradd(system_context, args[0], **kwargs)