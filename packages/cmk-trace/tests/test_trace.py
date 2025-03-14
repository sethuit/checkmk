#!/usr/bin/env python3
# Copyright (C) 2024 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

import logging
from collections.abc import Iterator
from contextlib import contextmanager

import opentelemetry.sdk.trace as sdk_trace
import pytest
from opentelemetry import context as otel_context
from opentelemetry import trace as otel_trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

from cmk import trace


def test_trace_send_config() -> None:
    assert trace.trace_send_config(
        {
            "CONFIG_ADMIN_MAIL": "",
            "CONFIG_AGENT_RECEIVER": "on",
            "CONFIG_AGENT_RECEIVER_PORT": "8000",
            "CONFIG_APACHE_MODE": "own",
            "CONFIG_APACHE_TCP_ADDR": "127.0.0.1",
            "CONFIG_APACHE_TCP_PORT": "5002",
            "CONFIG_AUTOSTART": "off",
            "CONFIG_CORE": "cmc",
            "CONFIG_LIVEPROXYD": "on",
            "CONFIG_LIVESTATUS_TCP": "off",
            "CONFIG_LIVESTATUS_TCP_ONLY_FROM": "0.0.0.0 ::/0",
            "CONFIG_LIVESTATUS_TCP_PORT": "6557",
            "CONFIG_LIVESTATUS_TCP_TLS": "on",
            "CONFIG_MKEVENTD": "on",
            "CONFIG_MKEVENTD_SNMPTRAP": "off",
            "CONFIG_MKEVENTD_SYSLOG": "on",
            "CONFIG_MKEVENTD_SYSLOG_TCP": "off",
            "CONFIG_MULTISITE_AUTHORISATION": "on",
            "CONFIG_MULTISITE_COOKIE_AUTH": "on",
            "CONFIG_NSCA": "off",
            "CONFIG_NSCA_TCP_PORT": "5667",
            "CONFIG_PNP4NAGIOS": "on",
            "CONFIG_RABBITMQ_PORT": "5672",
            "CONFIG_TMPFS": "on",
            "CONFIG_TRACE_JAEGER_ADMIN_PORT": "14269",
            "CONFIG_TRACE_JAEGER_UI_PORT": "13333",
            "CONFIG_TRACE_RECEIVE": "off",
            "CONFIG_TRACE_RECEIVE_ADDRESS": "[::1]",
            "CONFIG_TRACE_RECEIVE_PORT": "4321",
            "CONFIG_TRACE_SEND": "off",
            "CONFIG_TRACE_SEND_TARGET": "local_site",
        }
    ) == trace.TraceSendConfig(enabled=False, target=trace.LocalTarget(4321))


def test_exporter_from_config_disabled() -> None:
    assert (
        trace.exporter_from_config(
            trace.TraceSendConfig(enabled=False, target=trace.LocalTarget(1234)),
        )
        is None
    )


class StubExporter(OTLPSpanExporter):
    def __init__(
        self,
        endpoint: str | None = None,
        insecure: bool | None = None,
        timeout: int | None = None,
    ):
        super().__init__(
            endpoint=endpoint,
            insecure=insecure,
            credentials=None,
            headers=None,
            timeout=timeout,
            compression=None,
        )
        self.test_endpoint = endpoint
        self.test_timeout = timeout
        self.test_insecure = insecure


def test_exporter_from_config_local_site() -> None:
    config = trace.TraceSendConfig(enabled=True, target=trace.LocalTarget(1234))
    exporter = trace.exporter_from_config(config, StubExporter)
    assert isinstance(exporter, StubExporter)
    assert exporter.test_timeout == 3
    assert exporter.test_endpoint == "http://localhost:1234"
    assert exporter.test_insecure is True


@pytest.fixture(name="reset_global_tracer_provider")
def _fixture_reset_global_tracer_provider() -> Iterator[None]:
    # pylint: disable=protected-access
    provider_orig = otel_trace._TRACER_PROVIDER
    try:
        yield
    finally:
        otel_trace._TRACER_PROVIDER_SET_ONCE._done = False
        otel_trace._TRACER_PROVIDER = provider_orig


@pytest.mark.usefixtures("reset_global_tracer_provider")
def test_get_tracer_after_initialized() -> None:
    trace.init_tracing("namespace", "service")

    tracer = trace.get_tracer()
    assert isinstance(tracer, sdk_trace.Tracer)
    assert tracer.instrumentation_info.name == "cmk.trace"
    assert tracer.instrumentation_info.version == ""


@pytest.mark.usefixtures("reset_global_tracer_provider")
def test_get_tracer_verify_provider_attributes() -> None:
    trace.init_tracing("namespace", "service", "myhost")

    tracer = trace.get_tracer()
    assert isinstance(tracer, sdk_trace.Tracer)

    assert tracer.resource.attributes["service.name"] == "namespace.service"
    assert tracer.resource.attributes["service.version"] == "0.0.1"
    assert tracer.resource.attributes["service.namespace"] == "namespace"
    assert tracer.resource.attributes["host.name"] == "myhost"


@pytest.mark.usefixtures("reset_global_tracer_provider")
def test_get_current_span_without_span() -> None:
    with initial_span_context():
        trace.init_tracing("namespace", "service")
        assert trace.get_current_span() == otel_trace.INVALID_SPAN


@pytest.mark.usefixtures("reset_global_tracer_provider")
def test_get_current_span_with_span() -> None:
    trace.init_tracing("namespace", "service")
    with trace.get_tracer().start_as_current_span("test") as span:
        assert trace.get_current_span() == span


@pytest.mark.usefixtures("reset_global_tracer_provider")
def test_get_current_tracer_provider() -> None:
    provider = trace.init_tracing("namespace", "service")
    assert provider == trace.get_current_tracer_provider()


def test_init_logging_attaches_logs_as_events(caplog: pytest.LogCaptureFixture) -> None:
    logger = logging.getLogger("cmk.trace.test")
    caplog.set_level(logging.INFO, logger="cmk.trace.test")

    with trace_logging(logger):
        trace.init_tracing("namespace", "service")
        with trace.get_tracer().start_as_current_span("test") as span:
            logger.info("HELLO")
            assert isinstance(span, sdk_trace.ReadableSpan)
            assert len(span.events) == 1
            assert span.events[0].name == "HELLO"
            assert span.events[0].attributes is not None
            assert span.events[0].attributes["log.level"] == "INFO"


@contextmanager
def trace_logging(logger: logging.Logger) -> Iterator[None]:
    orig_handlers = logger.handlers

    try:
        trace.init_logging()
        yield
    finally:
        logger.handlers = orig_handlers


@contextmanager
def initial_span_context() -> Iterator[None]:
    token = otel_context.attach(otel_trace.set_span_in_context(otel_trace.INVALID_SPAN))
    try:
        otel_trace.set_span_in_context(otel_trace.INVALID_SPAN)
        yield
    finally:
        otel_context.detach(token)
