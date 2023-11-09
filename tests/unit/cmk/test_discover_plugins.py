#!/usr/bin/env python3
# Copyright (C) 2022 Checkmk GmbH - License: GNU General Public License v2
# This file is part of Checkmk (https://checkmk.com). It is subject to the terms and
# conditions defined in the file COPYING, which is part of this source code package.

from collections.abc import Iterable
from dataclasses import dataclass
from types import ModuleType

import pytest

from cmk.discover_plugins import Collector, find_namespaces, PluginLocation


class AssumeDirs:
    """Fake os.listdir"""

    def __init__(self, *dirs: str) -> None:
        self._dirs = tuple(d.rstrip("/") for d in dirs)

    def __call__(self, path: str) -> Iterable[str]:
        path_ = path.rstrip("/")
        return sorted(
            {
                s
                for d in self._dirs
                if (s := d.removeprefix(path_).strip("/").split("/")[0]) and d.startswith(path_)
            }
        )


def test_assume_dirs() -> None:
    ls = AssumeDirs("/var/foo", "/var/bar", "/etc/var")
    assert ls("/var") == ["bar", "foo"]
    assert not ls("/usr")
    assert not ls("/etc/var")


def _make_module(name: str, path: list[str], **kwargs: object) -> ModuleType:
    m = ModuleType(name)
    m.__path__ = path
    for attr, value in kwargs.items():
        setattr(m, attr, value)
    return m


def test_find_namespaces_ignore_init() -> None:
    assert list(
        find_namespaces(
            (_make_module("cmk.plugins", ["/local/lib/cmk/plugins", "/lib/cmk/plugins"]),),
            "notification",
            ls=AssumeDirs(
                "/local/lib/cmk/plugins/foo/notification/bar.py",
                "/local/lib/cmk/plugins/foo/notification/__init__.py",
                "/local/lib/cmk/plugins/foo/notification/__pycache__",
                "/lib/cmk_hugo/plugins/gee/notification/nope.py",
                "/lib/cmk/plugins/okey/notification/hello.py",
            ),
        )
    ) == [
        "cmk.plugins.foo.notification.bar",
        "cmk.plugins.okey.notification.hello",
    ]


def test_find_namespaces_ignore_non_path_match() -> None:
    assert list(
        find_namespaces(
            (_make_module("cmk.plugins", ["/mypath/cmk/plugins"]),),
            "notification",
            ls=AssumeDirs(
                "/mypath/cmk/plugins/my_foo/notification/bar.py",
                "/otherpath/cmk/plugins/other_foo/notification/bar.py",
            ),
        )
    ) == [
        "cmk.plugins.my_foo.notification.bar",
    ]


def test_find_namespaces_deduplicate_preserving_order() -> None:
    assert list(
        find_namespaces(
            (
                _make_module("cmk.plugins", ["/lib/cmk/plugins"]),
                _make_module("cmk.plugins", ["/local/cmk/plugins"]),
            ),
            "notification",
            ls=AssumeDirs(
                "/lib/cmk/plugins/my_foo/notification/bar.py",
                "/lib/cmk/plugins/my_zoo/notification/bar.py",
                "/local/cmk/plugins/my_foo/notification/bar.py",
                "/local/cmk/plugins/my_boo/notification/bar.py",
            ),
        )
    ) == [
        "cmk.plugins.my_foo.notification.bar",
        "cmk.plugins.my_zoo.notification.bar",
        "cmk.plugins.my_boo.notification.bar",
    ]


@dataclass
class MyTestPlugin:
    name: str


@dataclass
class MyOtherPlugin:
    name: str


class TestCollector:
    def _importer(self, module_name: str, raise_errors: bool) -> ModuleType | None:
        """Fake importable modules"""
        match module_name:
            case "nonexistant":
                return None
            case "my_module":
                return _make_module("my_module", [], my_plugin_1=MyTestPlugin("herta"))
            case "my_other_type":
                return _make_module("my_other_type", [], my_plugin_2=MyOtherPlugin("herta"))
            case "my_collision":
                return _make_module("my_collision", [], my_plugin_3=MyTestPlugin("herta"))

        raise ValueError("this test seems broken")

    def test_sipmle_ok_case(self) -> None:
        """Load a plugin"""
        collector = Collector(MyTestPlugin, "my_", raise_errors=False)
        collector.add_from_module("my_module", self._importer)
        assert not collector.errors
        assert collector.plugins == {
            PluginLocation("my_module", "my_plugin_1"): MyTestPlugin("herta"),
        }

    def test_mising_ok(self) -> None:
        """Ignore missing modules"""
        collector = Collector(MyTestPlugin, "my_", raise_errors=True)
        # missing is ok, even if raise_errors is true.
        collector.add_from_module("nonexistant", self._importer)
        assert not collector.errors
        assert not collector.plugins

    def test_unknown_name_ignored(self) -> None:
        """Do not load a plugin with name prefix missmatch"""
        collector = Collector(MyTestPlugin, "your_", raise_errors=False)
        collector.add_from_module("my_module", self._importer)
        assert not collector.errors
        assert not collector.plugins

    def test_wrong_type_raise(self) -> None:
        """Raise if a plugin has the wrong type"""
        collector = Collector(MyTestPlugin, "my_", raise_errors=True)

        with pytest.raises(TypeError):
            collector.add_from_module("my_other_type", self._importer)

    def test_wrong_type_recorded(self) -> None:
        """Record the error if a plugin has the wrong type"""
        collector = Collector(MyTestPlugin, "my_", raise_errors=False)
        collector.add_from_module("my_other_type", self._importer)
        assert len(collector.errors) == 1
        assert isinstance(collector.errors[0], TypeError)
        assert not collector.plugins

    def test_name_collision_same_type(self) -> None:
        collector = Collector(MyTestPlugin, "my_", raise_errors=False)
        collector.add_from_module("my_module", self._importer)
        collector.add_from_module("my_collision", self._importer)
        # FIXME: colliding name should yield an error.
        assert not collector.errors
        assert collector.plugins == {
            PluginLocation("my_collision", "my_plugin_3"): MyTestPlugin("herta"),
            PluginLocation("my_module", "my_plugin_1"): MyTestPlugin("herta"),
        }

    def test_name_collision_different_type(self) -> None:
        collector = Collector(object, "my_", raise_errors=False)
        collector.add_from_module("my_module", self._importer)
        collector.add_from_module("my_other_type", self._importer)
        assert not collector.errors
        assert collector.plugins == {
            PluginLocation("my_module", "my_plugin_1"): MyTestPlugin("herta"),
            PluginLocation("my_other_type", "my_plugin_2"): MyOtherPlugin("herta"),
        }
