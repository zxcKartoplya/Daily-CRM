"""Выгружает схему OpenAPI в openapi.json — контракт для клиентов."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.main import app

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "openapi.json"


def render() -> str:
    return json.dumps(app.openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> None:
    SCHEMA_PATH.write_text(render(), encoding="utf-8")
    print(f"schema written to {SCHEMA_PATH}")


if __name__ == "__main__":
    main()
