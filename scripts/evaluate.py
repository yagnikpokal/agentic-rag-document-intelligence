from __future__ import annotations

import json

from docsearch.services.evaluation import evaluate_pipeline


def main() -> None:
    summary = evaluate_pipeline()
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
