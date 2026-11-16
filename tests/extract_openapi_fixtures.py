"""Extract official schema subgraphs for offline tests. Do not hand-write schemas."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import urlopen

import yaml

ROOTS = (
    "VideoUpscaleCreateRequest",
    "VideoUpscaleJob",
    "UploadCreateRequest",
    "RemoveTextJobCreateRequest",
)

SOURCES = {
    "china": {
        "url": "https://unmarkai.cn/openapi-v1.yaml",
        "filename": "openapi-china-1.3.0.json",
    },
    "overseas": {
        "url": "https://unmarkai.net/openapi-v1.yaml",
        "filename": "openapi-overseas-1.4.0.json",
    },
}


def collect_refs(node, found: set[str]) -> None:
    if isinstance(node, dict):
        ref = node.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            found.add(ref.rsplit("/", 1)[-1])
        for value in node.values():
            collect_refs(value, found)
    elif isinstance(node, list):
        for item in node:
            collect_refs(item, found)


def extract(document: dict, roots=ROOTS) -> dict:
    schemas = document["components"]["schemas"]
    needed = set(roots)
    pending = set(roots)
    while pending:
        name = pending.pop()
        extra: set[str] = set()
        collect_refs(schemas[name], extra)
        for item in extra - needed:
            if item in schemas:
                needed.add(item)
                pending.add(item)
    return {name: schemas[name] for name in sorted(needed)}


def build_fixture(document: dict, source_url: str, retrieved: str) -> dict:
    return {
        "source": source_url,
        "retrieved": retrieved,
        "openapi": document.get("openapi"),
        "info": {
            "title": document["info"]["title"],
            "version": document["info"]["version"],
        },
        "servers": document.get("servers", []),
        "roots": list(ROOTS),
        "components": {"schemas": extract(document)},
    }


def load_yaml(path_or_url: str, url: str | None = None) -> dict:
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        with urlopen(path_or_url, timeout=30) as response:  # nosec - public docs only
            return yaml.safe_load(response.read())
    return yaml.safe_load(Path(path_or_url).read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--china-yaml")
    parser.add_argument("--overseas-yaml")
    parser.add_argument("--retrieved", default="2026-11-16")
    parser.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent / "fixtures")
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    local = {
        "china": args.china_yaml,
        "overseas": args.overseas_yaml,
    }
    for region, meta in SOURCES.items():
        source = local[region] or meta["url"]
        document = load_yaml(source)
        fixture = build_fixture(document, meta["url"], args.retrieved)
        version = fixture["info"]["version"]
        path = args.out_dir / meta["filename"]
        # If the published version changes, still write under a versioned name plus the planned filename.
        path.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n")
        print(f"wrote {path} version={version} schemas={len(fixture['components']['schemas'])}")


if __name__ == "__main__":
    main()
