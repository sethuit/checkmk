#!/usr/bin/env python3
# Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.
from typing import Callable, Sequence

from cmk.gui.form_specs.vue.autogen_type_defs import vue_formspec_components as VueComponents
from cmk.gui.form_specs.vue.registries import FormSpecVisitor
from cmk.gui.form_specs.vue.type_defs import DEFAULT_VALUE, EmptyValue, Value
from cmk.gui.form_specs.vue.utils import (
    compute_validation_errors,
    compute_validators,
    create_validation_error,
    get_title_and_help,
    localize,
)
from cmk.gui.form_specs.vue.validators import build_vue_validators

from cmk.ccc.exceptions import MKGeneralException
from cmk.rulesets.v1 import Title
from cmk.rulesets.v1.form_specs import FixedValue

_FixedValueT = int | float | str | bool | None


class FixedValueVisitor(FormSpecVisitor[FixedValue, _FixedValueT]):
    def _parse_value(self, raw_value: object) -> _FixedValueT | EmptyValue:
        return self.form_spec.value

    def _validators(self) -> Sequence[Callable[[_FixedValueT], object]]:
        return list(self.form_spec.custom_validate) if self.form_spec.custom_validate else []

    def _to_vue(
        self, raw_value: object, parsed_value: _FixedValueT | EmptyValue
    ) -> tuple[VueComponents.FixedValue, Value]:
        title, help_text = get_title_and_help(self.form_spec)
        return (
            VueComponents.FixedValue(
                title=title,
                help=help_text,
                label=localize(self.form_spec.label),
                value=parsed_value,
                validators=build_vue_validators(compute_validators(self.form_spec)),
            ),
            parsed_value,
        )

    def _validate(
        self, raw_value: object, parsed_value: _FixedValueT | EmptyValue
    ) -> list[VueComponents.ValidationMessage]:
        if isinstance(parsed_value, EmptyValue):
            # Note: this code should be unreachable, because the parse function always returns a valid value
            return create_validation_error(
                "" if raw_value == DEFAULT_VALUE else raw_value, Title("Invalid FixedValue")
            )
        return compute_validation_errors(compute_validators(self.form_spec), raw_value)

    def _to_disk(self, raw_value: object, parsed_value: _FixedValueT | EmptyValue) -> _FixedValueT:
        if isinstance(parsed_value, EmptyValue):
            raise MKGeneralException("Unable to serialize empty value")
        return parsed_value
