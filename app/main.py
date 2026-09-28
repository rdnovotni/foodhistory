"""FastAPI entry point for the Food History public catalogue."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from psycopg import Error as DatabaseError

from app import __version__
from app.config import Settings
from app.db import Database
from app.repository import Repository

BASE_DIR = Path(__file__).resolve().parent
VOCABULARY_CODES = {"ENT", "FC", "SUB", "ROT", "CTX", "COL", "FAC", "REL", "EVD", "CAT"}


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()


def get_repository(settings: Annotated[Settings, Depends(get_settings)]) -> Repository:
    return Repository(Database(settings.database_url))


Repo = Annotated[Repository, Depends(get_repository)]


def create_app() -> FastAPI:
    app = FastAPI(
        title="Food History",
        version=__version__,
        description="Public read API and catalogue for the Food History knowledge base.",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )
    app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
    templates = Jinja2Templates(directory=BASE_DIR / "templates")

    @app.exception_handler(ValueError)
    async def invalid_parameter(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.get("/health", tags=["system"])
    def health(repo: Repo) -> JSONResponse:
        try:
            repo.db.ping()
        except DatabaseError:
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return JSONResponse(content={"status": "ok", "version": __version__})

    @app.get("/v1/entities", tags=["entities"])
    def entities(
        repo: Repo,
        q: str | None = None,
        type_code: str | None = None,
        term_code: str | None = None,
        cursor: str | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
    ) -> dict:
        return repo.list_entities(
            q=q, type_code=type_code, term_code=term_code, cursor=cursor, limit=limit
        )

    @app.get("/v1/entities/{public_id}/assertions", tags=["entities", "evidence"])
    def entity_assertions(
        public_id: str, repo: Repo, predicate_code: str | None = None
    ) -> list[dict]:
        assertions = repo.get_assertions(public_id, predicate_code)
        if assertions is None:
            raise HTTPException(status_code=404, detail="Entity not found")
        return assertions

    @app.get("/v1/entities/{public_id}", tags=["entities"])
    def entity(public_id: str, repo: Repo) -> dict:
        result = repo.get_entity(public_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Entity not found")
        return result

    @app.get("/v1/taxonomy/{vocabulary_code}/terms", tags=["taxonomy"])
    def taxonomy_terms(
        vocabulary_code: str,
        repo: Repo,
        parent_code: str | None = None,
        q: str | None = None,
    ) -> list[dict]:
        code = vocabulary_code.upper()
        if code not in VOCABULARY_CODES:
            raise HTTPException(status_code=404, detail="Vocabulary not found")
        return repo.list_taxonomy_terms(code, parent_code, q)

    @app.get("/v1/taxonomy/terms/{code:path}", tags=["taxonomy"])
    def taxonomy_term(code: str, repo: Repo) -> dict:
        result = repo.get_taxonomy_term(code)
        if result is None:
            raise HTTPException(status_code=404, detail="Taxonomy term not found")
        return result

    @app.get("/v1/menus/{public_id}", tags=["menus"])
    def menu(public_id: str, repo: Repo) -> dict:
        result = repo.get_menu(public_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Menu not found")
        return result

    @app.get("/v1/foods/{public_id}/menu-occurrences", tags=["menus"])
    def menu_occurrences(
        public_id: str,
        repo: Repo,
        date_from: str | None = None,
        date_to: str | None = None,
        place_id: str | None = None,
        cursor: str | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
    ) -> dict:
        result = repo.get_menu_occurrences(
            public_id,
            date_from=date_from,
            date_to=date_to,
            place_id=place_id,
            cursor=cursor,
            limit=limit,
        )
        if result is None:
            raise HTTPException(status_code=404, detail="Food entity not found")
        return result

    @app.get("/v1/works/{public_id}", tags=["bibliography"])
    def work(public_id: str, repo: Repo) -> dict:
        result = repo.get_work(public_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Work not found")
        return result

    @app.get("/v1/objects/{public_id}", tags=["material culture"])
    def object_record(public_id: str, repo: Repo) -> dict:
        result = repo.get_object(public_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Object not found")
        return result

    @app.get("/v1/search", tags=["search"])
    def search(
        repo: Repo,
        q: Annotated[str, Query(min_length=1)],
        type_code: str | None = None,
        term_code: str | None = None,
        cursor: str | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
    ) -> dict:
        return repo.search(q, type_code, term_code, cursor, limit)

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def home(request: Request, repo: Repo) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="home.html",
            context={"vocabularies": repo.list_vocabularies()},
        )

    @app.get("/entities", response_class=HTMLResponse, include_in_schema=False)
    def browse_entities(
        request: Request,
        repo: Repo,
        q: str | None = None,
        type_code: str | None = None,
        term_code: str | None = None,
        cursor: str | None = None,
    ) -> HTMLResponse:
        page = repo.list_entities(
            q=q, type_code=type_code, term_code=term_code, cursor=cursor
        )
        return templates.TemplateResponse(
            request=request,
            name="entities.html",
            context={
                "page": page,
                "q": q or "",
                "type_code": type_code or "",
                "term_code": term_code or "",
            },
        )

    @app.get("/entities/{public_id}", response_class=HTMLResponse, include_in_schema=False)
    def entity_page(request: Request, public_id: str, repo: Repo) -> HTMLResponse:
        result = repo.get_entity(public_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Entity not found")
        assertions = repo.get_assertions(public_id) or []
        return templates.TemplateResponse(
            request=request,
            name="entity.html",
            context={"entity": result, "assertions": assertions},
        )

    @app.get("/taxonomy", response_class=HTMLResponse, include_in_schema=False)
    def taxonomy_index(request: Request, repo: Repo) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="taxonomy_index.html",
            context={"vocabularies": repo.list_vocabularies()},
        )

    @app.get(
        "/taxonomy/{vocabulary_code}", response_class=HTMLResponse, include_in_schema=False
    )
    def taxonomy_page(
        request: Request,
        vocabulary_code: str,
        repo: Repo,
        parent_code: str | None = None,
        q: str | None = None,
    ) -> HTMLResponse:
        code = vocabulary_code.upper()
        if code not in VOCABULARY_CODES:
            raise HTTPException(status_code=404, detail="Vocabulary not found")
        return templates.TemplateResponse(
            request=request,
            name="taxonomy.html",
            context={
                "vocabulary_code": code,
                "terms": repo.list_taxonomy_terms(code, parent_code, q),
                "parent_code": parent_code or "",
                "q": q or "",
            },
        )

    @app.get("/menus/{public_id}", response_class=HTMLResponse, include_in_schema=False)
    def menu_page(request: Request, public_id: str, repo: Repo) -> HTMLResponse:
        result = repo.get_menu(public_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Menu not found")
        return templates.TemplateResponse(
            request=request, name="menu.html", context={"menu": result}
        )

    @app.get("/works/{public_id}", response_class=HTMLResponse, include_in_schema=False)
    def work_page(request: Request, public_id: str, repo: Repo) -> HTMLResponse:
        result = repo.get_work(public_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Work not found")
        return templates.TemplateResponse(
            request=request, name="work.html", context={"tree": result}
        )

    @app.get("/objects/{public_id}", response_class=HTMLResponse, include_in_schema=False)
    def object_page(request: Request, public_id: str, repo: Repo) -> HTMLResponse:
        result = repo.get_object(public_id)
        if result is None:
            raise HTTPException(status_code=404, detail="Object not found")
        return templates.TemplateResponse(
            request=request, name="object.html", context={"object": result}
        )

    @app.get("/search", response_class=HTMLResponse, include_in_schema=False)
    def search_page(
        request: Request,
        repo: Repo,
        q: str = "",
        type_code: str | None = None,
        term_code: str | None = None,
        cursor: str | None = None,
    ) -> HTMLResponse:
        page = repo.search(q, type_code, term_code, cursor) if q else None
        return templates.TemplateResponse(
            request=request,
            name="search.html",
            context={
                "page": page,
                "q": q,
                "type_code": type_code or "",
                "term_code": term_code or "",
            },
        )

    return app


app = create_app()
