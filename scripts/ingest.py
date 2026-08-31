from __future__ import annotations

import json
from pathlib import Path

from docsearch.config import get_settings
from docsearch.services.pipeline import ingest_directory


def main() -> None:
    settings = get_settings()
    result = ingest_directory(settings.pdf_dir)
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
