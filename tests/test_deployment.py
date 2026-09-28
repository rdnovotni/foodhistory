from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_render_blueprint_uses_private_postgres_and_release_migrations():
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    service = blueprint["services"][0]
    database = blueprint["databases"][0]

    assert service["runtime"] == "docker"
    assert service["plan"] == "free"
    assert service["healthCheckPath"] == "/health"
    assert service["preDeployCommand"] == "python tools/bootstrap_db.py"
    assert service["envVars"][0]["fromDatabase"]["name"] == database["name"]
    assert database["postgresMajorVersion"] == "16"
    assert database["plan"] == "free"
    assert database["ipAllowList"] == []
