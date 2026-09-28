"""Public wiki reads and private-only editorial routes."""

import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.auth import digest_secret, new_secret
from app.config import Settings
from app.db import Database
from app.wiki_render import render_markdown
from app.wiki_repository import WikiRepository

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

    @router.get("/v1/wiki/pages", tags=["wiki"])
    def wiki_pages(repo: WikiRepo) -> list[dict[str, Any]]:
        return repo.list_published()

    @router.get("/v1/wiki/pages/{slug}", tags=["wiki"])
    def wiki_page_api(slug: str, repo: WikiRepo) -> dict[str, Any]:
        page = repo.get_published(slug)
        if not page or "redirect_slug" in page:
            if page:
                return RedirectResponse(f"/v1/wiki/pages/{page['redirect_slug']}", status_code=308)
            raise HTTPException(status_code=404, detail="Wiki page not found")
        page["body_html"] = render_markdown(page.pop("body_markdown"))
        return page

    @router.get("/wiki", response_class=HTMLResponse, include_in_schema=False)
    def wiki_index(request: Request, repo: WikiRepo) -> HTMLResponse:
        return templates.TemplateResponse(
            request=request, name="wiki_index.html", context={"pages": repo.list_published()}
        )

    @router.get("/wiki/{slug}", response_class=HTMLResponse, include_in_schema=False)
    def wiki_page(request: Request, slug: str, repo: WikiRepo) -> HTMLResponse:
        page = repo.get_published(slug)
        if page and "redirect_slug" in page:
            return RedirectResponse(f"/wiki/{page['redirect_slug']}", status_code=308)
        if not page:
            raise HTTPException(status_code=404, detail="Wiki page not found")
        page["body_html"] = render_markdown(page["body_markdown"])
        return templates.TemplateResponse(
            request=request, name="wiki_page.html", context={"page": page}
        )

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
    def editor_dashboard(request: Request, repo: WikiRepo) -> HTMLResponse:
        account = _require_account(request, repo)
        return templates.TemplateResponse(
            request=request,
            name="editor_dashboard.html",
            context={
                "account": account,
                "pages": repo.list_editor_pages(),
                "csrf_token": request.cookies.get(CSRF_COOKIE, ""),
            },
        )

    @router.get("/editor/pages/new", response_class=HTMLResponse, include_in_schema=False)
    def editor_new(request: Request, repo: WikiRepo) -> HTMLResponse:
        account = _require_account(request, repo)
        if account["role"] not in {"owner", "editor"}:
            raise HTTPException(status_code=403, detail="Editor role required")
        return templates.TemplateResponse(
            request=request,
            name="editor_form.html",
            context={
                "account": account,
                "page": None,
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
            context={"title": title, "body_html": render_markdown(body_markdown)},
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
    ) -> RedirectResponse:
        account = _require_account(request, repo)
        _require_csrf(request, account, csrf_token)
        if account["role"] not in {"owner", "editor"}:
            raise HTTPException(status_code=403, detail="Editor role required")
        repo.add_revision(
            page_id, title=title.strip(), summary=summary.strip(), body_markdown=body_markdown,
            change_note=change_note.strip(), user_id=account["account_id"],
            entity_public_ids=_csv(entity_public_ids), citation_ids=_csv(citation_ids),
        )
        return RedirectResponse(f"/editor/pages/{page_id}", status_code=303)

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
