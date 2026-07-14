"""Entry point for ``python -m researcher_core``.

Delegates to :func:`researcher_core.cli.main`, which is also what the ``researcher-core``
console script points at. The import is deferred into the guard so that importing this
module never drags the whole CLI in.
"""

from __future__ import annotations

if __name__ == "__main__":
    from researcher_core.cli import main

    raise SystemExit(main())
