#!/usr/bin/env python3
# Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, MutableSequence, NewType

from cmk.gui.quick_setup.v0_unstable.widgets import FormSpecId

StageId = NewType("StageId", int)
QuickSetupId = NewType("QuickSetupId", str)
RawFormData = NewType("RawFormData", Mapping[FormSpecId, object])
ParsedFormData = Mapping[FormSpecId, Any]
GeneralStageErrors = MutableSequence[str]


@dataclass(frozen=True)
class ServiceInterest:
    check_plugin_name_pattern: str
    label: str
