from __future__ import annotations

import argparse
import json
from pathlib import Path

from docsearch.config import get_settings
from docsearch.services.evaluation import evaluate_pipeline
from docsearch.services.pipeline import ingest_directory


def ingest_cli() -> None:
    parser = argparse.ArgumentParser(description="Ingest PDFs into pgvector")
    parser.add_argument("--source", default=None, help="Directory of PDF files")
    parser.add_argument("--no-enrich", action="store_true", help="Skip contextual chunk prefixes")
    args = parser.parse_args()
    result = ingest_directory(
        Path(args.source) if args.source else None,
        enrich=False if args.no_enrich else None,
    )
    print(json.dumps(result, indent=2, default=str))


def eval_cli() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the RAG pipeline with RAGAs")
    parser.add_argument("--dataset", default=None)
    parser.add_argument("--sample-size", type=int, default=None)
    args = parser.parse_args()
    summary = evaluate_pipeline(
        dataset_path=Path(args.dataset) if args.dataset else None,
        sample_size=args.sample_size,
    )
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    get_settings()
    ingest_cli()
