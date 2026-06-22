# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_TEMPLATE = ROOT / "template"
PACKAGE_TEMPLATE = ROOT / "src" / "vaultwright" / "template"


def generated_cache(path: Path) -> bool:
    return "__pycache__" in path.parts or path.suffix == ".pyc"


def template_files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file() and not generated_cache(path)
    }


def test_packaged_template_matches_repository_template() -> None:
    source_files = template_files(SOURCE_TEMPLATE)
    package_files = template_files(PACKAGE_TEMPLATE)

    assert package_files == source_files
    assert ".gitignore" in package_files
    assert "tools/catalog_report.py" in package_files
    assert "tools/conversion_report.py" in package_files
    assert "tools/m365_report.py" in package_files
    assert "tools/migration_report.py" in package_files
    assert "tools/overlap_report.py" in package_files
    assert "tools/pilot_report.py" in package_files
    assert "tools/recovery_report.py" in package_files
    assert "tools/review_ledger.py" in package_files
    assert "tools/sandbox_report.py" in package_files
    assert "80_sources/repos/.gitkeep" in package_files
