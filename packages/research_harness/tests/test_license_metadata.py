from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def test_root_license_is_polyform_noncommercial() -> None:
    license_text = (ROOT / "LICENSE").read_text()

    assert (
        "Required Notice: Copyright 2026 Research Harness Contributors" in license_text
    )
    assert "PolyForm Noncommercial License 1.0.0" in license_text


def test_python_package_license_metadata_matches_root_license() -> None:
    expected = "PolyForm-Noncommercial-1.0.0"
    pyprojects = sorted((ROOT / "packages").glob("*/pyproject.toml"))

    assert pyprojects, "expected at least one package pyproject"
    for pyproject in pyprojects:
        data = tomllib.loads(pyproject.read_text())
        project = data.get("project", {})
        assert project.get("license") == expected, (
            f"{pyproject.relative_to(ROOT)} must not advertise a license "
            "different from the repository root"
        )
