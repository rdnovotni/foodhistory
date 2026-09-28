#!/usr/bin/env python3
"""Verify a deployed Food History catalogue using only public HTTP routes."""

import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import urlopen


def fetch(base_url: str, path: str, content_type: str) -> bytes:
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    with urlopen(url, timeout=20) as response:
        if response.status != 200:
            raise RuntimeError(f"{url} returned HTTP {response.status}")
        actual_type = response.headers.get_content_type()
        if actual_type != content_type:
            raise RuntimeError(f"{url} returned {actual_type}, expected {content_type}")
        return response.read()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()
    try:
        health = json.loads(fetch(args.base_url, "/health", "application/json"))
        if health.get("status") != "ok":
            raise RuntimeError(f"Unexpected health response: {health}")
        homepage = fetch(args.base_url, "/", "text/html").decode()
        if "Food History" not in homepage:
            raise RuntimeError("Homepage does not contain the application title")
        openapi = json.loads(fetch(args.base_url, "/api/openapi.json", "application/json"))
        required = {"/v1/entities", "/v1/works/{public_id}", "/v1/objects/{public_id}"}
        missing = required - set(openapi.get("paths", {}))
        if missing:
            raise RuntimeError(f"OpenAPI is missing routes: {sorted(missing)}")
    except (HTTPError, URLError) as exc:
        raise SystemExit(f"Smoke test failed: {exc}") from exc
    print("PASS: health, homepage, and public API contract are available")


if __name__ == "__main__":
    main()
