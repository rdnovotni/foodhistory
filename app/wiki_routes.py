"""Public wiki reads and private-only editorial routes."""

import difflib
import hashlib
import json
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from PIL import Image, UnidentifiedImageError

from app.auth import digest_secret, new_secret
from app.config import Settings
from app.db import Database
from app.wiki_render import glossary_slugs, render_article, wiki_link_slugs
from app.wiki_repository import WikiRepository
from app.wiki_structures import structure_references

SESSION_COOKIE = "fh_editor_session"
CSRF_COOKIE = "fh_editor_csrf"


def get_wiki_repository() -> WikiRepository:
    settings = Settings.from_env()
    return WikiRepository(Database(settings.database_url))


WikiRepo = Annotated[WikiRepository, Depends(get_wiki_repository)]


def _csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def _slug(value: str) -> str:
    value = value.strip().lower()
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value):
        raise ValueError("Slug must contain lowercase letters, numbers, and single hyphens")
    return value


def _images(value: str) -> list[dict[str, str]]:
    if not value.strip():
        return []
    try:
        result = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError("Image selections are invalid") from exc
    if not isinstance(result, list) or not all(isinstance(item, dict) for item in result):
        raise ValueError("Image selections are invalid")
    return result


def _require_account(request: Request, repo: WikiRepository) -> dict[str, Any]:
    token = request.cookies.get(SESSION_COOKIE)
    account = repo.get_session(token) if token else None
    if not account:
        raise HTTPException(status_code=401, detail="Editorial sign-in required")
    return account


def _require_csrf(request: Request, account: dict[str, Any], submitted: str) -> None:
    cookie = request.cookies.get(CSRF_COOKIE, "")
    if not cookie or cookie != submitted or digest_secret(cookie) != account["csrf_token_hash"]:
        raise HTTPException(status_code=403, detail="Invalid form token")


def build_wiki_router(templates: Jinja2Templates, settings: Settings) -> APIRouter:
    router = APIRouter()

    def rendered(body: str, repo: WikiRepository) -> dict[str, Any]:
        slugs = wiki_link_slugs(body)
        terms = repo.glossary_terms(glossary_slugs(body))
        links = slugs + [term["article_slug"] for term in terms.values() if term["article_slug"]]
        structures = repo.structured_block_data(structure_references(body))
        return render_article(body, repo.public_link_targets(links), terms, structures)

    @router.get("/v1/wiki/pages", tags=["wiki"])
    def wiki_pages(
        repo: WikiRepo, q: str | None = None, category: str | None = None
    ) -> list[dict[str, Any]]:
        return repo.list_published(q=q, category=category)

    @router.get("/v1/wiki/pages/{slug}", tags=["wiki"])
    def wiki_page_api(slug: str, repo: WikiRepo) -> dict[str, Any]:
        page = repo.get_published(slug)
        if not page or "redirect_slug" in page:
            if page:
                return RedirectResponse(f"/v1/wiki/pages/{page['redirect_slug']}", status_code=308)
            raise HTTPException(status_code=404, detail="Wiki page not found")
        body = page.pop("body_markdown")
        page.update(rendered(body, repo))
        page["backlinks"] = repo.backlinks(page["slug"])
        return page

    @router.get("/v1/wiki/pages/{slug}/preview", tags=["wiki"])
    def wiki_preview(slug: str, repo: WikiRepo) -> dict[str, Any]:
        page = repo.get_published(slug)
        if page and "redirect_slug" in page:
            return RedirectResponse(f"/v1/wiki/pages/{page['redirect_slug']}/preview", status_code=308)
        if not page:
            raise HTTPException(status_code=404, detail="Wiki page not found")
        return {"slug": page["slug"], "title": page["title"],
                "summary": page["summary"],
                "reading_minutes": rendered(page["body_markdown"], repo)["reading_minutes"]}

    @router.get("/v1/wiki/pages/{slug}/revisions", tags=["wiki"])
    def wiki_revisions_api(slug: str, repo: WikiRepo) -> list[dict[str, Any]]:
        if not repo.get_published(slug) or not repo.page_information(slug):
            raise HTTPException(status_code=404, detail="Wiki page not found")
        return repo.published_revisions(slug)

    @router.get("/v1/wiki/pages/{slug}/revisions/{number}", tags=["wiki"])
    def wiki_revision_api(slug: str, number: int, repo: WikiRepo) -> dict[str, Any]:
        revision = repo.published_revision(slug, number)
        if not revision:
            raise HTTPException(status_code=404, detail="Published revision not found")
        body = revision.pop("body_markdown")
        revision.update(rendered(body, repo))
        return revision

    @router.get("/wiki", response_class=HTMLResponse, include_in_schema=False)
    def wiki_index(
        request: Request,
        repo: WikiRepo,
        q: str = "",
        category: str | None = None,
    ) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="wiki_index.html",
            context={
                "pages": repo.list_published(q=q or None, category=category),
                "categories": repo.list_public_categories(),
                "q": q,
                "selected_category": category or "",
                "recent": repo.recent_pages(),
                "improved": repo.recent_pages(improved=True),
                "on_this_day": repo.on_this_day(
                    datetime.now(ZoneInfo("America/Chicago")).month,
                    datetime.now(ZoneInfo("America/Chicago")).day,
                ),
            },
        )

    @router.get("/wiki/random", include_in_schema=False)
    def wiki_random(repo: WikiRepo) -> RedirectResponse:
        page = repo.random_page()
        if not page:
            raise HTTPException(status_code=404, detail="No published articles yet")
        return RedirectResponse(f"/wiki/{page['slug']}", status_code=303)

    @router.get("/wiki/series/{slug}", response_class=HTMLResponse, include_in_schema=False)
    def wiki_series(request: Request, slug: str, repo: WikiRepo) -> HTMLResponse:
        series = repo.public_series(slug)
        if not series:
            raise HTTPException(status_code=404, detail="Article series not found")
        return templates.TemplateResponse(
            request=request, name="wiki_series.html", context={"series": series},
        )

    @router.get("/wiki/{slug}/history", response_class=HTMLResponse, include_in_schema=False)
    def wiki_history(request: Request, slug: str, repo: WikiRepo) -> HTMLResponse:
        page = repo.page_information(slug)
        if not page:
            raise HTTPException(status_code=404, detail="Wiki page not found")
        return templates.TemplateResponse(
            request=request, name="wiki_history.html",
            context={"page": page, "revisions": repo.published_revisions(slug)},
        )

    @router.get("/wiki/{slug}/revisions/{number}", response_class=HTMLResponse,
                include_in_schema=False)
    def wiki_revision(request: Request, slug: str, number: int, repo: WikiRepo) -> HTMLResponse:
        revision = repo.published_revision(slug, number)
        if not revision:
            raise HTTPException(status_code=404, detail="Published revision not found")
        revision.update(rendered(revision["body_markdown"], repo))
        return templates.TemplateResponse(
            request=request, name="wiki_revision.html", context={"page": revision},
        )

    @router.get("/wiki/{slug}/information", response_class=HTMLResponse,
                include_in_schema=False)
    def wiki_information(request: Request, slug: str, repo: WikiRepo) -> HTMLResponse:
        page = repo.page_information(slug)
        if not page:
            raise HTTPException(status_code=404, detail="Wiki page not found")
        return templates.TemplateResponse(
            request=request, name="wiki_information.html", context={"page": page},
        )

    @router.get("/wiki/categories", response_class=HTMLResponse, include_in_schema=False)
    def wiki_categories(request: Request, repo: WikiRepo) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request,
            name="wiki_categories.html",
            context={"categories": repo.list_public_categories()},
        )

    @router.get("/wiki/category/{slug}", response_class=HTMLResponse, include_in_schema=False)
    def wiki_category(request: Request, slug: str, repo: WikiRepo) -> HTMLResponse:
        categories = repo.list_public_categories()
        category = next((item for item in categories if item["slug"] == slug), None)
        if not category:
            raise HTTPException(status_code=404, detail="Wiki category not found")
        return templates.TemplateResponse(
            request=request,
            name="wiki_category.html",
            context={"category": category, "pages": repo.list_published(category=slug)},
        )

    @router.get("/wiki/{slug}", response_class=HTMLResponse, include_in_schema=False)
    def wiki_page(request: Request, slug: str, repo: WikiRepo, view: str = "") -> HTMLResponse:
        page = repo.get_published(slug)
        if page and "redirect_slug" in page:
            return RedirectResponse(f"/wiki/{page['redirect_slug']}", status_code=308)
        if not page:
            raise HTTPException(status_code=404, detail="Wiki page not found")
        page.update(rendered(page["body_markdown"], repo))
        page["backlinks"] = repo.backlinks(page["slug"])
        return templates.TemplateResponse(
            request=request, name="wiki_page.html",
            context={"page": page, "focus": view == "focus"},
        )

    @router.get("/media/{digest}/{filename}", include_in_schema=False)
    def wiki_media(digest: str, filename: str, repo: WikiRepo) -> FileResponse:
        if not re.fullmatch(r"[0-9a-f]{64}", digest) or not re.fullmatch(
            r"asset\.(?:jpg|png|webp|gif)", filename
        ):
            raise HTTPException(status_code=404, detail="Media not found")
        storage_uri = f"/media/{digest}/{filename}"
        allowed = (
            repo.media_exists(storage_uri)
            if settings.app_mode == "editorial"
            else repo.media_is_public(storage_uri)
        )
        path = Path(settings.media_root) / digest / filename
        if not allowed or not path.is_file():
            raise HTTPException(status_code=404, detail="Media not found")
        return FileResponse(path)

    if settings.app_mode != "editorial":
        return router

    @router.get("/editor/login", response_class=HTMLResponse, include_in_schema=False)
    def editor_login(request: Request) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request, name="editor_login.html", context={"error": None}
        )

    @router.post("/editor/login", response_class=HTMLResponse, include_in_schema=False)
    def editor_login_submit(
        request: Request,
        repo: WikiRepo,
        username: Annotated[str, Form()],
        password: Annotated[str, Form()],
    ) -> HTMLResponse:
        account = repo.authenticate(username, password)
        if not account:
            return templates.TemplateResponse(
                request=request,
                name="editor_login.html",
                context={"error": "The username or password was not accepted."},
                status_code=401,
            )
        token, csrf = new_secret(), new_secret()
        repo.create_session(account["account_id"], token, csrf, settings.editor_session_hours)
        response = RedirectResponse("/editor", status_code=303)
        response.set_cookie(
            SESSION_COOKIE,
            token,
            httponly=True,
            secure=settings.editor_cookie_secure,
            samesite="strict",
            max_age=settings.editor_session_hours * 3600,
        )
        response.set_cookie(
            CSRF_COOKIE,
            csrf,
            httponly=False,
            secure=settings.editor_cookie_secure,
            samesite="strict",
            max_age=settings.editor_session_hours * 3600,
        )
        return response

    @router.post("/editor/logout", include_in_schema=False)
    def editor_logout(
        request: Request, repo: WikiRepo, csrf_token: Annotated[str, Form()]
    ) -> RedirectResponse:
        account = _require_account(request, repo)
        _require_csrf(request, account, csrf_token)
        repo.delete_session(request.cookies[SESSION_COOKIE])
        response = RedirectResponse("/editor/login", status_code=303)
        response.delete_cookie(SESSION_COOKIE)
        response.delete_cookie(CSRF_COOKIE)
        return response

    @router.get("/editor", response_class=HTMLResponse, include_in_schema=False)
    def editor_dashboard(
        request: Request, repo: WikiRepo, q: str = "", status: str = ""
    ) -> HTMLResponse:
        account = _require_account(request, repo)
        pages = repo.list_editor_pages()
        if q:
            pages = [page for page in pages if q.lower() in page["title"].lower()]
        if status:
            pages = [page for page in pages if page["status"] == status]
        return templates.TemplateResponse(
            request=request,
            name="editor_dashboard.html",
            context={
                "account": account,
                "pages": pages,
                "q": q,
                "status": status,
                "csrf_token": request.cookies.get(CSRF_COOKIE, ""),
            },
        )

    @router.get("/editor/pages/new", response_class=HTMLResponse, include_in_schema=False)
    def editor_new(request: Request, repo: WikiRepo, template: str = "") -> HTMLResponse:
        account = _require_account(request, repo)
        if account["role"] not in {"owner", "editor"}:
            raise HTTPException(status_code=403, detail="Editor role required")
        selected_template = repo.get_article_template(template) if template else None
        return templates.TemplateResponse(
            request=request,
            name="editor_form.html",
            context={
                "account": account,
                "page": None,
                "templates": repo.list_article_templates(),
                "selected_template": selected_template,
                "categories": repo.list_editor_categories(),
                "series_list": repo.list_series(),
                "csrf_token": request.cookies.get(CSRF_COOKIE, ""),
            },
        )

    @router.post("/editor/pages", include_in_schema=False)
    def editor_create(
        request: Request,
        repo: WikiRepo,
        csrf_token: Annotated[str, Form()],
        slug: Annotated[str, Form()],
        title: Annotated[str, Form(min_length=1)],
        body_markdown: Annotated[str, Form(min_length=1)],
        summary: Annotated[str, Form()] = "",
        change_note: Annotated[str, Form()] = "",
        entity_public_ids: Annotated[str, Form()] = "",
        citation_ids: Annotated[str, Form()] = "",
        category_names: Annotated[str, Form()] = "",
        image_data: Annotated[str, Form()] = "",
        series_slug: Annotated[str, Form()] = "",
        series_position: Annotated[int | None, Form()] = None,
        related_slugs: Annotated[str, Form()] = "",
        is_disambiguation: Annotated[bool, Form()] = False,
        event_month: Annotated[int | None, Form()] = None,
        event_day: Annotated[int | None, Form()] = None,
        template_key: Annotated[str, Form()] = "",
        template_version: Annotated[int | None, Form()] = None,
    ) -> RedirectResponse:
        account = _require_account(request, repo)
        _require_csrf(request, account, csrf_token)
        if account["role"] not in {"owner", "editor"}:
            raise HTTPException(status_code=403, detail="Editor role required")
        page_id = repo.create_page(
            slug=_slug(slug), title=title.strip(), summary=summary.strip(),
            body_markdown=body_markdown, change_note=change_note.strip(),
            user_id=account["account_id"], entity_public_ids=_csv(entity_public_ids),
            citation_ids=_csv(citation_ids),
            category_names=_csv(category_names), images=_images(image_data),
            series_slug=series_slug, series_position=series_position,
            related_slugs=_csv(related_slugs), is_disambiguation=is_disambiguation,
            event_month=event_month, event_day=event_day,
            template_key=template_key, template_version=template_version,
        )
        return RedirectResponse(f"/editor/pages/{page_id}", status_code=303)

    @router.post("/editor/preview", response_class=HTMLResponse, include_in_schema=False)
    def editor_preview(
        request: Request,
        repo: WikiRepo,
        csrf_token: Annotated[str, Form()],
        title: Annotated[str, Form()] = "Preview",
        body_markdown: Annotated[str, Form()] = "",
    ) -> HTMLResponse:
        account = _require_account(request, repo)
        _require_csrf(request, account, csrf_token)
        return templates.TemplateResponse(
            request=request,
            name="editor_preview.html",
            context={"title": title, **rendered(body_markdown, repo)},
        )

    @router.get("/editor/pages/{page_id}", response_class=HTMLResponse, include_in_schema=False)
    def editor_page(request: Request, page_id: str, repo: WikiRepo) -> HTMLResponse:
        account = _require_account(request, repo)
        page = repo.get_editor_page(page_id)
        if not page:
            raise HTTPException(status_code=404, detail="Wiki page not found")
        return templates.TemplateResponse(
            request=request,
            name="editor_form.html",
            context={
                "account": account,
                "page": page,
                "templates": repo.list_article_templates(),
                "selected_template": None,
                "categories": repo.list_editor_categories(),
                "series_list": repo.list_series(),
                "csrf_token": request.cookies.get(CSRF_COOKIE, ""),
            },
        )

    @router.post("/editor/pages/{page_id}/revisions", include_in_schema=False)
    def editor_revision(
        request: Request,
        page_id: str,
        repo: WikiRepo,
        csrf_token: Annotated[str, Form()],
        title: Annotated[str, Form(min_length=1)],
        body_markdown: Annotated[str, Form(min_length=1)],
        summary: Annotated[str, Form()] = "",
        change_note: Annotated[str, Form()] = "",
        entity_public_ids: Annotated[str, Form()] = "",
        citation_ids: Annotated[str, Form()] = "",
        category_names: Annotated[str, Form()] = "",
        image_data: Annotated[str, Form()] = "",
        series_slug: Annotated[str, Form()] = "",
        series_position: Annotated[int | None, Form()] = None,
        related_slugs: Annotated[str, Form()] = "",
        is_disambiguation: Annotated[bool, Form()] = False,
        event_month: Annotated[int | None, Form()] = None,
        event_day: Annotated[int | None, Form()] = None,
        template_key: Annotated[str, Form()] = "",
        template_version: Annotated[int | None, Form()] = None,
    ) -> RedirectResponse:
        account = _require_account(request, repo)
        _require_csrf(request, account, csrf_token)
        if account["role"] not in {"owner", "editor"}:
            raise HTTPException(status_code=403, detail="Editor role required")
        repo.add_revision(
            page_id, title=title.strip(), summary=summary.strip(), body_markdown=body_markdown,
            change_note=change_note.strip(), user_id=account["account_id"],
            entity_public_ids=_csv(entity_public_ids), citation_ids=_csv(citation_ids),
            category_names=_csv(category_names), images=_images(image_data),
            series_slug=series_slug, series_position=series_position,
            related_slugs=_csv(related_slugs), is_disambiguation=is_disambiguation,
            event_month=event_month, event_day=event_day,
            template_key=template_key, template_version=template_version,
        )
        return RedirectResponse(f"/editor/pages/{page_id}", status_code=303)

    @router.post("/editor/pages/{page_id}/template-migration", include_in_schema=False)
    def editor_template_migration(
        request: Request, page_id: str, repo: WikiRepo,
        csrf_token: Annotated[str, Form()],
    ) -> RedirectResponse:
        account = _require_account(request, repo)
        _require_csrf(request, account, csrf_token)
        if account["role"] not in {"owner", "editor"}:
            raise HTTPException(status_code=403, detail="Editor role required")
        page = repo.get_editor_page(page_id)
        if not page or not page.get("template"):
            raise HTTPException(status_code=404, detail="Versioned template not found")
        old = page["template"]
        latest = repo.get_article_template(old["template_key"])
        if not latest or latest["version"] <= old["template_version"]:
            raise HTTPException(status_code=409, detail="Article already uses the latest template")
        addition = latest["migration_markdown"].strip()
        body = page["body_markdown"]
        if addition:
            body = f"{body.rstrip()}\n\n{addition}\n"
        repo.add_revision(
            page_id, title=page["title"], summary=page.get("summary") or "",
            body_markdown=body,
            change_note=f"Migrated {old['template_key']} template to version {latest['version']}",
            user_id=account["account_id"], entity_public_ids=page["entity_public_ids"],
            citation_ids=page["citation_ids"], category_names=page["category_names"],
            images=page["images"],
            series_slug=(page["series_membership"] or {}).get("slug", ""),
            series_position=(page["series_membership"] or {}).get("position"),
            related_slugs=page["related_slugs"],
            is_disambiguation=page["metadata"]["is_disambiguation"],
            event_month=page["metadata"]["event_month"],
            event_day=page["metadata"]["event_day"],
            template_key=latest["template_key"], template_version=latest["version"],
            migrated_from_version=old["template_version"],
        )
        return RedirectResponse(f"/editor/pages/{page_id}", status_code=303)

    @router.get("/editor/pickers/entities", include_in_schema=False)
    def entity_picker(request: Request, repo: WikiRepo, q: str = "") -> list[dict[str, Any]]:
        _require_account(request, repo)
        return repo.search_entities(q.strip()) if q.strip() else []

    @router.get("/editor/pickers/wiki", include_in_schema=False)
    def wiki_picker(request: Request, repo: WikiRepo, q: str = "") -> list[dict[str, Any]]:
        _require_account(request, repo)
        return repo.search_wiki_pages(q.strip()) if q.strip() else []

    @router.get("/editor/templates", response_class=HTMLResponse, include_in_schema=False)
    def editor_templates(request: Request, repo: WikiRepo) -> HTMLResponse:
        account = _require_account(request, repo)
        if account["role"] != "owner":
            raise HTTPException(status_code=403, detail="Owner role required")
        return templates.TemplateResponse(
            request=request, name="editor_templates.html",
            context={"versions": repo.list_template_versions(), "account": account,
                     "csrf_token": request.cookies.get(CSRF_COOKIE, "")},
        )

    @router.post("/editor/templates", include_in_schema=False)
    def editor_create_template_version(
        request: Request, repo: WikiRepo,
        csrf_token: Annotated[str, Form()], key: Annotated[str, Form()],
        article_type: Annotated[str, Form()], title: Annotated[str, Form(min_length=1)],
        body_markdown: Annotated[str, Form(min_length=1)],
        description: Annotated[str, Form()] = "",
        migration_markdown: Annotated[str, Form()] = "",
    ) -> RedirectResponse:
        account = _require_account(request, repo)
        _require_csrf(request, account, csrf_token)
        if account["role"] != "owner":
            raise HTTPException(status_code=403, detail="Owner role required")
        allowed = {"dish", "ingredient", "restaurant", "person", "company", "book", "object"}
        if article_type not in allowed:
            raise HTTPException(status_code=422, detail="Invalid article type")
        try:
            repo.create_template_version(
                _slug(key), article_type, title.strip(), description.strip(), body_markdown,
                migration_markdown,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return RedirectResponse("/editor/templates", status_code=303)

    @router.get("/editor/series", response_class=HTMLResponse, include_in_schema=False)
    def editor_series(request: Request, repo: WikiRepo) -> HTMLResponse:
        account = _require_account(request, repo)
        return templates.TemplateResponse(request=request, name="editor_series.html",
                                          context={"series_list": repo.list_series(), "account": account,
                                                   "csrf_token": request.cookies.get(CSRF_COOKIE, "")})

    @router.post("/editor/series", include_in_schema=False)
    def editor_create_series(request: Request, repo: WikiRepo,
                             csrf_token: Annotated[str, Form()], slug: Annotated[str, Form()],
                             title: Annotated[str, Form()], description: Annotated[str, Form()] = "") -> RedirectResponse:
        account = _require_account(request, repo)
        _require_csrf(request, account, csrf_token)
        if account["role"] not in {"owner", "editor"}:
            raise HTTPException(status_code=403, detail="Editor role required")
        repo.create_series(_slug(slug), title.strip(), description.strip())
        return RedirectResponse("/editor/series", status_code=303)

    @router.get("/editor/glossary", response_class=HTMLResponse, include_in_schema=False)
    def editor_glossary(request: Request, repo: WikiRepo) -> HTMLResponse:
        account = _require_account(request, repo)
        return templates.TemplateResponse(request=request, name="editor_glossary.html",
                                          context={"terms": repo.list_glossary(), "account": account,
                                                   "csrf_token": request.cookies.get(CSRF_COOKIE, "")})

    @router.post("/editor/glossary", include_in_schema=False)
    def editor_save_glossary(request: Request, repo: WikiRepo,
                             csrf_token: Annotated[str, Form()], slug: Annotated[str, Form()],
                             term: Annotated[str, Form()], definition: Annotated[str, Form()],
                             article_slug: Annotated[str, Form()] = "",
                             is_published: Annotated[bool, Form()] = False) -> RedirectResponse:
        account = _require_account(request, repo)
        _require_csrf(request, account, csrf_token)
        if account["role"] != "owner":
            raise HTTPException(status_code=403, detail="Owner role required")
        repo.save_glossary(_slug(slug), term.strip(), definition.strip(),
                           _slug(article_slug) if article_slug.strip() else None, is_published)
        return RedirectResponse("/editor/glossary", status_code=303)

    @router.post("/editor/pages/{page_id}/redirects", include_in_schema=False)
    def editor_add_redirect(request: Request, page_id: str, repo: WikiRepo,
                            csrf_token: Annotated[str, Form()], slug: Annotated[str, Form()]) -> RedirectResponse:
        account = _require_account(request, repo)
        _require_csrf(request, account, csrf_token)
        if account["role"] != "owner":
            raise HTTPException(status_code=403, detail="Owner role required")
        repo.add_redirect(page_id, _slug(slug), account["account_id"])
        return RedirectResponse(f"/editor/pages/{page_id}", status_code=303)

    @router.post("/editor/pages/{page_id}/redirects/{slug}/delete", include_in_schema=False)
    def editor_delete_redirect(request: Request, page_id: str, slug: str,
                               repo: WikiRepo, csrf_token: Annotated[str, Form()]) -> RedirectResponse:
        account = _require_account(request, repo)
        _require_csrf(request, account, csrf_token)
        if account["role"] != "owner":
            raise HTTPException(status_code=403, detail="Owner role required")
        repo.delete_redirect(page_id, slug)
        return RedirectResponse(f"/editor/pages/{page_id}", status_code=303)

    @router.get("/editor/pickers/citations", include_in_schema=False)
    def citation_picker(request: Request, repo: WikiRepo, q: str = "") -> list[dict[str, Any]]:
        _require_account(request, repo)
        return repo.search_citations(q.strip()) if q.strip() else []

    @router.get("/editor/pickers/media", include_in_schema=False)
    def media_picker(request: Request, repo: WikiRepo, q: str = "") -> list[dict[str, Any]]:
        _require_account(request, repo)
        return repo.search_media(q.strip()) if q.strip() else []

    @router.post("/editor/media", include_in_schema=False)
    async def media_upload(
        request: Request,
        repo: WikiRepo,
        csrf_token: Annotated[str, Form()],
        upload: Annotated[UploadFile, File()],
    ) -> dict[str, Any]:
        account = _require_account(request, repo)
        _require_csrf(request, account, csrf_token)
        if account["role"] not in {"owner", "editor"}:
            raise HTTPException(status_code=403, detail="Editor role required")
        allowed_types = {
            "image/jpeg": "jpg", "image/png": "png",
            "image/webp": "webp", "image/gif": "gif",
        }
        if upload.content_type not in allowed_types:
            raise HTTPException(status_code=415, detail="Use JPEG, PNG, WebP, or GIF")
        content = await upload.read(settings.media_max_bytes + 1)
        if len(content) > settings.media_max_bytes:
            raise HTTPException(status_code=413, detail="Image exceeds the upload limit")
        try:
            with Image.open(BytesIO(content)) as image:
                image.verify()
            with Image.open(BytesIO(content)) as image:
                width, height = image.size
                detected_format = image.format
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise HTTPException(status_code=415, detail="File is not a valid image") from exc
        expected_format = {
            "image/jpeg": "JPEG", "image/png": "PNG",
            "image/webp": "WEBP", "image/gif": "GIF",
        }[upload.content_type]
        if detected_format != expected_format:
            raise HTTPException(status_code=415, detail="Image content does not match its type")
        digest = hashlib.sha256(content).hexdigest()
        filename = f"asset.{allowed_types[upload.content_type]}"
        directory = Path(settings.media_root) / digest
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / filename
        if not path.exists():
            path.write_bytes(content)
        return repo.register_media(
            sha256=digest,
            storage_uri=f"/media/{digest}/{filename}",
            original_filename=Path(upload.filename or filename).name,
            mime_type=upload.content_type,
            file_size_bytes=len(content),
            width_px=width,
            height_px=height,
            user_id=account["account_id"],
        )

    @router.get(
        "/editor/pages/{page_id}/history",
        response_class=HTMLResponse,
        include_in_schema=False,
    )
    def revision_history(
        request: Request,
        page_id: str,
        repo: WikiRepo,
        from_revision: int | None = None,
        to_revision: int | None = None,
    ) -> HTMLResponse:
        account = _require_account(request, repo)
        page = repo.get_editor_page(page_id)
        if not page:
            raise HTTPException(status_code=404, detail="Wiki page not found")
        revisions = repo.list_revisions(page_id)
        comparison = None
        if revisions and (from_revision is not None or len(revisions) > 1):
            newer_number = to_revision or revisions[0]["revision_number"]
            older_number = from_revision or revisions[1]["revision_number"]
            older = repo.get_revision(page_id, older_number)
            newer = repo.get_revision(page_id, newer_number)
            if not older or not newer:
                raise HTTPException(status_code=404, detail="Revision not found")
            comparison = {
                "from": older_number,
                "to": newer_number,
                "html": difflib.HtmlDiff(wrapcolumn=70).make_table(
                    older["body_markdown"].splitlines(),
                    newer["body_markdown"].splitlines(),
                    fromdesc=f"Revision {older_number}",
                    todesc=f"Revision {newer_number}",
                    context=True,
                    numlines=3,
                ),
            }
        return templates.TemplateResponse(
            request=request,
            name="editor_history.html",
            context={
                "account": account, "page": page, "revisions": revisions,
                "comparison": comparison,
            },
        )

    @router.post("/editor/pages/{page_id}/review", include_in_schema=False)
    def editor_review(
        request: Request,
        page_id: str,
        repo: WikiRepo,
        csrf_token: Annotated[str, Form()],
        decision: Annotated[str, Form()],
        note: Annotated[str, Form()] = "",
    ) -> RedirectResponse:
        account = _require_account(request, repo)
        _require_csrf(request, account, csrf_token)
        if decision == "submitted":
            if account["role"] not in {"owner", "editor"}:
                raise HTTPException(status_code=403, detail="Editor role required")
        elif account["role"] not in {"owner", "reviewer"}:
            raise HTTPException(status_code=403, detail="Reviewer role required")
        repo.review(page_id, decision, note.strip(), account["account_id"])
        return RedirectResponse(f"/editor/pages/{page_id}", status_code=303)

    @router.post("/editor/pages/{page_id}/publish", include_in_schema=False)
    def editor_publish(
        request: Request,
        page_id: str,
        repo: WikiRepo,
        csrf_token: Annotated[str, Form()],
    ) -> RedirectResponse:
        account = _require_account(request, repo)
        _require_csrf(request, account, csrf_token)
        if account["role"] != "owner":
            raise HTTPException(status_code=403, detail="Owner role required")
        repo.publish(page_id)
        return RedirectResponse(f"/editor/pages/{page_id}", status_code=303)

    return router
