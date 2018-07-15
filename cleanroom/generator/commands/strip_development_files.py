# -*- coding: utf-8 -*-
"""strip_development_files command.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""

from cleanroom.generator.command import Command


class StripDevelopmentFilesCommand(Command):
    """The strip_development_files Command."""

    def __init__(self):
        """Constructor."""
        super().__init__('strip_development_files',
                         help='Strip away development files.', file=__file__)

    def validate_arguments(self, location, *args, **kwargs):
        """Validate arguments."""
        self._validate_no_arguments(location, *args, **kwargs)

    def __call__(self, location, system_context, *args, **kwargs):
        """Execute command."""
        location.set_description('Strip development files')
        system_context.add_hook(location, 'export',
                                'remove',  '/usr/include/*', '/usr/src/*',
                                '/usr/share/pkgconfig/*',
                                '/usr/share/aclocal/*', '/usr/lib/cmake/*',
                                recursive=True, force=True)