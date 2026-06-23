# SPDX-License-Identifier: AGPL-3.0-or-later
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"
RELEASE_DOC = ROOT / "docs" / "RELEASE.md"
PYPROJECT = ROOT / "pyproject.toml"


def test_release_workflow_is_tag_only_and_draft_prerelease() -> None:
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "tags:" in text
    assert '"v*"' in text
    assert "branches:" not in text
    assert "gh release create" in text
    assert "--draft" in text
    assert "--prerelease" in text


def test_release_checklist_tag_matches_package_version() -> None:
    pyproject = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    init_text = (ROOT / "src" / "vaultwright" / "__init__.py").read_text(encoding="utf-8")
    text = RELEASE_DOC.read_text(encoding="utf-8")

    assert version == "0.1.0a1"
    assert f'__version__ = "{version}"' in init_text
    assert f"git tag -a v{version} -m \"v{version}\"" in text
    assert f"git push origin v{version}" in text


def test_workflows_use_current_action_majors() -> None:
    ci = CI_WORKFLOW.read_text(encoding="utf-8")
    release = RELEASE_WORKFLOW.read_text(encoding="utf-8")
    combined = f"{ci}\n{release}"

    assert "actions/checkout@v7" in combined
    assert "actions/setup-python@v6" in combined
    assert "actions/upload-artifact@v7" in release
    assert "actions/download-artifact@v8" in release
    assert "actions/checkout@v4" not in combined
    assert "actions/setup-python@v5" not in combined
    assert "actions/upload-artifact@v4" not in combined
    assert "actions/download-artifact@v4" not in combined


def test_release_workflow_verifies_built_wheel_before_release() -> None:
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "python -m build" in text
    assert "dist/vaultwright-*.whl" in text
    assert "vaultwright-release-venv" in text
    assert "vaultwright\" init" in text
    assert "test -f \"$tmp_vault/tools/catalog_report.py\"" in text
    assert "test -f \"$tmp_vault/tools/m365_report.py\"" in text
    assert "test -f \"$tmp_vault/tools/overlap_report.py\"" in text
    assert "test -f \"$tmp_vault/tools/review_ledger.py\"" in text
    assert "catalog --check" in text
    assert "catalog --html --check" in text
    assert "test -f \"$tmp_vault/tools/sandbox_report.py\"" in text
    assert "sandbox --source-root" in text
    assert "conversion --guide --json" in text
    assert "conversion --init-results" in text
    assert "conversion --results _meta/conversion-quality-results.yml --require-reviewed --json" in text
    assert "release-smoke-source" in text
    assert "agent-readiness-results.yml" in text
    assert "--require-prompt-safety" in text
    assert "overlap --json" in text
    assert "overlap --worksheet" in text
    assert "m365 --json" in text
    assert "review --artifact CATALOG.html --status approved --reviewer Release --json" in text
    assert "review --check" in text
    assert "migration --worksheet" in text
    assert "migration --runbook" in text
    assert "migration --normalize-frontmatter-domains --worksheet" in text
    assert "pilot --worksheet" in text
    assert "recovery --worksheet" in text
    assert "actions/upload-artifact@v7" in text


def test_ci_workflow_smokes_sandbox_command() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "src/vaultwright/catalog.py" in text
    assert "template/tools/catalog_report.py" in text
    assert "template/tools/m365_report.py" in text
    assert "template/tools/overlap_report.py" in text
    assert "template/tools/review_ledger.py" in text
    assert "test -f \"$tmp_vault/tools/catalog_report.py\"" in text
    assert "test -f \"$tmp_vault/tools/m365_report.py\"" in text
    assert "test -f \"$tmp_vault/tools/overlap_report.py\"" in text
    assert "test -f \"$tmp_vault/tools/review_ledger.py\"" in text
    assert "catalog --check" in text
    assert "catalog --html --check" in text
    assert "template/tools/sandbox_report.py" in text
    assert "test -f \"$tmp_vault/tools/sandbox_report.py\"" in text
    assert "sandbox --source-root" in text
    assert "conversion --init-results" in text
    assert "conversion --results _meta/conversion-quality-results.yml --require-reviewed --json" in text
    assert "release-smoke-source" in text
    assert "agent-readiness-results.yml" in text
    assert "--require-prompt-safety" in text
    assert "migration --worksheet" in text
    assert "migration --runbook" in text
    assert "migration --normalize-frontmatter-domains --worksheet" in text
    assert "overlap --json" in text
    assert "overlap --worksheet" in text
    assert "m365 --json" in text
    assert "review --artifact CATALOG.html --status approved --reviewer CI --json" in text
    assert "review --check" in text
    assert "recovery --worksheet" in text


def test_release_workflow_isolates_write_token_to_publish_job() -> None:
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "persist-credentials: false" in text
    assert "publish-draft:" in text
    assert "needs: build-release" in text
    assert "actions/download-artifact@v8" in text
    assert "contents: read" in text
    assert "contents: write" in text
    assert text.index("contents: write") > text.index("publish-draft:")
    assert text.index("GH_TOKEN: ${{ github.token }}") > text.index("publish-draft:")
    assert text.index("GH_REPO: ${{ github.repository }}") > text.index("publish-draft:")


def test_release_workflow_refuses_to_mutate_published_release() -> None:
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "--json isDraft,isPrerelease" in text
    assert "not both draft and prerelease" in text
    assert "refusing to clobber assets" in text
    assert "gh release upload" in text
    assert "--clobber" in text


def test_release_workflow_does_not_publish_to_pypi() -> None:
    text = RELEASE_WORKFLOW.read_text(encoding="utf-8").lower()

    forbidden = [
        "pypi",
        "twine upload",
        "__token__",
        "id-token: write",
        "trusted publishing",
    ]
    assert not any(value in text for value in forbidden)


def test_release_checklist_documents_owner_review_and_limitations() -> None:
    text = RELEASE_DOC.read_text(encoding="utf-8")

    assert "draft, prerelease GitHub Release" in text
    assert "owner should publish it only after reviewing" in text
    assert "This repository does not publish to PyPI yet." in text
    assert "`sandbox`" in text
    assert "conversion quality" in text
    assert "conversion-quality result packs" in text
    assert "external pilot evidence" in text
