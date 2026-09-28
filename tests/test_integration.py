import os

import pytest

from app.db import Database
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


def test_empty_catalogue_queries_are_valid(repository):
    page = repository.list_entities(limit=5)
    assert set(page) == {"items", "next_cursor"}
    search = repository.search("synthetic", limit=5)
    assert set(search) == {"items", "facets", "next_cursor"}
