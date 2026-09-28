"""Safe Markdown rendering for authored wiki revisions."""

import bleach
from markdown_it import MarkdownIt

_MARKDOWN = MarkdownIt("commonmark", {"html": False, "linkify": False})
_TAGS = {
    "a", "blockquote", "br", "code", "em", "h1", "h2", "h3", "h4", "hr",
    "li", "ol", "p", "pre", "strong", "ul",
}


def render_markdown(source: str) -> str:
    return bleach.clean(
        _MARKDOWN.render(source),
        tags=_TAGS,
        attributes={"a": ["href", "title"]},
        protocols={"http", "https", "mailto"},
        strip=True,
    )
