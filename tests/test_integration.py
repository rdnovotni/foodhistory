import os

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import make_conninfo

from app.db import Database
from app.main import create_app
from app.repository import Repository

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
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            connection.execute("SELECT * FROM editor_account")
    with psycopg.connect(reader_url) as connection:
        connection.execute("SET search_path TO food_history, public")
        with pytest.raises(psycopg.errors.ReadOnlySqlTransaction):
            connection.execute(
                "INSERT INTO schema_version (version, description) VALUES ('forbidden', 'test')"
            )
