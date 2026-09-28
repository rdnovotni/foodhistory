"""Safe Markdown rendering and wiki links for authored revisions."""

import re
import unicodedata
from html import unescape

import bleach
from markdown_it import MarkdownIt
from markdown_it.token import Token

_MARKDOWN = MarkdownIt("commonmark", {"html": False, "linkify": False})
_LINK = re.compile(r"\[\[([a-z0-9]+(?:-[a-z0-9]+)*)(?:\|([^\[\]\n]+))?\]\]")
_TAGS = {
    "a", "blockquote", "br", "code", "em", "h1", "h2", "h3", "h4", "hr",
    "li", "ol", "p", "pre", "span", "strong", "ul",
}


def _text_tokens(source: str):
    """Yield prose tokens, excluding code and ordinary Markdown links."""
    for block in _MARKDOWN.parse(source):
        if block.type != "inline":
            continue
        link_depth = 0
        for child in block.children or []:
            if child.type == "link_open":
                link_depth += 1
            elif child.type == "link_close":
                link_depth -= 1
            elif child.type == "text" and not link_depth:
                yield child


def wiki_link_slugs(source: str) -> list[str]:
    """Return unique links in reading order, with the same parsing as rendering."""
    return list(dict.fromkeys(match.group(1) for token in _text_tokens(source)
                              for match in _LINK.finditer(token.content)))


def _anchor(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "section"


def render_article(source: str, pages: dict[str, dict] | None = None) -> dict:
    """Render article body and a matching heading outline; pages are public targets."""
    pages = pages or {}
    blocks = _MARKDOWN.parse(source)
    toc = []
    anchors: dict[str, int] = {}
    for index, block in enumerate(blocks):
        if block.type == "heading_open" and block.tag in {"h2", "h3", "h4"}:
            inline = blocks[index + 1]
            label = unescape("".join(child.content for child in inline.children or []
                                     if child.type in {"text", "code_inline"})).strip()
            base = _anchor(label)
            anchors[base] = anchors.get(base, 0) + 1
            anchor = base if anchors[base] == 1 else f"{base}-{anchors[base]}"
            block.attrSet("id", anchor)
            toc.append({"id": anchor, "title": label, "level": int(block.tag[1])})
        if block.type != "inline":
            continue
        children = []
        link_depth = 0
        for child in block.children or []:
            if child.type == "link_open":
                link_depth += 1
            if child.type == "text" and not link_depth:
                start = 0
                for match in _LINK.finditer(child.content):
                    if match.start() > start:
                        children.append(Token("text", "", 0, content=child.content[start:match.start()]))
                    slug = match.group(1)
                    target = pages.get(slug)
                    label = match.group(2) or (target["title"] if target else slug.replace("-", " "))
                    if target:
                        opening = Token("link_open", "a", 1)
                        opening.attrSet("href", f"/wiki/{target['slug']}")
                    else:
                        opening = Token("span_open", "span", 1)
                        opening.attrSet("class", "wiki-missing")
                        opening.attrSet("title", "Wiki page not published")
                    children.extend((opening, Token("text", "", 0, content=label),
                                     Token("link_close" if target else "span_close",
                                           "a" if target else "span", -1)))
                    start = match.end()
                if start:
                    if start < len(child.content):
                        children.append(Token("text", "", 0, content=child.content[start:]))
                else:
                    children.append(child)
            else:
                children.append(child)
            if child.type == "link_close":
                link_depth -= 1
        block.children = children
    html = bleach.clean(
        _MARKDOWN.renderer.render(blocks, _MARKDOWN.options, {}),
        tags=_TAGS,
        attributes={"a": ["href", "title"], "span": ["class", "title"],
                    "h2": ["id"], "h3": ["id"], "h4": ["id"]},
        protocols={"http", "https", "mailto"},
        strip=True,
    )
    return {"body_html": html, "toc": toc}


def render_markdown(source: str) -> str:
    return render_article(source)["body_html"]
