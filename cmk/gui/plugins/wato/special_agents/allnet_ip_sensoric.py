#!/usr/bin/env python3
# Copyright (C) 2019 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.


from cmk.utils.rulesets.definition import RuleGroup

from cmk.gui.i18n import _
from cmk.gui.plugins.wato.utils import HostRulespec, rulespec_registry
from cmk.gui.valuespec import Dictionary, Integer
from cmk.gui.wato import RulespecGroupDatasourceProgramsHardware


def _valuespec_special_agents_allnet_ip_sensoric():
    return Dictionary(
        title=_("ALLNET IP Sensoric Devices"),
        help=_(
            "This rule selects the ALLNET IP Sensoric agent, which fetches "
            "/xml/sensordata.xml from the device by HTTP and extracts the "
            "needed monitoring information from this file."
        ),
        elements=[
            (
                "timeout",
                Integer(
                    title=_("Connect timeout"),
                    help=_(
                        "The network timeout in seconds when communicating via HTTP. "
                        "The default is 10 seconds."
                    ),
                    default_value=10,
                    minvalue=1,
                    unit=_("seconds"),
                ),
            ),
        ],
        optional_keys=["timeout"],
    )


rulespec_registry.register(
    HostRulespec(
        group=RulespecGroupDatasourceProgramsHardware,
        name=RuleGroup.SpecialAgents("allnet_ip_sensoric"),
        valuespec=_valuespec_special_agents_allnet_ip_sensoric,
    )
)
