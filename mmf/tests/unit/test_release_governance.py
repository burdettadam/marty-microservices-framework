from pathlib import Path


ROOT = Path(__file__).parents[3]
RELEASE = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
PREPARE = (ROOT / ".github" / "workflows" / "prepare-stable-tag.yml").read_text(
    encoding="utf-8"
)


def test_stable_tag_is_an_exact_main_one_time_handoff() -> None:
    assert "test \"$RUN_REF\" = refs/heads/main" in PREPARE
    assert "test \"$RUN_SHA\" = \"$EXPECTED_SHA\"" in PREPARE
    assert "git ls-remote --tags" in PREPARE
    assert "git tag -a" in PREPARE
    assert "Stable-Tag-Gate: elevenid.stable-tag-preparation/v1" in PREPARE
    assert "git push origin \"refs/tags/$TAG:refs/tags/$TAG\"" in PREPARE
    assert "actions: write" in PREPARE
    assert 'gh workflow run release.yml --ref "$TAG" -f "tag=$TAG"' in PREPARE
    assert "event=workflow_dispatch" in PREPARE
    assert "Stable-tag preparation did not reach a terminal state" in RELEASE
    for workflow in (
        ".github/workflows/ci.yml:push",
        ".github/workflows/open-source-policy.yml:push",
        ".github/workflows/organization-quality.yml:push",
        ".github/workflows/license-compliance.yml:push",
        ".github/workflows/codeql.yml:push",
    ):
        assert workflow in PREPARE


def test_release_fails_closed_instead_of_updating_existing_assets() -> None:
    assert "upload-release-assets: false" in RELEASE
    assert "upload-artifact: false" in RELEASE
    assert "softprops/action-gh-release" not in RELEASE
    assert "gh release create \"$TAG\"" in RELEASE
    assert "--verify-tag" in RELEASE
    assert "gh release view \"$TAG\"" in RELEASE
    assert "--clobber" not in RELEASE
    assert "sigstore/cosign-installer@" in RELEASE
    assert "cosign sign-blob --yes --bundle" in RELEASE
    assert "SHA256SUMS" in RELEASE
    assert "actions/attest-build-provenance@" in RELEASE


def test_public_registry_waits_for_verified_immutable_release() -> None:
    assert "needs: [build, github-release]" in RELEASE
    assert "jq -e '.draft == false and .immutable == true'" in RELEASE
    assert ".name == $name and .digest == $digest" in RELEASE


def test_package_and_release_versions_match() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    package = (ROOT / "mmf" / "__init__.py").read_text(encoding="utf-8")
    assert 'version = "1.0.2"' in pyproject
    assert '__version__ = "1.0.2"' in package


def test_release_dispatch_runs_from_the_exact_tag() -> None:
    assert "workflow_dispatch:" in RELEASE
    assert "TAG: ${{ inputs.tag || github.ref_name }}" in RELEASE
    assert 'test "$RUN_REF" = "refs/tags/$TAG"' in RELEASE


def test_exact_main_gates_run_on_main_push() -> None:
    workflows = {
        "ci.yml": 'branches: [ "main", "dev" ]',
        "open-source-policy.yml": "branches: [main, dev]",
        "organization-quality.yml": "branches: [main]",
        "license-compliance.yml": 'branches: [ "main", "dev" ]',
        "codeql.yml": "branches: [main]",
    }
    for filename, expected in workflows.items():
        text = (ROOT / ".github" / "workflows" / filename).read_text(encoding="utf-8")
        assert expected in text, filename
