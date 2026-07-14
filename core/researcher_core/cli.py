"""Command-line interface for researcher_core.

PLACEHOLDER. This module exists so that the ``researcher-core`` console script and
``python -m researcher_core`` resolve while the full CLI (task M2.11: search, get,
verify-bib, verify-ref, status, citations, references, oa-pdf, fulltext, passages,
faithfulness, snapshot, provenance) is being built. It is expected to be replaced wholesale.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from . import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="researcher-core",
        description=(
            "Deterministic multi-source literature retrieval and per-axis citation "
            "verification."
        ),
    )
    parser.add_argument("--version", action="version", version=f"researcher-core {__version__}")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of a human table.",
    )
    parser.add_argument("command", nargs="?", help="Subcommand to run.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command:
        parser.error(f"unknown command: {args.command}")
    parser.print_help()
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
