# -*- coding: utf-8 -*-
"""Generic support for iptables firewall management.

@author: Tobias Hunger <tobias.hunger@gmail.com>
"""


from ...exceptions import GenerateError
from ...location import Location
from ...systemcontext import SystemContext
from ..file import create_file

import os
import textwrap
import typing


_TCP_MAGIC = '#### Allowed TCP ports:'
_UDP_MAGIC = '#### Allowed UDP ports:'
_FORWARD_MAGIC = '#### Custom FORWARD rules:'

_IPv4_RULES = '/etc/iptables/iptables.rules'
_IPv6_RULES = '/etc/iptables/ip6tables.rules'


def install_rules(location: Location, system_context: SystemContext) -> None:
    """Install basic firewall rules."""
    assert firewall_type(system_context) is None
    set_firewall_type(system_context)

    if not os.path.isdir(system_context.file_name('/etc/iptables')):
        os.makedirs(system_context.file_name('/etc/iptables'))

    _install_v4_rules(location, system_context, _IPv4_RULES)
    _install_v6_rules(location, system_context, _IPv6_RULES)


def firewall_type(system_context: SystemContext) -> typing.Optional[str]:
    """Get type of firewall or None if none is active."""
    return system_context.substitution('CLRM_FIREWALL', None)


def set_firewall_type(system_context: SystemContext) -> None:
    """Set the type of firewall."""
    system_context.set_substitution('CLRM_FIREWALL', 'iptables')


def _insert_rules(file_name: str, magic: str, *rules: str) -> None:
    with open(file_name, 'r') as in_fd:
        input_rules = in_fd.read()

    output_rules: typing.List[str] = []
    for ir in input_rules.split('\n'):
        output_rules.append(ir)
        if ir in rules:
            raise GenerateError('Rule {} already found in iptables rules.'
                                .format(ir))
        if ir == magic:
            output_rules += rules

    with open(file_name, 'w') as out_fd:
        out_fd.write('\n'.join(output_rules))


def open_port(system_context: SystemContext, port: int, *,
              protocol: str = 'tcp', comment: str = '') -> None:
    """Open a port in the firewall."""
    magic = _TCP_MAGIC if protocol == 'tcp' else _UDP_MAGIC

    rules = ['# {}:\n'.format(comment)] if comment else []
    rules.append('-A {0} -p {1} -m {1} --dport {2} -j ACCEPT' \
                 .format(protocol.upper(), protocol, port))

    _insert_rules(system_context.file_name(_IPv4_RULES), magic, *rules)
    _insert_rules(system_context.file_name(_IPv6_RULES), magic, *rules)


def forward_interface(system_context: SystemContext, interface: str, *,
                      comment: str = '') -> None:
    magic = _FORWARD_MAGIC

    rules = ['# {}:\n'.format(comment)] if comment else []
    rules.append('-A FORWARD -i {} -j ACCEPT'.format(interface))
    rules.append('-A FORWARD -o {} -m conntrack '
                 '--ctstate RELATED,ESTABLISHED -j ACCEPT'
                 .format(interface))

    _insert_rules(system_context.file_name(_IPv4_RULES), magic, *rules)
    _insert_rules(system_context.file_name(_IPv6_RULES), magic, *rules)


def _install_v4_rules(location: Location, system_context: SystemContext,
                      rule_file: str) -> None:
    location.set_description('Install IPv4 rules')
    create_file(system_context, rule_file, textwrap.dedent("""\
                # iptables rules:

                *filter
                :INPUT DROP [0:0]
                :FORWARD DROP [0:0]
                :OUTPUT ACCEPT [66:5016]
                :TCP - [0:0]
                :UDP - [0:0]
                :LOGDROP - [0:0]
                
                -A LOGDROP -m limit --limit 5/m --limit-burst 10 -j LOG
                -A LOGDROP -j DROP

                -A FORWARD -m physdev --physdev-is-bridged -j ACCEPT

                {}

                -A FORWARD -j LOGDROP

                -A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
                -A INPUT -i lo -j ACCEPT
                -A INPUT -m conntrack --ctstate INVALID -j DROP
                -A INPUT -p icmp -m icmp --icmp-type 8 -m conntrack --ctstate NEW -j ACCEPT
                -A INPUT -p udp --dport 67:68 --sport 67:68 -j ACCEPT
                -A INPUT -p udp -m conntrack --ctstate NEW -j UDP
                -A INPUT -p tcp -m conntrack --ctstate NEW -j TCP
                -A INPUT -p udp -j REJECT --reject-with icmp-port-unreachable
                -A INPUT -p tcp -j REJECT --reject-with tcp-reset
                -A INPUT -j REJECT --reject-with icmp-proto-unreachable
                -A INPUT -j LOGDROP

                -A OUTPUT -p udp --dport 67:68 --sport 67:68 -j ACCEPT

                {}

                {}

                COMMIT
                """).format(_FORWARD_MAGIC, _TCP_MAGIC, _UDP_MAGIC)
                .encode('utf8'), force=True, mode=0o644)


def _install_v6_rules(location: Location, system_context: SystemContext, rule_file: str) -> None:
    location.set_description('Install IPv6 rules')
    create_file(system_context, rule_file, textwrap.dedent("""\
                # ip6tables rules:

                *filter
                :INPUT DROP [0:0]
                :FORWARD DROP [0:0]
                :OUTPUT ACCEPT [0:0]

                :TCP - [0:0]
                :UDP - [0:0]
                :LOGDROP - [0:0]

                -A LOGDROP -m limit --limit 5/m --limit-burst 10 -j LOG
                -A LOGDROP -j DROP

                -A FORWARD -m physdev --physdev-is-bridged -j ACCEPT

                {}

                -A FORWARD -j LOGDROP

                -A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT
                -A INPUT -i lo -j ACCEPT
                -A INPUT -m conntrack --ctstate INVALID -j DROP
                -A INPUT -p icmpv6 -j ACCEPT
                -A INPUT -p udp --dport 67:68 --sport 67:68 -j ACCEPT
                -A INPUT -p udp -m conntrack --ctstate NEW -j UDP
                -A INPUT -p tcp -m conntrack --ctstate NEW -j TCP
                -A INPUT -p udp -j REJECT --reject-with icmp6-port-unreachable
                -A INPUT -p tcp -j REJECT --reject-with tcp-reset
                -A INPUT -j REJECT --reject-with icmp6-port-unreachable
                -A INPUT -j LOGDROP

                -A OUTPUT -p udp --dport 67:68 --sport 67:68 -j ACCEPT

                {}

                {}

                COMMIT
                """).format(_FORWARD_MAGIC, _TCP_MAGIC, _UDP_MAGIC)
                .encode('utf8'), force=True, mode=0o644)
