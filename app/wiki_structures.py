"""Structured, canonical-data-aware blocks embedded in wiki Markdown fences."""

import json
from html import escape
from typing import Any

from markdown_it import MarkdownIt

BLOCK_TYPES = {
    "infobox", "notice", "quotation", "sidebar", "gallery", "comparison",
    "timeline", "map", "source-excerpt", "recipe", "menu-excerpt",
    "historical-price", "contested-history", "bibliography",
}


def _payload(token: Any) -> tuple[str, dict[str, Any]] | None:
    kind = token.info.strip().lower()
    if token.type != "fence" or not kind.startswith("fh-"):
        return None
    kind = kind[3:]
    if kind not in BLOCK_TYPES:
        return None
    try:
        value = json.loads(token.content)
    except json.JSONDecodeError:
        return kind, {"error": "This block contains invalid JSON."}
    return kind, value if isinstance(value, dict) else {"error": "Block data must be an object."}


def structure_references(source: str) -> dict[str, list[str]]:
    """Collect stable identifiers required to resolve structured blocks."""
    found = {"entities": [], "citations": [], "menus": [], "prices": [], "media": []}
    for token in MarkdownIt("commonmark").parse(source):
        parsed = _payload(token)
        if not parsed:
            continue
        kind, data = parsed
        if kind in {"infobox", "map"}:
            points = data.get("points") if isinstance(data.get("points"), list) else []
            values = [data.get("public_id"), *(p.get("public_id") for p in points if isinstance(p, dict))]
            found["entities"].extend(value for value in values if isinstance(value, str))
        if kind == "gallery":
            values = data.get("public_ids") if isinstance(data.get("public_ids"), list) else []
            found["media"].extend(str(value) for value in values)
        if kind == "menu-excerpt" and isinstance(data.get("public_id"), str):
            found["menus"].append(data["public_id"])
        if kind == "historical-price" and isinstance(data.get("public_id"), str):
            found["prices"].append(data["public_id"])
        citation_ids = data.get("citation_ids") if isinstance(data.get("citation_ids"), list) else []
        if isinstance(data.get("citation_id"), str):
            citation_ids = [*citation_ids, data["citation_id"]]
        found["citations"].extend(str(value) for value in citation_ids)
    return {key: list(dict.fromkeys(values)) for key, values in found.items()}


def _tag(name: str, value: Any) -> str:
    return f"<dt>{escape(name)}</dt><dd>{escape(str(value))}</dd>" if value not in (None, "", []) else ""


def _citation(item: dict[str, Any]) -> str:
    locator = item.get("locator_text") or item.get("page_label") or ""
    suffix = f", {escape(str(locator))}" if locator else ""
    return f'<a href="/entities/{escape(item["source_public_id"])}">{escape(item["source_label"])}</a>{suffix}'


def render_structure(kind: str, data: dict[str, Any], resolved: dict[str, Any]) -> str:
    if error := data.get("error"):
        return f'<aside class="structure structure-error"><strong>Invalid {escape(kind)} block</strong><p>{escape(error)}</p></aside>'
    title = escape(str(data.get("title") or kind.replace("-", " ").title()))
    entities = resolved.get("entities", {})
    citations = resolved.get("citations", {})
    if kind == "infobox":
        record = entities.get(data.get("public_id"))
        if not record:
            return '<aside class="structure structure-error">Canonical record is unavailable.</aside>'
        fields = "".join(_tag(label, record.get(key)) for label, key in (
            ("Type", "type_label"), ("Dates", "dates"), ("Occupation", "occupation"),
            ("Founded", "founded"), ("Website", "website"), ("Address", "address"),
            ("Created", "creation_date"), ("Manufactured", "manufacture_date"),
            ("Materials", "materials"), ("Identifiers", "identifiers"),
        ))
        return (f'<aside class="structure infobox"><p class="structure-kicker">Canonical record</p>'
                f'<h2>{escape(record["label"])}</h2><dl>{fields}</dl>'
                f'<a href="/entities/{escape(record["public_id"])}">View catalogue record</a></aside>')
    if kind == "notice":
        tone = data.get("tone", "note") if data.get("tone") in {"note", "warning", "context", "research"} else "note"
        return f'<aside class="structure notice notice-{tone}"><h2>{title}</h2><p>{escape(str(data.get("text", "")))}</p></aside>'
    if kind == "quotation":
        footer = " — ".join(escape(str(value)) for value in (data.get("attribution"), data.get("source")) if value)
        return f'<figure class="structure quotation"><blockquote>{escape(str(data.get("quote", "")))}</blockquote>{f"<figcaption>{footer}</figcaption>" if footer else ""}</figure>'
    if kind == "sidebar":
        return f'<aside class="structure sidebar"><h2>{title}</h2><p>{escape(str(data.get("text", "")))}</p></aside>'
    if kind == "gallery":
        figures = []
        captions = data.get("captions", {})
        for public_id in data.get("public_ids", []):
            image = resolved.get("media", {}).get(public_id)
            if image:
                caption = captions.get(public_id) or image.get("label") or ""
                figures.append(f'<figure><img src="{escape(image["uri"])}" alt="{escape(str(caption))}"><figcaption>{escape(str(caption))}</figcaption></figure>')
        return f'<section class="structure gallery"><h2>{title}</h2><div class="structure-grid">{"".join(figures)}</div></section>'
    if kind == "comparison":
        columns = "".join(f'<section><h3>{escape(str(column.get("title", "")))}</h3><ul>{"".join(f"<li>{escape(str(item))}</li>" for item in column.get("items", []))}</ul></section>' for column in data.get("columns", []) if isinstance(column, dict))
        return f'<section class="structure comparison"><h2>{title}</h2><div class="structure-grid">{columns}</div></section>'
    if kind == "timeline":
        events = "".join(f'<li><time>{escape(str(event.get("date", "")))}</time><div><strong>{escape(str(event.get("title", "")))}</strong><p>{escape(str(event.get("text", "")))}</p></div></li>' for event in data.get("events", []) if isinstance(event, dict))
        return f'<section class="structure timeline"><h2>{title}</h2><ol>{events}</ol></section>'
    if kind == "map":
        points = []
        for point in data.get("points", []):
            if not isinstance(point, dict):
                continue
            record = entities.get(point.get("public_id"), {})
            lat, lon = point.get("latitude", record.get("latitude")), point.get("longitude", record.get("longitude"))
            if lat is None or lon is None:
                continue
            label = point.get("label") or record.get("label") or "Location"
            points.append(f'<li data-map-point data-latitude="{escape(str(lat))}" data-longitude="{escape(str(lon))}"><strong>{escape(str(label))}</strong><span>{escape(str(lat))}, {escape(str(lon))}</span></li>')
        return f'<section class="structure map-block" data-map><h2>{title}</h2><div class="map-plot" aria-hidden="true"></div><ol>{"".join(points)}</ol></section>'
    if kind == "source-excerpt":
        citation = citations.get(data.get("citation_id"))
        excerpt = data.get("excerpt") or (citation or {}).get("excerpt") or ""
        credit = _citation(citation) if citation else "Source unavailable"
        return f'<figure class="structure source-excerpt"><h2>{title}</h2><blockquote>{escape(str(excerpt))}</blockquote><figcaption>{credit}</figcaption></figure>'
    if kind == "recipe":
        ingredients = "".join(f'<li>{escape(str(item))}</li>' for item in data.get("ingredients", []))
        steps = "".join(f'<li>{escape(str(item))}</li>' for item in data.get("steps", []))
        source = citations.get(data.get("citation_id"))
        return f'<section class="structure recipe-block"><h2>{title}</h2>{_tag("Yield", data.get("yield"))}<h3>Ingredients</h3><ul>{ingredients}</ul><h3>Method</h3><ol>{steps}</ol>{f"<p class=structure-source>{_citation(source)}</p>" if source else ""}</section>'
    if kind == "menu-excerpt":
        menu = resolved.get("menus", {}).get(data.get("public_id"))
        if not menu:
            return '<aside class="structure structure-error">Published menu record is unavailable.</aside>'
        limit = max(1, min(int(data.get("limit", 12)), 50))
        items = "".join(f'<tr><th>{escape(str(item["name"]))}</th><td>{escape(str(item.get("description") or ""))}</td><td>{escape(str(item.get("price") or ""))}</td></tr>' for item in menu["items"][:limit])
        return f'<section class="structure menu-excerpt"><h2>{title}</h2><p>{escape(menu["label"])} · {escape(str(menu.get("date") or "Undated"))}</p><table><tbody>{items}</tbody></table></section>'
    if kind == "historical-price":
        rows = "".join(f'<tr><th>{escape(str(item.get("date") or "Undated"))}</th><td>{escape(str(item.get("display") or ""))}</td><td>{escape(str(item.get("place") or ""))}</td><td>{_citation(item["citation"])}</td></tr>' for item in resolved.get("prices", {}).get(data.get("public_id"), []))
        return f'<section class="structure price-block"><h2>{title}</h2><table><thead><tr><th>Date</th><th>Price</th><th>Place</th><th>Source</th></tr></thead><tbody>{rows}</tbody></table></section>'
    if kind == "contested-history":
        views = "".join(f'<section><h3>{escape(str(view.get("label", "Perspective")))}</h3><p>{escape(str(view.get("text", "")))}</p></section>' for view in data.get("perspectives", []) if isinstance(view, dict))
        return f'<section class="structure contested"><h2>{title}</h2><p>{escape(str(data.get("claim", "")))}</p>{views}<p class="structure-note">{escape(str(data.get("note", "Evidence and interpretations may differ.")))}</p></section>'
    if kind == "bibliography":
        items = "".join(f'<li>{_citation(citations[value])}</li>' for value in data.get("citation_ids", []) if value in citations)
        return f'<section class="structure bibliography"><h2>{title}</h2><ol>{items}</ol></section>'
    return '<aside class="structure structure-error">Unsupported article block.</aside>'


def apply_structures(blocks: list[Any], resolved: dict[str, Any] | None = None) -> None:
    """Replace recognized fence tokens with controlled HTML before sanitization."""
    resolved = resolved or {}
    for token in blocks:
        parsed = _payload(token)
        if parsed:
            token.type = "html_block"
            token.tag = ""
            try:
                token.content = render_structure(*parsed, resolved)
            except (KeyError, TypeError, ValueError):
                token.content = (
                    f'<aside class="structure structure-error"><strong>Invalid '
                    f'{escape(parsed[0])} block</strong><p>Check the block fields and value types.</p></aside>'
                )

