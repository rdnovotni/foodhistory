from fastapi.testclient import TestClient

from app.main import create_app, get_repository

ENTITY = {
    "public_id": "FH-TEST",
    "preferred_label": "Apple pie",
    "slug": "apple-pie",
    "type": {"code": "ENT.CUL.FOOD", "label": "Food or beverage"},
    "summary": "A synthetic test record.",
    "record_status": "published",
    "visibility": "public",
    "names": [],
    "identifiers": [],
    "terms": [],
    "primary_image": None,
}


class FakeDatabase:
    def ping(self):
        return True


class FakeRepository:
    db = FakeDatabase()

    def list_entities(self, **_kwargs):
        return {"items": [ENTITY], "next_cursor": None}

    def get_entity(self, public_id):
        return ENTITY if public_id == "FH-TEST" else None

    def get_assertions(self, public_id, predicate_code=None):
        return [] if public_id == "FH-TEST" else None

    def list_taxonomy_terms(self, vocabulary_code, parent_code=None, q=None):
        return [
            {
                "code": "FC.FOOD",
                "vocabulary_code": vocabulary_code,
                "preferred_label": "Food",
                "scope_note": None,
                "status": "approved",
            }
        ]

    def list_vocabularies(self):
        return [
            {
                "code": "FC",
                "name": "Food Concepts",
                "version": "1.1",
                "description": "Test",
                "term_count": 1,
            }
        ]

    def get_taxonomy_term(self, code):
        if code != "FC.FOOD":
            return None
        return {
            "code": code,
            "vocabulary_code": "FC",
            "preferred_label": "Food",
            "scope_note": None,
            "status": "approved",
            "broader": [],
            "narrower": [],
            "labels": [],
        }

    def get_menu(self, public_id):
        if public_id != "FH-MENU":
            return None
        return {
            **ENTITY,
            "public_id": public_id,
            "preferred_label": "Dinner menu",
            "menu_type": {"code": "ROT.DOC.MENU", "label": "Menu"},
            "establishment": None,
            "service_date": "1956-06-15",
            "currency_code": "USD",
            "sections": [],
            "images": [],
        }

    def get_menu_occurrences(self, public_id, **_kwargs):
        return {"items": [], "next_cursor": None} if public_id == "FH-TEST" else None

    def search(self, q, type_code=None, term_code=None, cursor=None, limit=25):
        return {
            "items": [
                {
                    "entity": {
                        "public_id": ENTITY["public_id"],
                        "label": ENTITY["preferred_label"],
                        "type": ENTITY["type"],
                    },
                    "score": 1.0,
                    "snippet": ENTITY["summary"],
                    "matched_fields": ["preferred_label"],
                }
            ],
            "facets": {"type_code": {"ENT.CUL.FOOD": 1}},
            "next_cursor": None,
        }


def client():
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: FakeRepository()
    return TestClient(app)


def test_health_and_openapi_are_available():
    test_client = client()
    assert test_client.get("/health").json()["status"] == "ok"
    paths = test_client.get("/api/openapi.json").json()["paths"]
    assert "/v1/entities" in paths
    assert "/v1/search" in paths


def test_entity_api_and_not_found():
    test_client = client()
    response = test_client.get("/v1/entities/FH-TEST")
    assert response.status_code == 200
    assert response.json()["preferred_label"] == "Apple pie"
    assert test_client.get("/v1/entities/missing").status_code == 404


def test_taxonomy_and_menu_api():
    test_client = client()
    assert test_client.get("/v1/taxonomy/FC/terms").json()[0]["code"] == "FC.FOOD"
    assert test_client.get("/v1/menus/FH-MENU").status_code == 200
    assert test_client.get("/v1/taxonomy/INVALID/terms").status_code == 404


def test_search_validation_and_results():
    test_client = client()
    assert test_client.get("/v1/search").status_code == 422
    response = test_client.get("/v1/search", params={"q": "apple"})
    assert response.json()["items"][0]["entity"]["label"] == "Apple pie"


def test_html_catalogue_views_render():
    test_client = client()
    assert "Foodways live" in test_client.get("/").text
    assert "Apple pie" in test_client.get("/entities").text
    assert "Controlled vocabularies" in test_client.get("/taxonomy").text
    assert "Dinner menu" in test_client.get("/menus/FH-MENU").text
    assert "Apple pie" in test_client.get("/search", params={"q": "apple"}).text
