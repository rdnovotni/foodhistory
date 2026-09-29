import os

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import make_conninfo

from app.auth import hash_password
from app.db import Database
from app.main import create_app
from app.repository import Repository
from app.wiki_repository import WikiRepository

pytestmark = pytest.mark.integration


@pytest.fixture
def repository():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is not set")
    return Repository(Database(database_url))


def test_seeded_taxonomy_is_visible(repository):
    vocabularies = repository.list_vocabularies()
    assert len(vocabularies) == 10
    assert sum(item["term_count"] for item in vocabularies) == 1392


def test_catalogue_queries_are_valid(repository):
    page = repository.list_entities(limit=5)
    assert set(page) == {"items", "next_cursor"}
    search = repository.search("synthetic", limit=5)
    assert set(search) == {"items", "facets", "next_cursor"}


def test_synthetic_menu_read_model_and_search(repository):
    page = repository.list_entities(q="Railroad Dining Car Dinner", limit=10)
    menu_summary = next(
        item for item in page["items"] if item["preferred_label"].startswith("Example Railroad")
    )

    menu = repository.get_menu(menu_summary["public_id"])
    assert menu is not None
    assert menu["service_date"] == "1956-06-15"
    assert [section["heading_original"] for section in menu["sections"]] == [
        "SOUPS",
        "ENTREES",
        "DESSERTS",
    ]
    assert menu["sections"][2]["items"][0]["printed_name"] == "Apple Pie"

    results = repository.search("Apple pie", limit=10)
    assert any(item["entity"]["label"] == "Apple pie" for item in results["items"])


def test_synthetic_bibliographic_work_tree(repository):
    page = repository.list_entities(q="Practical Kitchen Ledger", type_code="ENT.WORK")
    assert len(page["items"]) == 1

    tree = repository.get_work(page["items"][0]["public_id"])
    assert tree is not None
    assert tree["work"]["work_type"]["code"] == "ROT.DOC.BOOK.COOK"
    assert len(tree["expressions"]) == 1
    assert len(tree["manifestations"]) == 1
    assert tree["manifestations"][0]["publication_date"] == "1912"
    assert tree["items"][0]["copy_number"] == "Fixture copy 1"


def test_synthetic_material_culture_object(repository):
    page = repository.list_entities(q="embossed soda bottle", type_code="ENT.OBJ")
    assert len(page["items"]) == 1

    record = repository.get_object(page["items"][0]["public_id"])
    assert record is not None
    assert record["object_type"]["code"] == "ROT.OBJ.PACK.BOTTLE"
    assert record["manufacture_date"] == "1938~"
    assert len(record["measurements"]) == 2
    assert len(record["marks"]) == 2
    assert record["current_holding"]["accession_number"] == "TEST-OBJ-0001"
    assert len(record["images"]) == 2


def test_real_http_application_smoke():
    with TestClient(create_app()) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/").status_code == 200
        response = client.get("/v1/search", params={"q": "Apple pie"})
        assert response.status_code == 200
        assert response.json()["items"]


def test_wiki_schema_and_public_database_role_are_read_only():
    database_url = os.getenv("DATABASE_URL")
    public_user = os.getenv("PUBLIC_DATABASE_USER")
    public_password = os.getenv("PUBLIC_DATABASE_PASSWORD")
    if not database_url or not public_user or not public_password:
        pytest.skip("Public reader integration settings are not set")
    reader_url = make_conninfo(
        database_url, user=public_user, password=public_password
    )
    with psycopg.connect(reader_url) as connection:
        connection.execute("SET search_path TO food_history, public")
        assert connection.execute("SELECT count(*) FROM public_wiki_page").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM public_wiki_category").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM public_wiki_revision_link").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM public_wiki_publication").fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM public_wiki_revision_template").fetchone()[0] == 0
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("SELECT * FROM wiki_revision_image")
    with psycopg.connect(reader_url) as connection:
        connection.execute("SET search_path TO food_history, public")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("SELECT * FROM wiki_revision_link")
    with psycopg.connect(reader_url) as connection:
        connection.execute("SET search_path TO food_history, public")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("SELECT * FROM wiki_publication")
    with psycopg.connect(reader_url) as connection:
        connection.execute("SET search_path TO food_history, public")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("SELECT * FROM wiki_article_template")
    with psycopg.connect(reader_url) as connection:
        connection.execute("SET search_path TO food_history, public")
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("SELECT * FROM wiki_revision_template")
    with psycopg.connect(reader_url) as connection:
        connection.execute("SET search_path TO food_history, public")
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            connection.execute(
                "INSERT INTO schema_version (version, description) VALUES ('forbidden', 'test')"
            )


def test_wiki_revision_category_review_and_publication_workflow(repository):
    wiki = WikiRepository(repository.db)
    account_id = wiki.create_account(
        "integration-owner",
        "Integration Owner",
        hash_password("integration test password"),
        "owner",
    )
    entity = repository.list_entities(limit=1)["items"][0]
    page_id = wiki.create_page(
        slug="integration-article",
        title="Integration article",
        summary="A workflow fixture.",
        body_markdown="# First revision",
        change_note="Initial draft",
        user_id=account_id,
        entity_public_ids=[entity["public_id"]],
        citation_ids=[],
        category_names=["Methods"],
        images=[],
        template_key="dish", template_version=1,
    )
    wiki.add_revision(
        page_id,
        title="Integration article",
        summary="A workflow fixture.",
        body_markdown="# Second revision",
        change_note="Clarified heading",
        user_id=account_id,
        entity_public_ids=[entity["public_id"]],
        citation_ids=[],
        category_names=["Methods"],
        images=[],
    )
    assert len(wiki.list_revisions(page_id)) == 2
    wiki.review(page_id, "submitted", "Ready", account_id)
    wiki.review(page_id, "approved", "Approved", account_id)
    wiki.publish(page_id)
    published = wiki.get_published("integration-article")
    assert published["revision_number"] == 2
    assert published["categories"][0]["name"] == "Methods"
    assert published["template"]["template_key"] == "dish"
    assert wiki.list_published(q="Second")[0]["slug"] == "integration-article"
    source_id = wiki.create_page(
        slug="integration-link-source", title="Link source", summary="A link fixture.",
        body_markdown="See [[integration-article]].", change_note="Link", user_id=account_id,
        entity_public_ids=[], citation_ids=[], category_names=[], images=[],
    )
    assert wiki.backlinks("integration-article") == []
    wiki.review(source_id, "submitted", "Ready", account_id)
    wiki.review(source_id, "approved", "Approved", account_id)
    wiki.publish(source_id)
    backlink = wiki.backlinks("integration-article")[0]
    assert backlink["slug"] == "integration-link-source"
    assert backlink["public_id"].startswith("FH-WIKI-")
    wiki.create_series("integration-series", "Integration series", "A test collection")
    wiki.add_revision(
        page_id, title="Integration article", summary="Improved history.",
        body_markdown="## Later history\n\nSee [[integration-link-source]].",
        change_note="Expanded", user_id=account_id, entity_public_ids=[], citation_ids=[],
        category_names=["Methods"], images=[], series_slug="integration-series",
        series_position=1, related_slugs=["integration-link-source"],
        event_month=9, event_day=28,
    )
    wiki.review(page_id, "submitted", "Ready", account_id)
    wiki.review(page_id, "approved", "Approved", account_id)
    wiki.publish(page_id)
    assert len(wiki.published_revisions("integration-article")) == 2
    assert wiki.published_revision("integration-article", 2)["title"] == "Integration article"
    assert wiki.published_revision("integration-article", 1) is None
    assert wiki.series_navigation(wiki.db.fetch_one(
        "SELECT revision_id FROM public_wiki_page WHERE slug = %s", ("integration-article",)
    )["revision_id"])[0]["slug"] == "integration-series"
    assert wiki.on_this_day(9, 28)[0]["slug"] == "integration-article"
    assert wiki.recent_pages(improved=True)[0]["slug"] == "integration-article"
    related = wiki.get_published("integration-article")["related"][0]
    assert related["slug"] == "integration-link-source"
    assert related["public_id"].startswith("FH-WIKI-")
    wiki.add_redirect(page_id, "integration-article-old", account_id)
    assert wiki.get_published("integration-article-old")["redirect_slug"] == "integration-article"
    wiki.save_glossary("corn-term", "Corn term", "A test definition.",
                       "integration-article", True)
    assert wiki.glossary_terms(["corn-term"])["corn-term"]["term"] == "Corn term"
    version = wiki.create_template_version(
        "dish", "dish", "Dish article", "Updated test scaffold",
        "## Overview\n\n## Evidence", "## Evidence",
    )
    assert version == 2
    assert wiki.get_article_template("dish")["version"] == 2
