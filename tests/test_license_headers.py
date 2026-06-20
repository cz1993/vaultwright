# SPDX-License-Identifier: AGPL-3.0-or-later
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPDX = "SPDX-License-Identifier: AGPL-3.0-or-later"


def source_files() -> list[Path]:
    files: list[Path] = [
        ROOT / ".githooks" / "pre-commit",
        *sorted((ROOT / "scripts").glob("*.sh")),
        *sorted((ROOT / "scripts").glob("*.py")),
        *sorted((ROOT / "src").rglob("*.py")),
        *sorted((ROOT / "template" / "tools").glob("*.py")),
        *sorted((ROOT / "template" / "tools").glob("*.sh")),
        *sorted((ROOT / "tests").glob("*.py")),
    ]
    for example in sorted((ROOT / "examples").glob("*-vault")):
        files.extend(sorted((example / "tools").glob("*.py")))
        files.extend(sorted((example / "tools").glob("*.sh")))
        files.extend(sorted((example / "_fixtures").rglob("*.py")))
    return files


def test_source_files_have_spdx_headers() -> None:
    missing: list[str] = []
    for path in source_files():
        lines = path.read_text(encoding="utf-8").splitlines()
        if not any(SPDX in line for line in lines[:3]):
            missing.append(path.relative_to(ROOT).as_posix())
    assert not missing


def test_license_is_vendored_agpl_text() -> None:
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "GNU AFFERO GENERAL PUBLIC LICENSE" in license_text
    assert "Version 3, 19 November 2007" in license_text
    assert "VENDORING TODO" not in license_text


def test_python_package_uses_modern_license_metadata() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = pyproject["project"]

    assert project["license"] == "AGPL-3.0-or-later"
    assert project["license-files"] == ["LICENSE", "NOTICE"]
    assert "setuptools>=77" in pyproject["build-system"]["requires"]
    assert not any(
        classifier.startswith("License ::") for classifier in project.get("classifiers", [])
    )
