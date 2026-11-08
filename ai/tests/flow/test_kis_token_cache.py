"""Pure cache regressions; no KIS client/app import or real credentials.

This AI pytest file is source-maintained. The protected Backend suite executes
this product cache module with synthetic credentials and owned temporary files.
"""
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from agents.flow.infrastructure import token_cache as cache  # noqa: E402


def context(tmp_path):
    base = tmp_path / "kis_token.json"
    digest = cache.scope_digest("https://synthetic.invalid", "synthetic-key", "synthetic-secret")
    return base, cache.scoped_path(base, digest), digest


def test_cache_roundtrip(tmp_path):
    _, path, digest = context(tmp_path)
    cache.write_cache(path, digest, "tok-abc", expires_at=1000.0)
    assert cache.read_cache(path, digest, now=100.0) == "tok-abc"


def test_expired_or_margin_cache_returns_none(tmp_path):
    _, path, digest = context(tmp_path)
    cache.write_cache(path, digest, "tok-abc", expires_at=1000.0)
    assert cache.read_cache(path, digest, now=2000.0) is None
    assert cache.read_cache(path, digest, now=950.0) is None


def test_missing_or_broken_cache_returns_none(tmp_path):
    _, path, digest = context(tmp_path)
    assert cache.read_cache(path, digest, now=0.0) is None
    path.write_text("not json", encoding="utf-8")
    path.chmod(0o600)
    assert cache.read_cache(path, digest, now=0.0) is None
    path.write_text("{}", encoding="utf-8")
    assert cache.read_cache(path, digest, now=0.0) is None


def test_valid_cache_skips_issuance(tmp_path):
    base, path, digest = context(tmp_path)
    cache.write_cache(path, digest, "tok-cached", expires_at=1000.0)
    def boom():
        raise AssertionError("valid cache must skip issuer")
    assert cache.get_token(base, "https://synthetic.invalid", "synthetic-key", "synthetic-secret", 100.0, boom) == "tok-cached"


def test_expired_cache_triggers_issuance_and_refreshes(tmp_path):
    base, path, digest = context(tmp_path)
    cache.write_cache(path, digest, "tok-old", expires_at=90.0)
    calls = []
    def issuer():
        calls.append(True)
        return {"access_token": "tok-new", "expires_in": 86400}
    assert cache.get_token(base, "https://synthetic.invalid", "synthetic-key", "synthetic-secret", 100.0, issuer) == "tok-new"
    assert calls == [True]
    assert cache.read_cache(path, digest, now=100.0) == "tok-new"
