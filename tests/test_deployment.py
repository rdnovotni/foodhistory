from pathlib import Path

import yaml

from tools import start_web

ROOT = Path(__file__).resolve().parents[1]


def test_render_blueprint_uses_private_postgres_and_release_migrations():
    blueprint = yaml.safe_load((ROOT / "render.yaml").read_text(encoding="utf-8"))
    service = blueprint["services"][0]
    database = blueprint["databases"][0]

    assert service["runtime"] == "docker"
    assert service["plan"] == "free"
    assert service["healthCheckPath"] == "/health"
    assert "preDeployCommand" not in service
    environment = {item["key"]: item for item in service["envVars"]}
    assert environment["RUN_DB_BOOTSTRAP"]["value"] == "true"
    assert environment["DATABASE_URL"]["fromDatabase"]["name"] == database["name"]
    assert database["postgresMajorVersion"] == "16"
    assert database["plan"] == "free"
    assert database["ipAllowList"] == []


def test_platform_launcher_sets_project_as_application_directory(monkeypatch):
    invocation = {}
    monkeypatch.delenv("RUN_DB_BOOTSTRAP", raising=False)
    monkeypatch.setattr(
        start_web.uvicorn,
        "run",
        lambda app, **options: invocation.update(app=app, **options),
    )

    start_web.main()

    assert invocation["app"] == "app.main:app"
    assert invocation["app_dir"] == str(ROOT)
