#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
import os
import pprint
import socket
import subprocess
import sys
import time
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Protocol

import cmk.utils.debug
import cmk.utils.paths
import cmk.utils.tty as tty
from cmk.utils.caching import cache_manager, DictCache
from cmk.utils.exceptions import MKGeneralException, MKIPAddressLookupError
from cmk.utils.hostaddress import HostAddress, HostName, Hosts
from cmk.utils.log import console

from cmk.automations.results import Gateway, GatewayResult

import cmk.base.obsolete_output as out
from cmk.base.config import ConfigCache
from cmk.base.ip_lookup import IPStackConfig


class _IpAddressLookup(Protocol):
    def __call__(
        self, hostname: HostName, *, family: socket.AddressFamily
    ) -> HostAddress | None: ...


def do_scan_parents(
    config_cache: ConfigCache,
    hosts_config: Hosts,
    monitoring_host: HostName | None,
    hosts: list[HostName],
    *,
    max_num_processes: int,
    lookup_ip_address: _IpAddressLookup,
) -> None:
    # pylint: disable=too-many-branches
    if not hosts:
        hosts = sorted(
            {
                hn
                for hn in hosts_config.hosts
                if config_cache.is_active(hn) and config_cache.is_online(hn)
            }
        )

    parent_hosts = []
    parent_ips: dict[HostName, HostAddress] = {}
    parent_rules = []
    gateway_hosts: set[HostName] = set()

    outfilename = Path(cmk.utils.paths.check_mk_config_dir) / "parents.mk"

    if not traceroute_available():
        raise MKGeneralException(
            'The program "traceroute" was not found.\n'
            "The parent scan needs this program.\n"
            "Please install it and try again."
        )

    if outfilename.exists():
        with outfilename.open(mode="r") as outfile:
            first_line = outfile.readline()

        if not first_line.startswith("# Automatically created by --scan-parents at"):
            raise MKGeneralException(
                "conf.d/parents.mk seems to be created manually.\n\n"
                "The --scan-parents function would overwrite this file.\n"
                "Please rename it to keep the configuration or delete "
                "the file and try again."
            )

    out.output("Scanning for parents (%d processes)..." % max_num_processes)
    while hosts:
        chunk: list[HostName] = []
        while len(chunk) < max_num_processes and hosts:
            host = hosts.pop()

            # skip hosts that already have a parent
            if config_cache.parents(host):
                console.verbose("(manual parent) ")
                continue
            chunk.append(host)

        results = scan_parents_of(
            config_cache, hosts_config, monitoring_host, chunk, lookup_ip_address=lookup_ip_address
        )

        for host, result in zip(chunk, results):
            if gw := result.gateway:
                if not gw.existing_gw_host_name:  # create artificial host
                    if gw.dns_name:
                        gateway = gw.dns_name
                    else:
                        gateway = HostName("gw-%s" % (gw.ip.replace(".", "-")))
                    if gateway not in gateway_hosts:
                        gateway_hosts.add(gateway)
                        parent_hosts.append("%s|parent|ping" % gateway)
                        parent_ips[gateway] = gw.ip
                        if monitoring_host:
                            parent_rules.append(
                                (monitoring_host, [gateway])
                            )  # make Nagios a parent of gw
                parent_rules.append((gateway, [host]))
            elif host != monitoring_host and monitoring_host:
                # make monitoring host the parent of all hosts without real parent
                parent_rules.append((monitoring_host, [host]))

    with outfilename.open(mode="w") as file:
        file.write("# Automatically created by --scan-parents at %s\n\n" % time.asctime())
        file.write("# Do not edit this file. If you want to convert an\n")
        file.write("# artificial gateway host into a permanent one, then\n")
        file.write("# move its definition into another *.mk file\n")

        file.write("# Parents which are not listed in your all_hosts:\n")
        file.write("all_hosts += %s\n\n" % pprint.pformat(parent_hosts))

        file.write("# IP addresses of parents not listed in all_hosts:\n")
        file.write("ipaddresses.update(%s)\n\n" % pprint.pformat(parent_ips))

        file.write("# Parent definitions\n")
        file.write("parents += %s\n\n" % pprint.pformat(parent_rules))
    out.output("\nWrote %s\n" % outfilename)


def traceroute_available() -> str | None:
    for path in os.environ["PATH"].split(os.pathsep):
        f = path + "/traceroute"
        if os.path.exists(f) and os.access(f, os.X_OK):
            return f
    return None


def scan_parents_of(
    config_cache: ConfigCache,
    hosts_config: Hosts,
    monitoring_host: HostName | None,
    hosts: Iterable[HostName],
    silent: bool = False,
    settings: dict[str, int] | None = None,
    *,
    lookup_ip_address: _IpAddressLookup,
) -> Sequence[GatewayResult]:
    # pylint: disable=too-many-branches
    if settings is None:
        settings = {}

    nagios_ip = (
        None
        if (
            monitoring_host is None
            or ConfigCache.ip_stack_config(monitoring_host) is IPStackConfig.NO_IP
        )
        else lookup_ip_address(monitoring_host, family=socket.AddressFamily.AF_INET)
    )

    os.putenv("LANG", "")
    os.putenv("LC_ALL", "")

    # Start processes in parallel
    procs: list[tuple[HostName, HostAddress | None, str | subprocess.Popen]] = []
    for host in hosts:
        console.verbose("%s " % host)
        if ConfigCache.ip_stack_config(host) is IPStackConfig.NO_IP:
            procs.append((host, None, "ERROR: Configured to be a No-IP host"))
            continue

        try:
            ip = lookup_ip_address(
                host,
                # [IPv6] -- what about it?
                family=socket.AddressFamily.AF_INET,
            )
            if ip is None:
                raise RuntimeError()
            command = [
                "traceroute",
                "-w",
                "%d" % settings.get("timeout", 8),
                "-q",
                "%d" % settings.get("probes", 2),
                "-m",
                "%d" % settings.get("max_ttl", 10),
                "-n",
                ip,
            ]
            console.vverbose("Running '%s'\n" % subprocess.list2cmdline(command))

            procs.append(
                (
                    host,
                    ip,
                    subprocess.Popen(  # pylint: disable=consider-using-with
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        close_fds=True,
                        encoding="utf-8",
                    ),
                )
            )
        except Exception as e:
            if cmk.utils.debug.enabled():
                raise
            procs.append((host, None, "ERROR: %s" % e))

    # Output marks with status of each single scan
    def dot(color: str, dot: str = "o") -> None:
        if not silent:
            out.output(tty.bold + color + dot + tty.normal)

    # Now all run and we begin to read the answers. For each host
    # we add a triple to gateways: the gateway, a scan state  and a diagnostic output
    gateways: list[GatewayResult] = []
    for host, ip, proc_or_error in procs:
        if isinstance(proc_or_error, str):
            lines = [proc_or_error]
            exitstatus = 1
        else:
            exitstatus = proc_or_error.wait()
            if proc_or_error.stdout is None:
                raise RuntimeError()
            lines = [l.strip() for l in proc_or_error.stdout.readlines()]

        if exitstatus:
            dot(tty.red, "*")
            gateways.append(
                GatewayResult(
                    None, "failed", 0, "Traceroute failed with exit code %d" % (exitstatus & 255)
                )
            )
            continue

        if len(lines) == 1 and lines[0].startswith("ERROR:"):
            message = lines[0][6:].strip()
            console.verbose("%s: %s\n", host, message, stream=sys.stderr)
            dot(tty.red, "D")
            gateways.append(GatewayResult(None, "dnserror", 0, message))
            continue

        if len(lines) == 0:
            if cmk.utils.debug.enabled():
                raise MKGeneralException(
                    "Cannot execute %s. Is traceroute installed? Are you root?" % command
                )
            dot(tty.red, "!")
            continue

        if len(lines) < 2:
            if not silent:
                console.error("{}: {}\n".format(host, " ".join(lines)))
            gateways.append(
                GatewayResult(
                    None,
                    "garbled",
                    0,
                    "The output of traceroute seem truncated:\n%s" % ("".join(lines)),
                )
            )
            dot(tty.blue)
            continue

        # Parse output of traceroute:
        # traceroute to 8.8.8.8 (8.8.8.8), 30 hops max, 40 byte packets
        #  1  * * *
        #  2  10.0.0.254  0.417 ms  0.459 ms  0.670 ms
        #  3  172.16.0.254  0.967 ms  1.031 ms  1.544 ms
        #  4  217.0.116.201  23.118 ms  25.153 ms  26.959 ms
        #  5  217.0.76.134  32.103 ms  32.491 ms  32.337 ms
        #  6  217.239.41.106  32.856 ms  35.279 ms  36.170 ms
        #  7  74.125.50.149  45.068 ms  44.991 ms *
        #  8  * 66.249.94.86  41.052 ms 66.249.94.88  40.795 ms
        #  9  209.85.248.59  43.739 ms  41.106 ms 216.239.46.240  43.208 ms
        # 10  216.239.48.53  45.608 ms  47.121 ms 64.233.174.29  43.126 ms
        # 11  209.85.255.245  49.265 ms  40.470 ms  39.870 ms
        # 12  8.8.8.8  28.339 ms  28.566 ms  28.791 ms
        routes: list[HostAddress | None] = []
        for line in lines[1:]:
            parts = line.split()
            route = parts[1]
            if route.count(".") == 3:
                routes.append(HostAddress(route))
            elif route == "*":
                routes.append(None)  # No answer from this router
            else:
                if not silent:
                    console.error(f"{host}: invalid output line from traceroute: '{line}'\n")

        if len(routes) == 0:
            error = "incomplete output from traceroute. No routes found."
            console.error(f"{host}: {error}\n")
            gateways.append(GatewayResult(None, "garbled", 0, error))
            dot(tty.red)
            continue

        # Only one entry -> host is directly reachable and gets nagios as parent -
        # if nagios is not the parent itself. Problem here: How can we determine
        # if the host in question is the monitoring host? The user must configure
        # this in monitoring_host.
        if len(routes) == 1:
            if ip == nagios_ip:
                gateways.append(
                    GatewayResult(None, "root", 0, "")
                )  # We are the root-monitoring host
                dot(tty.white, "N")
            elif monitoring_host and nagios_ip:
                gateways.append(
                    GatewayResult(Gateway(monitoring_host, nagios_ip, None), "direct", 0, "")
                )
                dot(tty.cyan, "L")
            else:
                gateways.append(GatewayResult(None, "direct", 0, ""))
            continue

        # Try far most route which is not identical with host itself
        ping_probes = settings.get("ping_probes", 5)
        skipped_gateways = 0
        this_route: HostAddress | None = None
        for r in routes[::-1]:
            if not r or (r == ip):
                continue
            # Do (optional) PING check in order to determine if that
            # gateway can be monitored via the standard host check
            if ping_probes:
                if not gateway_reachable_via_ping(r, ping_probes):
                    console.verbose("(not using %s, not reachable)\n", r, stream=sys.stderr)
                    skipped_gateways += 1
                    continue
            this_route = r
            break
        if not this_route:
            error = "No usable routing information"
            if not silent:
                console.error(f"{host}: {error}\n")
            gateways.append(GatewayResult(None, "notfound", 0, error))
            dot(tty.blue)
            continue

        # TTLs already have been filtered out)
        gateway_ip = this_route
        gateway = _ip_to_hostname(
            config_cache, hosts_config, this_route, lookup_ip_address=lookup_ip_address
        )
        if gateway:
            console.verbose("%s(%s) ", gateway, gateway_ip)
        else:
            console.verbose("%s ", gateway_ip)

        # Try to find DNS name of host via reverse DNS lookup
        dns_name = _ip_to_dnsname(gateway_ip)
        gateways.append(
            GatewayResult(Gateway(gateway, gateway_ip, dns_name), "gateway", skipped_gateways, "")
        )
        dot(tty.green, "G")
    return gateways


def gateway_reachable_via_ping(ip: HostAddress, probes: int) -> bool:
    return (
        subprocess.call(
            ["ping", "-q", "-i", "0.2", "-l", "3", "-c", "%d" % probes, "-W", "5", ip],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
            close_fds=True,
        )
        == 0
    )


def _ip_to_hostname(
    config_cache: ConfigCache,
    hosts_config: Hosts,
    ip: HostAddress | None,
    lookup_ip_address: _IpAddressLookup,
) -> HostName | None:
    """Find hostname belonging to an ip address."""
    absent = "ip_to_hostname" not in cache_manager
    cache = cache_manager.obtain_cache("ip_to_hostname")
    if absent:
        _fill_ip_to_hostname_cache(
            cache, config_cache, hosts_config, lookup_ip_address=lookup_ip_address
        )

    return cache.get(ip)


def _fill_ip_to_hostname_cache(
    cache: DictCache,
    config_cache: ConfigCache,
    hosts_config: Hosts,
    *,
    lookup_ip_address: _IpAddressLookup,
) -> None:
    """We must not use reverse DNS but the Checkmk mechanisms, since we do not
    want to find the DNS name but the name of a matching host from all_hosts"""
    for host in {
        # inconsistent with do_scan_parents where a list of hosts could be passed as an argument
        hn
        for hn in hosts_config.hosts
        if config_cache.is_active(hn) and config_cache.is_online(hn)
    }:
        if ConfigCache.ip_stack_config(host) is IPStackConfig.NO_IP:
            continue
        try:
            cache[lookup_ip_address(host, family=socket.AddressFamily.AF_INET)] = host
        except MKIPAddressLookupError:
            pass


def _ip_to_dnsname(ip: HostAddress) -> HostName | None:
    try:
        return HostName(socket.gethostbyaddr(ip)[0])
    except Exception:
        return None
