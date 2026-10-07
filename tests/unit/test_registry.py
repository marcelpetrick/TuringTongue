# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
import pytest

from tests.helpers import EchoProvider, registry
from turingtongue.errors import ConfigurationError
from turingtongue.models import TransportKind
from turingtongue.normalization.limits import LimitUnit
from turingtongue.registry import Registry

pytestmark = pytest.mark.unit


def test_builtin_registry_loads_and_all_adapters_import() -> None:
    reg = Registry.builtin()
    assert "mock" in reg
    assert len(reg) == len(reg.ids())
    for spec in reg:
        assert spec.load_adapter() is not None
        assert spec.last_verified
        assert spec.adapter_status


def test_spec_fields() -> None:
    reg = registry()
    echo = reg.get(" ECHO ")
    assert echo.transport is TransportKind.API
    assert echo.limit_unit is LimitUnit.WORDS
    assert echo.known_max_input == 10
    assert echo.load_adapter() is EchoProvider
    assert echo.missing_credentials({"ECHO_KEY": " "}) == ["ECHO_KEY"]
    assert echo.missing_credentials({"ECHO_KEY": "k"}) == []
    assert echo.missing_credentials() == ["ECHO_KEY"]


def test_extra_fields_preserved() -> None:
    reg = registry('plan = "pro"\n')
    assert reg.get("mock").extra == {"plan": "pro"}


def test_unknown_provider() -> None:
    with pytest.raises(ConfigurationError, match="Known providers: echo"):
        registry().get("nope")


def test_missing_required_fields() -> None:
    with pytest.raises(ConfigurationError, match="lacks fields"):
        Registry.from_toml("[providers.x]\nname = 'x'\n")
