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


def test_production_compose_is_private_by_default_and_examples_are_disabled():
    compose = yaml.safe_load(
        (ROOT / "compose.production.yaml").read_text(encoding="utf-8")
    )
    services = compose["services"]

    assert "ports" not in services["db"]
    assert services["db"]["restart"] == "unless-stopped"
    assert compose["networks"]["backend"]["internal"] is True
    assert services["setup"]["command"] == ["python", "tools/bootstrap_db.py"]
    assert "LOAD_EXAMPLES" not in services["setup"]["environment"]
    assert services["web"]["ports"] == ["127.0.0.1:8000:8000"]
    assert services["web"]["read_only"] is True
    assert services["web"]["restart"] == "unless-stopped"
    assert services["web"]["environment"]["APP_MODE"] == "editorial"
    assert services["public_web"]["profiles"] == ["public"]
    assert services["public_web"]["environment"]["APP_MODE"] == "public"
    assert "PUBLIC_DATABASE_USER" in services["public_web"]["environment"]["DATABASE_URL"]
    assert "POSTGRES_USER" in services["web"]["environment"]["DATABASE_URL"]
    assert "edge" not in services["web"]["networks"]
    assert "edge" in services["public_web"]["networks"]
    assert services["caddy"]["profiles"] == ["public"]
    assert services["caddy"]["ports"] == ["80:80", "443:443", "443:443/udp"]
    public_bindings = {
        name for name, service in services.items() if service.get("ports")
    }
    assert public_bindings == {"web", "caddy"}
    assert all(
        str(binding).startswith("127.0.0.1:") for binding in services["web"]["ports"]
    )


def test_public_proxy_enforces_https_security_headers():
    caddyfile = (ROOT / "ops" / "Caddyfile").read_text(encoding="utf-8")

    assert "{$PUBLIC_HOST}" in caddyfile
    assert "reverse_proxy public_web:8000" in caddyfile
    assert "reverse_proxy web:8000" not in caddyfile
    assert "Strict-Transport-Security" in caddyfile
    assert "X-Content-Type-Options" in caddyfile
