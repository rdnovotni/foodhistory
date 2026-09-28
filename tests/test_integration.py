import os

import pytest
from fastapi.testclient import TestClient

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


def test_real_http_application_smoke():
    with TestClient(create_app()) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert client.get("/").status_code == 200
        response = client.get("/v1/search", params={"q": "Apple pie"})
        assert response.status_code == 200
        assert response.json()["items"]
