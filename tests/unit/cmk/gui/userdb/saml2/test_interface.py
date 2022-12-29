#!/usr/bin/env python3
# Copyright (C) 2019 tribe29 GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import base64
import re
import time
import xml.etree.ElementTree as ET
import zlib
from itertools import zip_longest
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import parse_qs, urlparse

import pytest
from freezegun import freeze_time
from redis import Redis
from saml2.validate import ResponseLifetimeExceed, ToEarly

from cmk.utils.redis import get_redis_client
from cmk.utils.type_defs import UserId

from cmk.gui.userdb.saml2.connector import ConnectorConfig
from cmk.gui.userdb.saml2.interface import Authenticated, Interface, Milliseconds


def _encode(string: str) -> str:
    return base64.b64encode(string.encode("utf-8")).decode("utf-8")


def _reduce_xml_template_whitespace(template: str) -> str:
    # This is to simplify comparison by adjusting the format to the one the pysaml2 client
    # generates
    return " ".join(template.split()).replace("> <", "><")


class TestInterface:
    @pytest.fixture(autouse=True)
    def ignore_signature(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "saml2.sigver.SecurityContext._check_signature", lambda s, d, i, *args, **kwargs: i
        )

    @pytest.fixture(autouse=True)
    def initialised_redis(self, monkeypatch: pytest.MonkeyPatch) -> Iterable[Redis]:
        requests_db = get_redis_client()  # this is already monkeypatched to fakeredis
        requests_db.set(
            "saml2_authentication_requests:id-Ex1qiCa1tiZj1nBKe",
            "http://localhost:8080/simplesaml/saml2/idp/metadata.php",
        )
        monkeypatch.setattr(
            "cmk.gui.userdb.saml2.interface.AUTHORIZATION_REQUEST_ID_DATABASE", requests_db
        )
        yield requests_db

    @pytest.fixture
    def metadata(self, xml_files_path: Path) -> str:
        return _reduce_xml_template_whitespace(
            Path(xml_files_path / "checkmk_service_provider_metadata.xml").read_text()
        )

    @pytest.fixture
    def interface(self, metadata_from_idp: None, raw_config: dict[str, Any]) -> Interface:
        interface = Interface(ConnectorConfig(**raw_config).interface_config)
        interface.authentication_request_id_expiry = Milliseconds(-1)
        return interface

    @pytest.fixture
    def authentication_request(self, xml_files_path: Path) -> str:
        return _reduce_xml_template_whitespace(
            Path(xml_files_path / "authentication_request.xml").read_text()
        )

    @pytest.fixture
    def authentication_request_response(self, xml_files_path: Path) -> str:
        return _encode(Path(xml_files_path / "authentication_request_response.xml").read_text())

    @pytest.fixture
    def authentication_request_response_not_for_us(self, xml_files_path: Path) -> str:
        response = Path(xml_files_path / "authentication_request_response.xml").read_text()
        response = response.replace(
            "<saml:Audience>http://localhost/heute/check_mk/saml_metadata.py</saml:Audience>",
            "<saml:Audience>http://some_other_audience.com</saml:Audience>",
        )
        return _encode(response)

    @pytest.fixture(
        params=[
            '<saml:Condition xsi:type="xs:string">mycustomconditiion</saml:Condition>',
            "<saml:Condition>mycustomconditiion</saml:Condition>",
        ],
        ids=[
            "Valid custom condition",
            "Custom condition not well-formed (must have xsi:type defined)",
        ],
    )
    def authentication_request_response_custom_condition(
        self, xml_files_path: Path, request: pytest.FixtureRequest
    ) -> str:
        response = Path(xml_files_path / "authentication_request_response.xml").read_text()
        response = response.replace(
            "</saml:Conditions>",
            f"{request.param}</saml:Conditions>",
        )
        return _encode(response)

    @pytest.fixture(
        params=[
            ('InResponseTo="id-Ex1qiCa1tiZj1nBKe"', "", None),
            ('InResponseTo="id-Ex1qiCa1tiZj1nBKe"', 'InResponseTo=""', None),
            ('InResponseTo="id-Ex1qiCa1tiZj1nBKe"', 'InResponseTo="id-12345678901234567"', None),
            (
                'InResponseTo="id-Ex1qiCa1tiZj1nBKe"',
                'InResponseTo="id-12345678901234567"',
                "SubjectConfirmationData",
            ),
            (
                "<saml:Issuer>http://localhost:8080/simplesaml/saml2/idp/metadata.php</saml:Issuer>",
                "<saml:Issuer>http://hackerman</saml:Issuer>",
                None,
            ),
        ],
        ids=[
            "No InResponseTo ID",
            "Empty value for InResponseTo ID",
            "Unknown InResponseTo ID",
            "Inconsistent InResponseTo ID",
            "Unexpected entity issued response",
        ],
    )
    def unsolicited_authentication_request_response(
        self, xml_files_path: Path, request: pytest.FixtureRequest
    ) -> str:
        with open(xml_files_path / "authentication_request_response.xml", "r") as f:
            response = f.readlines()

        original_value, new_value, replacement_criteria = request.param

        modified_response = []
        for line in response:
            if replacement_criteria is None or replacement_criteria in line:
                line = line.replace(original_value, new_value)
            modified_response.append(line)

        return _encode("\n".join(modified_response))

    def test_interface_properties(self, interface: Interface) -> None:
        assert interface.acs_endpoint == (
            "http://localhost/heute/check_mk/saml_acs.py?acs",
            "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect",
        )
        assert interface.acs_binding == (
            "http://localhost/heute/check_mk/saml_acs.py?acs",
            "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST",
        )
        assert interface.idp_sso_binding == "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
        assert (
            interface.idp_sso_destination
            == "http://localhost:8080/simplesaml/saml2/idp/SSOService.php"
        )

    def test_metadata(self, interface: Interface, metadata: str) -> None:
        assert interface.metadata == metadata

    def test_authentication_request_contains_relay_state(self, interface: Interface) -> None:
        request = str(interface.authentication_request(relay_state="index.py"))
        parsed_query = parse_qs(urlparse(request).query)

        relay_state = parsed_query.get("RelayState")

        assert relay_state == ["index.py"]

    def test_authentication_request_is_valid(
        self, interface: Interface, authentication_request: str
    ) -> None:
        dynamic_elements = {
            "ID": re.compile("id-[a-zA-Z0-9]{17}"),
            "IssueInstant": re.compile("[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"),
        }  # These regex patterns are just to simplify comparison, they are not meant to test the conformity/standard of these fields

        request = str(interface.authentication_request(relay_state="_"))
        parsed_query = parse_qs(urlparse(request).query)

        saml_request = parsed_query.get("SAMLRequest")

        assert isinstance(saml_request, list)
        assert len(saml_request) == 1

        saml_request_decoded = zlib.decompress(base64.b64decode(saml_request[0]), -15).decode(
            "utf-8"
        )
        for actual_element, expected_element in zip_longest(
            sorted(ET.fromstring(saml_request_decoded).items()),
            sorted(ET.fromstring(authentication_request).items()),
        ):
            if regex_to_match := dynamic_elements.get(actual_element[0]):
                assert re.match(regex_to_match, actual_element[1])
            else:
                assert actual_element == expected_element

    @freeze_time("2022-12-28T11:06:05Z")
    def test_parse_successful_authentication_request_response(
        self, interface: Interface, authentication_request_response: str
    ) -> None:
        parsed_response = interface.parse_authentication_request_response(
            authentication_request_response
        )
        assert isinstance(parsed_response, Authenticated)
        assert parsed_response.in_response_to_id == "id-Ex1qiCa1tiZj1nBKe"
        assert parsed_response.user_id == UserId("user1")

    @freeze_time("2022-12-28T11:11:36Z")
    def test_parse_authentication_request_response_too_old(
        self, interface: Interface, authentication_request_response: str
    ) -> None:
        with pytest.raises(ResponseLifetimeExceed):
            interface.parse_authentication_request_response(authentication_request_response)

    @freeze_time("2022-12-28T11:06:04Z")
    def test_parse_authentication_request_response_too_young(
        self, interface: Interface, authentication_request_response: str
    ) -> None:
        with pytest.raises(ToEarly):
            interface.parse_authentication_request_response(authentication_request_response)

    def test_parse_garbage_xml_authentication_request_response(self, interface: Interface) -> None:
        with pytest.raises(Exception):
            interface.parse_authentication_request_response(_encode("<aardvark></aardvark>"))

    def test_parse_garbage_authentication_request_response(self, interface: Interface) -> None:
        with pytest.raises(ET.ParseError):
            interface.parse_authentication_request_response(_encode("aardvark"))

    @freeze_time("2022-12-28T11:06:05Z")
    def test_parse_authentication_request_response_is_not_for_us(
        self,
        interface: Interface,
        authentication_request_response_not_for_us: str,
    ) -> None:
        with pytest.raises(Exception):
            interface.parse_authentication_request_response(
                authentication_request_response_not_for_us
            )

    @freeze_time("2022-12-28T11:06:05Z")
    def test_parse_authentication_request_response_custom_condition(
        self,
        interface: Interface,
        authentication_request_response_custom_condition: str,
    ) -> None:
        with pytest.raises(Exception):
            interface.parse_authentication_request_response(
                authentication_request_response_custom_condition
            )

    @freeze_time("2022-12-28T11:06:05Z")
    def test_reject_unsolicited_authentication_request_response(
        self, interface: Interface, unsolicited_authentication_request_response: str
    ) -> None:
        with pytest.raises(AttributeError):
            interface.parse_authentication_request_response(
                unsolicited_authentication_request_response
            )

    def test_authentication_request_ids_expire(
        self, interface: Interface, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        redis = get_redis_client()  # this is already monkeypatched to fakeredis
        monkeypatch.setattr(
            "cmk.gui.userdb.saml2.interface.AUTHORIZATION_REQUEST_ID_DATABASE", redis
        )

        expiry = 1
        monkeypatch.setattr(interface, "authentication_request_id_expiry", expiry)

        interface.authentication_request(relay_state="_")

        time.sleep(expiry / 1000)

        assert not list(redis.keys("saml2_authentication_requests:*"))
