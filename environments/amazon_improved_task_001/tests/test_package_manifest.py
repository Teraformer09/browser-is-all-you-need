from pathlib import Path

import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_wheel_bootstrap_does_not_require_repository_only_documentation():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    forced = project["tool"]["hatch"]["build"]["targets"]["wheel"]["force-include"]

    assert "IMPLEMENTATION_LOG.md" not in forced
    assert "README.md" in forced
    assert "scripts/provision_android.sh" in forced


def test_project_and_runtime_versions_match():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())
    namespace = {}
    exec((ROOT / "amazon_improved_task_001" / "__init__.py").read_text(), namespace)

    assert project["project"]["version"] == "0.1.2"
    assert namespace["VERSION"] == project["project"]["version"]
