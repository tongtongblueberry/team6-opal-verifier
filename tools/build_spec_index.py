# Changed: build a lightweight guidebook index for rule-coverage work.
# Why: hidden-score improvements should come from spec-backed coverage, not label guessing.

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


METHOD_NAMES = {
    "Properties",
    "StartSession",
    "EndSession",
    "Get",
    "Set",
    "Activate",
    "GenKey",
    "Read",
    "Write",
}
OBJECT_NAMES = {
    "SP",
    "C_PIN",
    "Authority",
    "Locking",
    "LockingInfo",
    "MBRControl",
    "K_AES_256",
    "Session Manager",
}
STATUS_TERMS = {"SUCCESS", "FAIL", "NOT_AUTHORIZED", "INVALID_PARAMETER"}


def load_titles(root: Path) -> dict[str, Any]:
    for path in (root / "section_title.json", root.parent / "section_title.json"):
        if path.exists():
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
    return {}


def extract_terms(text: str, candidates: set[str]) -> list[str]:
    lowered = text.lower()
    return sorted(term for term in candidates if term.lower() in lowered)


def extract_uids(text: str) -> list[str]:
    spaced = re.findall(r"(?:[0-9A-Fa-f]{2}\s+){7}[0-9A-Fa-f]{2}", text)
    compact = re.findall(r"\b[0-9A-Fa-f]{16}\b", text)
    return sorted(set(item.upper() for item in spaced + compact))[:50]


def extract_field_names(text: str) -> list[str]:
    # Changed: collect high-signal protocol-looking identifiers without NLP dependencies.
    # Why: these terms become sparse retrieval hooks for rule proposal prompts.
    terms = re.findall(r"\b[A-Z][A-Za-z0-9_]{3,}\b", text)
    blocked = {"Table", "Figure", "Section", "Example", "This", "That", "When", "Where"}
    return sorted({term for term in terms if term not in blocked})[:80]


def title_for(path: Path, root: Path, titles: dict[str, Any]) -> str:
    rel = str(path.relative_to(root))
    stem = path.stem
    return str(titles.get(rel) or titles.get(stem) or "")


def build_index(root: Path) -> list[dict[str, Any]]:
    titles = load_titles(root)
    records: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*.txt")):
        text = path.read_text(encoding="utf-8", errors="ignore")
        title = title_for(path, root, titles)
        searchable = f"{title}\n{text}"
        records.append(
            {
                "path": str(path.relative_to(root)),
                "section_title": title,
                "size": len(text),
                "methods": extract_terms(searchable, METHOD_NAMES),
                "objects": extract_terms(searchable, OBJECT_NAMES),
                "statuses": extract_terms(searchable, STATUS_TERMS),
                "uids": extract_uids(searchable),
                "fields": extract_field_names(searchable),
                "text_preview": re.sub(r"\s+", " ", text).strip()[:500],
            }
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec-root", type=Path, default=Path("/dl2026/skeleton/artifacts/documents"))
    parser.add_argument("--out", type=Path, default=Path("artifacts/spec_index.jsonl"))
    args = parser.parse_args()

    records = build_index(args.spec_root)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )

    methods = sorted({method for record in records for method in record["methods"]})
    objects = sorted({obj for record in records for obj in record["objects"]})
    print(f"indexed={len(records)}")
    print(f"methods={','.join(methods)}")
    print(f"objects={','.join(objects)}")
    print(f"out={args.out}")


if __name__ == "__main__":
    main()
