"""researcher_core: the deterministic evidence kernel behind the Researcher plugin.

Skills invoke this package through its JSON-emitting CLI::

    uv run --project "${CLAUDE_PLUGIN_ROOT}/core" python -m researcher_core search "<query>" --json

What it provides: reproducible multi-source literature retrieval with content-addressed
response snapshots, deduplication, per-axis citation verification, publication-status
checks, minimal open-access full-text extraction with lexical passage retrieval, and an
append-only provenance ledger.

Determinism (D15) means replayable given a source snapshot, a configuration, and a parser
version: identical inputs under those three produce byte-identical ``--json`` output.
Determinism is never claimed for live calls, because live indexes change.
"""

from __future__ import annotations

__version__ = "1.0.0"

#: Version of the extraction and parsing rules. It participates in passage IDs (D21) and in
#: provenance records (D19). Bumping it intentionally invalidates derived IDs, which is what
#: makes a verdict replayable rather than merely repeatable.
PARSER_VERSION = "1"

#: Version of the decision rules (verdict precedence, thresholds) in force. Recorded on
#: every provenance event so a replay can tell which rulebook produced a verdict.
PROTOCOL_VERSION = "1"

from .cache import DEFAULT_TTL_SECONDS, CacheEntry, ResponseCache  # noqa: E402
from .model import (  # noqa: E402
    CSLDate,
    CSLName,
    CSLRecord,
    OALocation,
    canonical_json,
    content_hash,
    is_valid_doi,
    normalize_authors,
    normalize_doi,
    normalize_title,
    parse_name,
    sha256_hex,
    title_fingerprint,
)
from .snapshots import (  # noqa: E402
    Snapshot,
    SnapshotDiff,
    SnapshotError,
    SnapshotMissingError,
    SnapshotMode,
    SnapshotSession,
    SnapshotStore,
    canonicalize,
    request_key,
    response_hash,
)

__all__ = [
    "DEFAULT_TTL_SECONDS",
    "PARSER_VERSION",
    "PROTOCOL_VERSION",
    "CSLDate",
    "CSLName",
    "CSLRecord",
    "CacheEntry",
    "OALocation",
    "ResponseCache",
    "Snapshot",
    "SnapshotDiff",
    "SnapshotError",
    "SnapshotMissingError",
    "SnapshotMode",
    "SnapshotSession",
    "SnapshotStore",
    "__version__",
    "canonical_json",
    "canonicalize",
    "content_hash",
    "is_valid_doi",
    "normalize_authors",
    "normalize_doi",
    "normalize_title",
    "parse_name",
    "request_key",
    "response_hash",
    "sha256_hex",
    "title_fingerprint",
]
