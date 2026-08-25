from pathlib import Path


ROOT = Path(__file__).parents[3]


def test_frozen_python_distribution_cannot_publish_again() -> None:
    assert not (ROOT / ".github/workflows/release.yml").exists()
    assert not (ROOT / ".github/workflows/prepare-stable-tag.yml").exists()


def test_project_metadata_and_readme_name_rust_as_canonical() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert 'Development Status :: 7 - Inactive' in pyproject
    assert "Frozen legacy Python distribution" in pyproject
    assert "canonical Rust microservice crate platform" in readme
    assert "no later Python distribution" in readme


def test_existing_rollback_version_remains_consistent() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    package = (ROOT / "mmf/__init__.py").read_text(encoding="utf-8")

    assert 'version = "1.0.2"' in pyproject
    assert '__version__ = "1.0.2"' in package
