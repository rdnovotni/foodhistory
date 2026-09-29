from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image

from app.auth import digest_secret, hash_password, verify_password
from app.config import Settings
from app.main import create_app, get_repository
from app.wiki_render import glossary_slugs, render_article, render_markdown, wiki_link_slugs
from app.wiki_routes import get_wiki_repository
from app.wiki_structures import structure_references
from tests.test_app import FakeRepository


class FakeWikiRepository:
    def __init__(self):
        self.account_id = uuid4()
        self.password_hash = hash_password("a sufficiently long password")
        self.sessions = {}
        self.created = None
        self.registered_media = None

    def list_published(self, q=None, category=None):
        if q == "missing" or category == "missing":
            return []
        return [{"public_id": "FH-WIKI-TEST", "slug": "apple-pie", "title": "Apple pie", "summary": "History."}]

    def list_public_categories(self):
        return [{"slug": "desserts", "name": "Desserts", "description": None, "page_count": 1}]

    def list_editor_categories(self):
        return self.list_public_categories()

    def list_series(self):
        return []

    def list_article_templates(self):
        return [{"template_key": "dish", "version": 1, "article_type": "dish",
                 "title": "Dish article", "description": "Dish structure"}]

    def get_article_template(self, key, version=None):
        return {"template_key": key, "version": version or 1, "article_type": key,
                "title": "Dish article", "description": "Dish structure",
                "body_markdown": "## Overview", "migration_markdown": ""} if key == "dish" else None

    def list_template_versions(self):
        return [{**self.list_article_templates()[0], "is_current": True, "created_at": "now",
                 "migration_markdown": ""}]

    def create_template_version(self, key, article_type, title, description, body_markdown,
                                migration_markdown):
        self.created_template = (key, article_type, title, description, body_markdown,
                                 migration_markdown)
        return 2

    def structured_block_data(self, references):
        return {}

    def create_series(self, slug, title, description):
        self.created_series = (slug, title, description)

    def list_glossary(self):
        return []

    def save_glossary(self, slug, term, definition, article_slug, is_published):
        self.saved_term = (slug, term, definition, article_slug, is_published)

    def add_redirect(self, page_id, slug, account_id):
        self.redirect = slug

    def delete_redirect(self, page_id, slug):
        self.deleted_redirect = slug

    def recent_pages(self, improved=False):
        return []

    def on_this_day(self, month, day):
        return []

    def glossary_terms(self, slugs):
        return {}

    def random_page(self):
        return {"slug": "apple-pie"}

    def published_revisions(self, slug):
        return [{"revision_number": 2, "title": "Apple pie", "published_at": "now", "is_current": True}]

    def published_revision(self, slug, number):
        return {"slug": slug, "revision_number": number, "title": "Apple pie",
                "summary": "History.", "body_markdown": "## Origins\n\nA researched article.",
                "published_at": "now"} if number == 2 and slug == "apple-pie" else None

    def page_information(self, slug):
        return {"slug": slug, "title": "Apple pie", "public_id": "FH-WIKI-TEST",
                "revision_created_at": "now", "first_published_at": "now",
                "revision_count": 1, "backlink_count": 1, "redirects": []} if slug == "apple-pie" else None

    def public_series(self, slug):
        return None

    def search_wiki_pages(self, q):
        return [{"slug": "apple-pie", "title": "Apple pie"}]

    def public_link_targets(self, slugs):
        return {slug: {"slug": slug, "title": "Apple pie"} for slug in slugs if slug == "apple-pie"}

    def backlinks(self, slug):
        return [{"slug": "pie-history", "title": "Pie history", "summary": "Background."}]

    def get_published(self, slug):
        if slug != "apple-pie":
            return None
        return {
            "public_id": "FH-WIKI-TEST", "slug": slug, "revision_number": 2,
            "title": "Apple pie", "summary": "History.",
            "body_markdown": "## Origins\n\nA researched article.",
            "entities": [], "citations": [], "categories": [], "images": [],
            "series": [], "related": [], "metadata": {"is_disambiguation": False},
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

    def get_editor_page(self, page_id):
        return {
            "page_id": page_id, "title": "Apple pie", "status": "draft",
            "revision_number": 2, "summary": "History.", "body_markdown": "New text",
            "entity_public_ids": [], "citation_ids": [], "category_names": [],
            "images": [], "reviews": [],
            "metadata": {"is_disambiguation": False, "event_month": None, "event_day": None},
            "series_membership": None, "related_slugs": [], "redirects": [],
        }

    def list_revisions(self, page_id):
        return [
            {"revision_number": 2, "title": "Apple pie", "summary": None, "change_note": "Rewrite", "created_at": "now", "author": "Test Editor", "is_published": False},
            {"revision_number": 1, "title": "Apple pie", "summary": None, "change_note": "Start", "created_at": "before", "author": "Test Editor", "is_published": True},
        ]

    def get_revision(self, page_id, number):
        return {"revision_number": number, "body_markdown": "New text" if number == 2 else "Old text"}

    def create_page(self, **values):
        self.created = values
        return "13a98a58-2c65-4ad8-86c6-31bd95c2ee13"

    def search_entities(self, q):
        return [{"public_id": "FH-TEST", "label": "Apple pie", "type_code": "ENT.CUL.FOOD"}]

    def search_citations(self, q):
        return [{"citation_id": str(uuid4()), "source_label": "Test source", "locator_text": "p. 1"}]

    def search_media(self, q):
        return []

    def register_media(self, **values):
        self.registered_media = values
        return {"public_id": "FH-DIG-TEST", "label": values["original_filename"], "storage_uri": values["storage_uri"]}


def make_client(mode="public", media_root="var/media"):
    wiki = FakeWikiRepository()
    app = create_app(Settings(database_url="unused", app_mode=mode, editor_cookie_secure=False, media_root=str(media_root)))
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


def test_outline_and_links_ignore_code_and_existing_links():
    source = ("## Origins & [[apple-pie|names]]\n\n[[apple-pie]] and [[apple-pie|<Pie>]]; "
              "[[draft-page]] and `[[code-page]]` and [normal](https://example.org).\n\n"
              "```\n[[fenced-page]]\n```\n\n### Origins & names\n\n## Origins & names")
    assert wiki_link_slugs(source) == ["apple-pie", "draft-page"]
    result = render_article(source, {"apple-pie": {"slug": "apple-pie", "title": "Apple pie"}})
    assert [item["id"] for item in result["toc"]] == [
        "origins-names", "origins-names-2", "origins-names-3",
    ]
    assert result["toc"][0]["title"] == "Origins & names"
    assert 'href="/wiki/apple-pie"' in result["body_html"]
    assert "&lt;Pie&gt;" in result["body_html"]
    assert 'class="wiki-missing"' in result["body_html"]
    assert 'href="/wiki/draft-page"' not in result["body_html"]
    assert 'id="origins-names-2"' in result["body_html"]


def test_glossary_and_footnotes_are_safe_and_previewable():
    source = "A {{sagamite}}[^1] and `{{code}}`.\n\n[^1]: See [[apple-pie]]."
    assert glossary_slugs(source) == ["sagamite"]
    result = render_article(source, {"apple-pie": {"slug": "apple-pie", "title": "Apple pie"}},
                            {"sagamite": {"term": "Sagamité", "definition": "A corn dish <script>",
                                           "article_slug": "apple-pie"}})
    assert 'class="glossary-term"' in result["body_html"]
    assert 'data-definition="A corn dish &lt;script&gt;"' in result["body_html"]
    assert 'href="#fn1"' in result["body_html"]
    assert 'id="fn1"' in result["body_html"]


def test_structured_blocks_render_controlled_markup_and_collect_references():
    source = '''```fh-infobox
{"public_id":"FH-FOOD-1"}
```
```fh-notice
{"title":"Research note","tone":"research","text":"<script>Not executable</script>"}
```
```fh-source-excerpt
{"citation_id":"00000000-0000-0000-0000-000000000001"}
```
```fh-gallery
{"public_ids":["FH-DIG-1"]}
```'''
    references = structure_references(source)
    assert references["entities"] == ["FH-FOOD-1"]
    assert references["citations"] == ["00000000-0000-0000-0000-000000000001"]
    assert references["media"] == ["FH-DIG-1"]
    result = render_article(source, structures={
        "entities": {"FH-FOOD-1": {"public_id": "FH-FOOD-1", "label": "Apple pie",
                                      "type_label": "Dish"}},
        "citations": {}, "media": {"FH-DIG-1": {"uri": "/media/pie.jpg", "label": "Pie"}},
    })
    assert "Canonical record" in result["body_html"]
    assert "Research note" in result["body_html"]
    assert "&lt;script&gt;Not executable&lt;/script&gt;" in result["body_html"]
    assert '<img src="/media/pie.jpg" alt="Pie">' in result["body_html"]


def test_public_wiki_reads_only_published_content():
    client, _ = make_client()
    assert "Apple pie" in client.get("/wiki").text
    response = client.get("/v1/wiki/pages/apple-pie")
    assert response.status_code == 200
    assert '<h2 id="origins">Origins</h2>' in response.json()["body_html"]
    assert client.get("/v1/wiki/pages/missing").status_code == 404
    assert "A researched article" in client.get("/wiki/apple-pie").text
    assert 'href="#origins"' in client.get("/wiki/apple-pie").text
    assert "What links here" in client.get("/wiki/apple-pie").text
    assert "min read" in client.get("/wiki/apple-pie").text
    assert client.get("/wiki/random", follow_redirects=False).headers["location"] == "/wiki/apple-pie"
    assert client.get("/wiki/apple-pie/history").status_code == 200
    assert client.get("/wiki/apple-pie/revisions/2").status_code == 200
    assert client.get("/wiki/apple-pie/revisions/1").status_code == 404
    assert "Stable ID" in client.get("/wiki/apple-pie/information").text
    assert "Exit focus view" in client.get("/wiki/apple-pie?view=focus").text
    assert client.get("/v1/wiki/pages/apple-pie/preview").json()["reading_minutes"] == 1
    assert "Desserts" in client.get("/wiki/categories").text
    assert "Apple pie" in client.get("/wiki/category/desserts").text


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
    template_page = client.get("/editor/pages/new", params={"template": "dish"})
    assert "## Overview" in template_page.text
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
            "template_key": "dish", "template_version": "1",
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    assert wiki.created["entity_public_ids"] == ["FH-TEST"]
    assert wiki.created["category_names"] == []
    assert wiki.created["is_disambiguation"] is False
    assert wiki.created["template_key"] == "dish"
    assert wiki.created["template_version"] == 1
    with_empty_optional_numbers = client.post(
        "/editor/pages", data={"csrf_token": csrf, "slug": "second-page", "title": "Second page",
                               "body_markdown": "Text", "series_position": "", "event_month": "",
                               "event_day": ""}, follow_redirects=False,
    )
    assert with_empty_optional_numbers.status_code == 303


def test_editor_can_manage_series_glossary_and_redirects():
    client, wiki = make_client("editorial")
    client.post("/editor/login", data={"username": "editor", "password": "a sufficiently long password"})
    csrf = client.cookies.get("fh_editor_csrf")
    assert "Article series" in client.get("/editor/series").text
    assert client.post("/editor/series", data={"csrf_token": csrf, "slug": "early-foods",
                                                  "title": "Early foods"}).status_code == 200
    assert wiki.created_series[:2] == ("early-foods", "Early foods")
    assert client.post("/editor/glossary", data={"csrf_token": csrf, "slug": "sagamite",
                    "term": "Sagamité", "definition": "A corn preparation.", "is_published": "true"}).status_code == 200
    assert wiki.saved_term[-1] is True
    assert "Version history" in client.get("/editor/templates").text
    response = client.post("/editor/templates", data={
        "csrf_token": csrf, "key": "dish", "article_type": "dish",
        "title": "Dish article", "body_markdown": "## Overview",
        "migration_markdown": "## New section",
    }, follow_redirects=False)
    assert response.status_code == 303
    assert wiki.created_template[0:3] == ("dish", "dish", "Dish article")
    client.post("/editor/pages/test/redirects", data={"csrf_token": csrf, "slug": "old-pie"})
    assert wiki.redirect == "old-pie"


def test_editor_picker_and_validated_image_upload(tmp_path):
    client, wiki = make_client("editorial", tmp_path)
    client.post(
        "/editor/login",
        data={"username": "editor", "password": "a sufficiently long password"},
    )
    assert client.get("/editor/pickers/entities", params={"q": "apple"}).json()[0]["public_id"] == "FH-TEST"
    assert client.get("/editor/pickers/wiki", params={"q": "apple"}).json()[0]["slug"] == "apple-pie"
    assert "Related catalogue records" in client.get("/editor/pages/new").text
    assert "Revision 1" in client.get("/editor/pages/test/history").text
    buffer = BytesIO()
    Image.new("RGB", (4, 3), "red").save(buffer, format="PNG")
    response = client.post(
        "/editor/media",
        data={"csrf_token": client.cookies.get("fh_editor_csrf")},
        files={"upload": ("test.png", buffer.getvalue(), "image/png")},
    )
    assert response.status_code == 200
    assert wiki.registered_media["width_px"] == 4
    assert (tmp_path / wiki.registered_media["sha256"] / "asset.png").is_file()
