#!/usr/bin/env python3
# Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
from __future__ import annotations

from dataclasses import dataclass

from cmk.gui.quick_setup.v0_unstable.type_defs import RawFormData, StageId

from cmk.ccc.exceptions import MKGeneralException


@dataclass
class IncomingStage:  # Request
    stage_id: StageId
    form_data: RawFormData


@dataclass
class QuickSetupSaveRedirect:
    redirect_url: str | None = None


class QuickSetupNotFoundException(MKGeneralException):
    pass


UniqueFormSpecIDStr = "formspec_unique_id"
UniqueBundleIDStr = "bundle_id"
