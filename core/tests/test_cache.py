"""Tests for the SQLite response cache."""

from __future__ import annotations

import time
from pathlib import Path

from researcher_core.cache import (
    DEFAULT_TTL_SECONDS,
    ResponseCache,
    cache_key,
    default_cache_path,
)


def test_round_trips_a_response(cache: ResponseCache):
    body = {"results": [{"doi": "10.1/a"}], "meta": {"count": 1}}
    assert cache.get("openalex", "works", {"search": "ecg"}) is None

    cache.set("openalex", "works", {"search": "ecg"}, body)

    assert cache.get("openalex", "works", {"search": "ecg"}) == body
    assert cache.count() == 1


def test_creates_its_parent_directory(tmp_path: Path):
    path = tmp_path / "deeply" / "nested" / "responses.sqlite3"
    with ResponseCache(path) as cache:
        cache.set("crossref", "works", {"query": "x"}, {"ok": True})
    assert path.is_file()


def test_key_is_param_order_independent_but_value_sensitive():
    left = cache_key("openalex", "works", {"search": "ecg", "per-page": 25})
    right = cache_key("openalex", "works", {"per-page": 25, "search": "ecg"})
    assert left == right
    assert cache_key("openalex", "works", {"search": "eeg", "per-page": 25}) != left
    assert cache_key("crossref", "works", {"search": "ecg", "per-page": 25}) != left
    assert cache_key("openalex", "authors", {"search": "ecg", "per-page": 25}) != left


def test_distinct_params_are_distinct_entries(cache: ResponseCache):
    cache.set("openalex", "works", {"search": "a"}, {"n": 1})
    cache.set("openalex", "works", {"search": "b"}, {"n": 2})

    assert cache.get("openalex", "works", {"search": "a"}) == {"n": 1}
    assert cache.get("openalex", "works", {"search": "b"}) == {"n": 2}
    assert cache.count() == 2


def test_overwrites_an_existing_entry(cache: ResponseCache):
    cache.set("openalex", "works", {"search": "a"}, {"n": 1})
    cache.set("openalex", "works", {"search": "a"}, {"n": 2})

    assert cache.get("openalex", "works", {"search": "a"}) == {"n": 2}
    assert cache.count() == 1


def test_expired_entries_are_a_miss_and_are_evicted(cache: ResponseCache):
    now = time.time()
    cache.set("openalex", "works", {"search": "a"}, {"n": 1}, ttl=60, now=now)

    assert cache.get("openalex", "works", {"search": "a"}, now=now + 59) == {"n": 1}
    assert cache.get("openalex", "works", {"search": "a"}, now=now + 61) is None
    # The expired row is evicted on the miss, not left to rot.
    assert cache.count() == 0


def test_default_ttl_is_seven_days(cache: ResponseCache):
    assert DEFAULT_TTL_SECONDS == 7 * 24 * 60 * 60
    assert cache.ttl_for("openalex") == DEFAULT_TTL_SECONDS

    now = time.time()
    cache.set("openalex", "works", {"search": "a"}, {"n": 1}, now=now)
    entry = cache.get_entry("openalex", "works", {"search": "a"}, now=now)

    assert entry is not None
    assert entry.expires_at == now + DEFAULT_TTL_SECONDS
    assert not entry.is_expired(now)
    assert entry.is_expired(now + DEFAULT_TTL_SECONDS + 1)


def test_per_source_ttl_overrides_the_default(tmp_path: Path):
    with ResponseCache(
        tmp_path / "c.sqlite3", ttl_by_source={"unpaywall": 3600}
    ) as cache:
        assert cache.ttl_for("unpaywall") == 3600
        assert cache.ttl_for("openalex") == DEFAULT_TTL_SECONDS

        now = time.time()
        cache.set("unpaywall", "v2", {"doi": "10.1/a"}, {"is_oa": True}, now=now)

        assert cache.get("unpaywall", "v2", {"doi": "10.1/a"}, now=now + 3599) is not None
        assert cache.get("unpaywall", "v2", {"doi": "10.1/a"}, now=now + 3601) is None


def test_disabled_cache_never_stores_and_never_hits(tmp_path: Path):
    with ResponseCache(tmp_path / "c.sqlite3", enabled=False) as cache:
        cache.set("openalex", "works", {"search": "a"}, {"n": 1})

        assert cache.get("openalex", "works", {"search": "a"}) is None
        assert cache.count() == 0
        assert cache.clear() == 0
        assert cache.purge_expired() == 0
        assert cache.delete("openalex", "works", {"search": "a"}) is False

    # The --no-cache path does not even create the database file.
    assert not (tmp_path / "c.sqlite3").exists()


def test_no_cache_env_var_disables_the_cache(monkeypatch):
    monkeypatch.setenv("RESEARCHER_CORE_NO_CACHE", "1")
    assert ResponseCache.from_env().enabled is False

    monkeypatch.setenv("RESEARCHER_CORE_NO_CACHE", "0")
    assert ResponseCache.from_env().enabled is True


def test_cache_dir_env_var_relocates_the_database(tmp_path: Path, monkeypatch):
    target = tmp_path / "elsewhere"
    monkeypatch.setenv("RESEARCHER_CORE_CACHE_DIR", str(target))

    assert default_cache_path() == target / "responses.sqlite3"
    assert ResponseCache.from_env().path == target / "responses.sqlite3"


def test_purge_expired_and_clear(cache: ResponseCache):
    now = time.time()
    cache.set("openalex", "works", {"search": "a"}, {"n": 1}, ttl=10, now=now)
    cache.set("crossref", "works", {"search": "b"}, {"n": 2}, ttl=10_000, now=now)

    assert cache.purge_expired(now=now + 11) == 1
    assert cache.count() == 1

    assert cache.clear("openalex") == 0
    assert cache.clear("crossref") == 1
    assert cache.count() == 0


def test_delete_removes_one_entry(cache: ResponseCache):
    cache.set("openalex", "works", {"search": "a"}, {"n": 1})

    assert cache.delete("openalex", "works", {"search": "a"}) is True
    assert cache.delete("openalex", "works", {"search": "a"}) is False
    assert cache.get("openalex", "works", {"search": "a"}) is None


def test_none_body_is_never_stored(cache: ResponseCache):
    # A clean negative from a connector is None. Storing it would make a miss and a
    # cached negative indistinguishable, so it is simply not stored.
    cache.set("openalex", "works", {"search": "a"}, None)
    assert cache.count() == 0


def test_survives_reopening_the_same_file(tmp_path: Path):
    path = tmp_path / "responses.sqlite3"
    with ResponseCache(path) as first:
        first.set("openalex", "works", {"search": "a"}, {"n": 1})

    with ResponseCache(path) as second:
        assert second.get("openalex", "works", {"search": "a"}) == {"n": 1}


def test_bodies_survive_unicode_and_nesting(cache: ResponseCache):
    body = {"title": "Ubiquitous élan", "authors": [{"family": "Nuñez"}]}
    cache.set("crossref", "works", {"query": "x"}, body)
    assert cache.get("crossref", "works", {"query": "x"}) == body
