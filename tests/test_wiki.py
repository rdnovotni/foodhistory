from uuid import uuid4

from fastapi.testclient import TestClient

from app.auth import digest_secret, hash_password, verify_password
from app.config import Settings
from app.main import create_app, get_repository
from app.wiki_render import render_markdown
from app.wiki_routes import get_wiki_repository
from tests.test_app import FakeRepository


class FakeWikiRepository:
    def __init__(self):
        self.account_id = uuid4()
        self.password_hash = hash_password("a sufficiently long password")
        self.sessions = {}
        self.created = None

    def list_published(self):
        return [{"public_id": "FH-WIKI-TEST", "slug": "apple-pie", "title": "Apple pie", "summary": "History."}]

    def get_published(self, slug):
        if slug != "apple-pie":
            return None
        return {
            "public_id": "FH-WIKI-TEST", "slug": slug, "revision_number": 2,
            "title": "Apple pie", "summary": "History.",
            "body_markdown": "## Origins\n\nA researched article.",
            "entities": [], "citations": [],
        }

    def authenticate(self, username, password):
        if username != "editor" or not verify_password(password, self.password_hash):
            return None
        return {"account_id": self.account_id, "username": username, "role": "owner", "display_name": "Test Editor"}

    def create_session(self, account_id, token, csrf_token, hours):
        self.sessions[digest_secret(token)] = {
            "account_id": account_id, "username": "editor", "role": "owner",
            "display_name": "Test Editor", "csrf_token_hash": digest_secret(csrf_token),
        }

    def get_session(self, token):
        return self.sessions.get(digest_secret(token))

    def delete_session(self, token):
        self.sessions.pop(digest_secret(token), None)

    def list_editor_pages(self):
        return []

    def create_page(self, **values):
        self.created = values
        return "13a98a58-2c65-4ad8-86c6-31bd95c2ee13"


def make_client(mode="public"):
    wiki = FakeWikiRepository()
    app = create_app(Settings(database_url="unused", app_mode=mode, editor_cookie_secure=False))
    app.dependency_overrides[get_repository] = lambda: FakeRepository()
    app.dependency_overrides[get_wiki_repository] = lambda: wiki
    return TestClient(app), wiki


def test_password_hashing_and_markdown_sanitizing():
    encoded = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)
    html = render_markdown("# Safe\n\n<script>alert(1)</script> [bad](javascript:alert(1))")
    assert "<h1>Safe</h1>" in html
    assert "<script" not in html
    assert 'href="javascript:' not in html


def test_public_wiki_reads_only_published_content():
    client, _ = make_client()
    assert "Apple pie" in client.get("/wiki").text
    response = client.get("/v1/wiki/pages/apple-pie")
    assert response.status_code == 200
    assert "<h2>Origins</h2>" in response.json()["body_html"]
    assert client.get("/v1/wiki/pages/missing").status_code == 404


def test_public_mode_does_not_register_editor_routes():
    client, _ = make_client("public")
    assert client.get("/editor/login").status_code == 404
    assert "/editor/login" not in client.get("/api/openapi.json").json()["paths"]


def test_editor_can_sign_in_and_create_draft_with_csrf_protection():
    client, wiki = make_client("editorial")
    failed = client.post("/editor/login", data={"username": "editor", "password": "incorrect"})
    assert failed.status_code == 401
    signed_in = client.post(
        "/editor/login",
        data={"username": "editor", "password": "a sufficiently long password"},
        follow_redirects=False,
    )
    assert signed_in.status_code == 303
    csrf = client.cookies.get("fh_editor_csrf")
    rejected = client.post(
        "/editor/pages",
        data={"csrf_token": "wrong", "slug": "apple-pie", "title": "Apple pie", "body_markdown": "Text"},
    )
    assert rejected.status_code == 403
    created = client.post(
        "/editor/pages",
        data={
            "csrf_token": csrf, "slug": "apple-pie", "title": "Apple pie",
            "body_markdown": "Text", "entity_public_ids": "FH-TEST",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    assert wiki.created["entity_public_ids"] == ["FH-TEST"]
