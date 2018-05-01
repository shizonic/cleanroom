# -*- coding: utf-8 -*-
"""Pretty-print output of cleanroom.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


import sys


def h1(*args, **kwargs):
    """Print main headline."""
    Printer.Instance().h1(*args, **kwargs)


def h2(*args, **kwargs):
    """Print sub headline."""
    Printer.Instance().h2(*args, **kwargs)


def h3(*args, **kwargs):
    """Print sub-sub headline."""
    Printer.Instance().h3(*args, **kwargs)


def error(*args, **kwargs):
    """Print error message."""
    Printer.Instance().error(*args, **kwargs)


def warn(*args, **kwargs):
    """Print warning message."""
    Printer.Instance().warn(*args, **kwargs)


def success(*args, **kwargs):
    """Print success message."""
    Printer.Instance().success(*args, **kwargs)


def fail(*args, **kwargs):
    """Print fail message."""
    Printer.Instance().fail(*args, **kwargs)


def msg(*args, **kwargs):
    """Print arguments."""
    Printer.Instance().msg(*args, **kwargs)


def verbose(*args, **kwargs):
    """Print if verbose is set."""
    Printer.Instance().verbose(*args, **kwargs)


def info(*args, **kwargs):
    """Print even more verbose."""
    Printer.Instance().info(*args, **kwargs)


def debug(*args, **kwargs):
    """Print if debug is set."""
    Printer.Instance().debug(*args, **kwargs)


def trace(*args, **kwargs):
    """Print trace messsages."""
    Printer.Instance().trace(*args, **kwargs)


def _ansify(seq):
    """Use ANSI color codes if possible.

    Use ANSI color codes if possible and strip them out if not.
    """
    if sys.stdout.isatty():
        return seq
    return ''


class Printer:
    """Pretty-print output.

    A Printer will be set up by the cleanroom executable and
    passed on to the cleanroom module.

    The module will then use this Printer object for all its
    output needs.
    """

    _instance = None

    @staticmethod
    def Instance():
        """Get the main printer instance."""
        if Printer._instance is None:
            Printer._instance = Printer(verbosity=0)
        return Printer._instance

    def __init__(self, verbosity=0):
        """Constructor."""
        self.set_verbosity(verbosity)

        self._ansi_reset = _ansify('\033[0m')
        self._h_prefix = _ansify('\033[1;31m')
        self._h1_suffix = _ansify('\033[0m\033[1;37m')
        self._error_prefix = _ansify('\033[1;31m')
        self._warn_prefix = _ansify('\033[1;33m')
        self._ok_prefix = _ansify('\033[1;7;32m')
        self._ok_suffix = _ansify('\033[0;32m')

        self._ig_fail_prefix = _ansify('\033[1;7;33m')
        self._ig_fail_suffix = _ansify('\033[0;33m')
        self._fail_prefix = _ansify('\033[1;7;31m')
        self._fail_suffix = _ansify('\033[0;31m')
        self._extra_prefix = _ansify('\033[1;36m')
        self._extra_suffix = _ansify('\033[0;m\033[2;m')

        Printer._instance = self

    def set_verbosity(self, verbosity):
        """Set the verbosity."""
        self._verbose = verbosity
        self._prefix = '      ' if verbosity > 0 else ''

    def _print(self, *args):
        print(*args)

    def _print_at_verbosity_level(self, verbosity):
        return verbosity <= self._verbose

    def h1(self, *args, verbosity=0):
        """Print big headline."""
        if self._print_at_verbosity_level(verbosity):
            intro = '\n\n{}============================================{}'\
                    .format(self._h1_suffix, self._ansi_reset)
            prefix = '{}== '.format(self._h1_suffix)
            outro = '{}============================================'\
                    .format(self._h1_suffix, self._ansi_reset)
            self._print(intro)
            self._print(prefix, *args, self._ansi_reset)
            self._print(outro)
            self._print()

    def h2(self, *args, verbosity=0):
        """Print a headline."""
        if self._print_at_verbosity_level(verbosity):
            intro = '\n{}******{}'.format(self._h_prefix, self._h1_suffix)
            self._print(intro, *args, self._ansi_reset)

    def h3(self, *args, verbosity=0):
        """Print a subheading."""
        if self._print_at_verbosity_level(verbosity):
            intro = '\n{}******{}'.format(self._h_prefix, self._ansi_reset)
            self._print(intro, *args)

    def error(self, *args, verbosity=0):
        """Print error message."""
        if self._print_at_verbosity_level(verbosity):
            intro = '{}ERROR:'.format(self._error_prefix)
            self._print(intro, *args, self._ansi_reset)

    def warn(self, *args, verbosity=0):
        """Print warning message."""
        if self._print_at_verbosity_level(verbosity):
            intro = '{}warn: '.format(self._warn_prefix)
            self._print(intro, *args, self._ansi_reset)

    def success(self, *args, verbosity=0):
        """Print success message."""
        if self._print_at_verbosity_level(verbosity):
            intro = '{}  OK  {}'.format(self._ok_prefix, self._ok_suffix)
            self._print(intro, *args, self._ansi_reset)

    def fail(self, *args, verbosity=0, force_exit=True, ignore=False):
        """Print fail message."""
        if self._print_at_verbosity_level(verbosity):
            if ignore:
                intro = '{} fail {}'.format(self._ig_fail_prefix,
                                            self._ig_fail_suffix)
                self._print(intro, *args, '(ignored)', self._ansi_reset)
            else:
                intro = '{} FAIL {}'.format(self._fail_prefix,
                                            self._fail_suffix)
                self._print(intro, *args, self._ansi_reset)
                if force_exit:
                    sys.exit(1)

    def msg(self, *args):
        """Print arguments."""
        self._print(self._prefix, *args)

    def verbose(self, *args):
        """Print if verbose is set."""
        if self._print_at_verbosity_level(1):
            self._print(self._prefix, *args)

    def info(self, *args):
        """Print even more verbose."""
        if self._print_at_verbosity_level(2):
            intro = '{}......{}'.format(self._extra_prefix, self._extra_suffix)
            self._print(intro, *args, self._ansi_reset)

    def debug(self, *args):
        """Print if debug is set."""
        if self._print_at_verbosity_level(3):
            intro = '{}------{}'.format(self._extra_prefix, self._extra_suffix)
            self._print(intro, *args, self._ansi_reset)

    def trace(self, *args):
        """Print trace messsages."""
        if self._print_at_verbosity_level(4):
            intro = '{}++++++{}'.format(self._extra_prefix, self._extra_suffix)
            self._print(intro, *args, self._ansi_reset)
