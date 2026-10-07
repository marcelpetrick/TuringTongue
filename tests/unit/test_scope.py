# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marcel Petrick <mail@marcelpetrick.it>
"""Guard for ADR 0005: the package integrates external detection services only."""

import tomllib
from pathlib import Path

import pytest

from turingtongue import Registry, TransportKind

pytestmark = pytest.mark.unit
ROOT = Path(__file__).parents[2]
FORBIDDEN_DEPENDENCIES = ("torch", "transformers", "tensorflow", "jax", "onnxruntime", "sklearn")


def test_every_real_provider_is_an_external_service() -> None:
    for spec in Registry.builtin():
        if spec.transport is TransportKind.MOCK:
            assert spec.id == "mock"
            assert not spec.enabled_by_default
            continue
        assert spec.transport in {TransportKind.API, TransportKind.SDK, TransportKind.BROWSER}
        assert spec.docs_url.startswith("https://")


def test_no_local_model_dependencies() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    declared = list(project["dependencies"])
    for extra in project.get("optional-dependencies", {}).values():
        declared.extend(extra)
    for requirement in declared:
        assert not requirement.lower().startswith(FORBIDDEN_DEPENDENCIES), requirement


def test_transport_kinds_have_no_local_detector() -> None:
    assert {kind.value for kind in TransportKind} == {"api", "sdk", "browser", "mock"}
