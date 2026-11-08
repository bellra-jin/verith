"""CF-004: actual stdlib product module, owned files and fake issuers only.

The KIS adapter is source-inspected, never imported. This is not AI pytest or
real KIS/credential/cache validation.
"""
import ast
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace

import pytest

_AI = Path(__file__).resolve().parents[3] / "ai/src"
sys.path.append(str(_AI))
try:
    from agents.flow.infrastructure import token_cache as cache
finally:
    sys.path.remove(str(_AI))

SERVER, KEY, SECRET = "https://synthetic.invalid", "sentinel-key", "sentinel-secret"
TOKEN = "synthetic-token"
NOW = 100.0


@pytest.fixture
def context(tmp_path):
    base = tmp_path / "isolated" / "kis_token.json"
    digest = cache.scope_digest(SERVER, KEY, SECRET)
    return base, cache.scoped_path(base, digest), digest


def issue(context, body=None, *, now=NOW, credentials=(SERVER, KEY, SECRET)):
    calls = []
    def issuer():
        calls.append(True)
        return {"access_token": TOKEN, "expires_in": 3600} if body is None else body
    result = cache.get_token(context[0], *credentials, now, issuer)
    return result, calls


def put_raw(context, raw):
    path = context[1]
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_bytes(raw)
    path.chmod(0o600)


def record(context, **changes):
    return dict(schema_version=2, scope_digest=context[2], token=TOKEN, expires_at=1000.0) | changes


def assert_fixed(error):
    assert type(error) is cache.TokenCacheError
    assert str(error) in {"KIS token cache operation failed.", "KIS token cache update failed after replacement."}
    import traceback
    rendered = "".join(traceback.format_exception(type(error), error, error.__traceback__))
    assert error.__cause__ is None
    # A directly created safe error need not suppress an absent context.
    if error.__context__ is not None:
        assert error.__suppress_context__
    for sentinel in (KEY, SECRET, TOKEN, "provider-private-body", "private-path"):
        assert sentinel not in str(error) and sentinel not in repr(error) and sentinel not in rendered


def test_roundtrip_hit_skips_issuer_legacy_unchanged(context):
    base, path, digest = context
    base.parent.mkdir(mode=0o700)
    base.write_bytes(b'legacy-synthetic-marker')
    legacy = (base.read_bytes(), base.stat().st_ino)
    cache.write_cache(path, digest, TOKEN, 1000.0)
    def boom():
        raise AssertionError("hit must never issue")
    assert cache.get_token(base, SERVER, KEY, SECRET, NOW, boom) == TOKEN
    assert cache.read_cache(path, digest, NOW) == TOKEN
    assert (base.read_bytes(), base.stat().st_ino) == legacy
    assert KEY not in path.name and SECRET not in path.name and SERVER not in path.name
    assert json.loads(path.read_bytes()) == record(context)


@pytest.mark.parametrize("credentials", [(SERVER, KEY+'x', SECRET), (SERVER, KEY, SECRET+'x'),
                                          (SERVER+'/other', KEY, SECRET)])
def test_context_change_and_rotation_do_not_reuse_or_modify_other_cache(context, credentials):
    cache.write_cache(context[1], context[2], "old-synthetic-token", 1000.0)
    before = (context[1].read_bytes(), context[1].stat().st_ino)
    assert issue(context, credentials=credentials) == (TOKEN, [True])
    digest = cache.scope_digest(*credentials)
    assert digest != context[2]
    assert cache.read_cache(cache.scoped_path(context[0], digest), digest, NOW) == TOKEN
    assert (context[1].read_bytes(), context[1].stat().st_ino) == before


def test_context_canonical_boundaries_and_only_server_trailing_slashes():
    assert cache.scope_digest(SERVER+'///', KEY, SECRET) == cache.scope_digest(SERVER, KEY, SECRET)
    assert cache.scope_digest(SERVER, "ab", "c") != cache.scope_digest(SERVER, "a", "bc")
    assert cache.scope_digest(SERVER, ' '+KEY, SECRET) != cache.scope_digest(SERVER, KEY, SECRET)
    assert cache.scope_digest(SERVER.upper(), KEY, SECRET) != cache.scope_digest(SERVER, KEY, SECRET)


@pytest.mark.parametrize("now,hit", [(939.999, True), (940.0, False), (940.001, False), (1000.0, False), (2000.0, False)])
def test_exact_margin_and_expiry(context, now, hit):
    cache.write_cache(context[1], context[2], TOKEN, 1000.0)
    assert (cache.read_cache(context[1], context[2], now) == TOKEN) is hit
    value, calls = issue(context, now=now)
    assert value == TOKEN and calls == ([] if hit else [True])


@pytest.mark.parametrize("now", [True, False, "100", None, float('nan'), float('inf'), -float('inf'), 10**1000])
def test_invalid_now_errors_before_issuer_or_file_creation(context, now):
    calls = []
    with pytest.raises(cache.TokenCacheError) as caught:
        cache.get_token(context[0], SERVER, KEY, SECRET, now, lambda: calls.append(True))
    assert_fixed(caught.value)
    assert calls == [] and not context[1].parent.exists()


_BAD_RECORDS = [None, [], 7, "value", {}, {"schema_version": 2}]
_BAD_FIELDS = [dict(schema_version=v) for v in (True, False, 2.0, "2", 1, 3)]
_BAD_FIELDS += [dict(token=v) for v in (None, True, 1, "", " ", "tab\ttoken", "line\ntoken", "bad\x00token", "bad\x7ftoken", "한글")]
_BAD_FIELDS += [dict(expires_at=v) for v in (None, True, "1000", float('nan'), float('inf'), -float('inf'), 10**1000)]
_BAD_FIELDS += [dict(scope_digest='0'*64), dict(extra="unexpected")]


@pytest.mark.parametrize("value", _BAD_RECORDS)
def test_non_object_and_missing_records_are_misses(context, value):
    put_raw(context, json.dumps(value).encode())
    assert cache.read_cache(context[1], context[2], NOW) is None
    assert issue(context) == (TOKEN, [True])


@pytest.mark.parametrize("changes", _BAD_FIELDS)
def test_strict_record_fields_types_scope_and_finite_values(context, changes):
    put_raw(context, json.dumps(record(context, **changes)).encode())
    assert cache.read_cache(context[1], context[2], NOW) is None
    assert issue(context) == (TOKEN, [True])


@pytest.mark.parametrize("raw", [b'\xff', b'{bad json', b'{"schema_version":2,"schema_version":2}', b'x'*(64*1024+1)])
def test_invalid_utf8_json_duplicate_keys_and_bounded_file(context, raw):
    put_raw(context, raw)
    assert cache.read_cache(context[1], context[2], NOW) is None
    assert issue(context) == (TOKEN, [True])


_BAD_RESPONSES = [None, [], True, "body", {}, {"access_token": TOKEN}, {"expires_in": 1000}]
_BAD_RESPONSES += [{"access_token": v, "expires_in": 1000} for v in (None, True, 1, "", " ", "bad token", "bad\n", "한글")]
_BAD_RESPONSES += [{"access_token": TOKEN, "expires_in": v} for v in (None, True, False, "1000", 0, -1, 60, float('nan'), float('inf'), 10**1000)]


@pytest.mark.parametrize("body", _BAD_RESPONSES)
def test_issued_raw_json_rejects_invalid_tokens_and_ttl_without_writing(context, body):
    with pytest.raises(cache.TokenCacheError) as caught:
        cache.validate_issued_response(body)
    assert_fixed(caught.value)
    calls = []
    with pytest.raises(cache.TokenCacheError):
        cache.get_token(context[0], SERVER, KEY, SECRET, NOW, lambda: (calls.append(True), body)[1])
    assert calls == [True] and not context[1].exists()
    assert list(context[1].parent.iterdir()) == []


def test_issuance_failure_and_overflow_never_retry_or_expose(context):
    calls = []
    def failed():
        calls.append(True)
        raise RuntimeError("provider-private-body "+KEY+SECRET+TOKEN+" private-path")
    with pytest.raises(cache.TokenCacheError) as caught:
        cache.get_token(context[0], SERVER, KEY, SECRET, NOW, failed)
    assert_fixed(caught.value)
    assert calls == [True] and not context[1].exists()
    with pytest.raises(cache.TokenCacheError):
        issue(context, {"access_token": TOKEN, "expires_in": 1.7e308}, now=1.7e308)
    assert not context[1].exists()


@pytest.mark.parametrize("kind", ['symlink', 'fifo', 'directory', 'hardlink', 'mode', 'parent-symlink', 'parent-mode'])
def test_unsafe_entries_are_errors_not_issuance(context, tmp_path, kind, monkeypatch):
    base, path, digest = context
    path.parent.mkdir(mode=0o700)
    sibling = tmp_path / 'sibling-marker'
    sibling.write_bytes(b'untouched-marker'); sibling.chmod(0o600)
    before = (sibling.read_bytes(), sibling.stat().st_ino)
    if kind == 'symlink': path.symlink_to(sibling)
    elif kind == 'fifo': os.mkfifo(path, 0o600)
    elif kind == 'directory': path.mkdir()
    elif kind == 'hardlink': os.link(sibling, path)
    elif kind == 'mode': path.write_bytes(b'unsafe'); path.chmod(0o644)
    elif kind == 'parent-symlink':
        path.parent.rmdir(); path.parent.symlink_to(tmp_path, target_is_directory=True)
    else: path.parent.chmod(0o777)
    opened = []
    original_open = cache.os.open
    def observe(name, *args, **kwargs):
        opened.append(str(name))
        return original_open(name, *args, **kwargs)
    calls = []
    with monkeypatch.context() as local:
        local.setattr(cache.os, 'open', observe)
        with pytest.raises(cache.TokenCacheError) as caught:
            cache.get_token(base, SERVER, KEY, SECRET, NOW, lambda: calls.append(True))
    assert_fixed(caught.value)
    assert calls == [] and path.name not in opened  # FIFO was not opened at all.
    assert (sibling.read_bytes(), sibling.stat().st_ino) == before


def test_other_uid_metadata_is_rejected_without_chown(context, monkeypatch):
    cache.write_cache(context[1], context[2], TOKEN, 1000.0)
    original = cache.os.stat
    calls = []
    def other_owner(path, *args, **kwargs):
        value = original(path, *args, **kwargs)
        if kwargs.get('dir_fd') is not None and str(path) == context[1].name:
            return SimpleNamespace(st_mode=value.st_mode, st_uid=value.st_uid+1, st_nlink=value.st_nlink)
        return value
    with monkeypatch.context() as local:
        local.setattr(cache.os, 'stat', other_owner)
        with pytest.raises(cache.TokenCacheError):
            cache.get_token(context[0], SERVER, KEY, SECRET, NOW, lambda: calls.append(True))
    assert calls == []


def test_0600_before_first_byte_and_parent_0700_even_permissive_umask(context, monkeypatch):
    original = cache.os.fdopen
    seen = []
    class Observe:
        def __init__(self, stream): self.stream = stream
        def __enter__(self): return self
        def __exit__(self, *args): return self.stream.__exit__(*args)
        def fileno(self): return self.stream.fileno()
        def flush(self): return self.stream.flush()
        def write(self, raw):
            seen.append(stat.S_IMODE(os.fstat(self.fileno()).st_mode))
            assert seen[-1] == 0o600
            return self.stream.write(raw)
    with monkeypatch.context() as local:
        local.setattr(cache.os, 'fdopen', lambda fd, mode: Observe(original(fd, mode)))
        previous = os.umask(0)
        try: cache.write_cache(context[1], context[2], TOKEN, 1000.0)
        finally: os.umask(previous)
    assert seen == [0o600]
    assert stat.S_IMODE(context[1].stat().st_mode) == 0o600
    assert stat.S_IMODE(context[1].parent.stat().st_mode) == 0o700


@pytest.mark.parametrize("operation", ['write', 'flush', 'fsync', 'replace', 'fchmod'])
def test_pre_replace_failure_preserves_exact_original_and_removes_own_temp(context, monkeypatch, operation):
    path, digest = context[1:]
    cache.write_cache(path, digest, 'old-token', 1000.0)
    before = (path.read_bytes(), path.stat().st_ino)
    fdopen = cache.os.fdopen
    class Failing:
        def __init__(self, stream): self.stream = stream
        def __enter__(self): return self
        def __exit__(self, *args): return self.stream.__exit__(*args)
        def fileno(self): return self.stream.fileno()
        def write(self, raw):
            if operation == 'write': raise OSError('private-path '+TOKEN)
            return self.stream.write(raw)
        def flush(self):
            if operation == 'flush': raise OSError('private-path '+TOKEN)
            return self.stream.flush()
    def fail(*args, **kwargs): raise OSError('private-path '+TOKEN)
    with monkeypatch.context() as local:
        if operation in ('write', 'flush'):
            local.setattr(cache.os, 'fdopen', lambda fd, mode: Failing(fdopen(fd, mode)))
        else: local.setattr(cache.os, operation, fail)
        with pytest.raises(cache.TokenCacheError) as caught:
            cache.write_cache(path, digest, TOKEN, 2000.0)
    assert_fixed(caught.value)
    assert caught.value.committed is False
    assert (path.read_bytes(), path.stat().st_ino) == before
    assert list(path.parent.iterdir()) == [path]


def test_reader_sees_complete_old_then_new_and_replace_uses_same_directory_fd(context, monkeypatch):
    path, digest = context[1:]
    cache.write_cache(path, digest, 'old-token', 1000.0)
    replace, observations = cache.os.replace, []
    def observe(src, dst, *, src_dir_fd, dst_dir_fd):
        assert src_dir_fd == dst_dir_fd and src_dir_fd is not None
        observations.append(cache.read_cache(path, digest, NOW))
        replace(src, dst, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)
        observations.append(cache.read_cache(path, digest, NOW))
    with monkeypatch.context() as local:
        local.setattr(cache.os, 'replace', observe)
        cache.write_cache(path, digest, TOKEN, 2000.0)
    assert observations == ['old-token', TOKEN]


def test_parent_replacement_fails_and_preserves_both_owned_sibling_trees(context, monkeypatch):
    path, digest = context[1:]
    cache.write_cache(path, digest, 'old-token', 1000.0)
    old = path.parent.with_name('previous-parent')
    before = (path.read_bytes(), path.stat().st_ino)
    fsync = cache.os.fsync
    def replace_parent(fd):
        fsync(fd)
        path.parent.rename(old)
        path.parent.mkdir(mode=0o700)
        (path.parent/'new-marker').write_bytes(b'preserve-new')
    with monkeypatch.context() as local:
        local.setattr(cache.os, 'fsync', replace_parent)
        with pytest.raises(cache.TokenCacheError): cache.write_cache(path, digest, TOKEN, 2000.0)
    assert ((old/path.name).read_bytes(), (old/path.name).stat().st_ino) == before
    assert list(old.iterdir()) == [old/path.name]
    assert (path.parent/'new-marker').read_bytes() == b'preserve-new'


def test_post_replace_failure_is_reported_as_committed(context, monkeypatch):
    path, digest = context[1:]
    cache.write_cache(path, digest, 'old-token', 1000.0)
    replace, entry = cache.os.replace, cache._entry
    replaced = []
    def observe(*args, **kwargs):
        replace(*args, **kwargs); replaced.append(True)
    def fail_after(fd, name):
        if replaced and name == path.name: raise OSError('private-path')
        return entry(fd, name)
    with monkeypatch.context() as local:
        local.setattr(cache.os, 'replace', observe)
        local.setattr(cache, '_entry', fail_after)
        with pytest.raises(cache.TokenCacheError) as caught: cache.write_cache(path, digest, TOKEN, 2000.0)
    assert_fixed(caught.value)
    assert caught.value.committed is True
    assert json.loads(path.read_bytes())['token'] == TOKEN


def test_write_record_limit_rejects_before_creating_parent(context):
    with pytest.raises(cache.TokenCacheError):
        cache.write_cache(context[1], context[2], 'x'*cache.MAX_BYTES, 1000.0)
    assert not context[1].parent.exists()


def test_source_closure_origin_and_no_import_time_io():
    source = _AI/'agents/flow/infrastructure/token_cache.py'
    assert Path(cache.__spec__.origin).resolve() == source.resolve()
    tree = ast.parse(source.read_text())
    modules = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    modules |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert modules == {'hashlib','json','math','os','pathlib','secrets','stat','contextlib'}
    assert all(isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef, ast.Assign))
               or isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant) for n in tree.body)
    for node in tree.body:
        if isinstance(node, ast.Assign): assert not any(isinstance(n, ast.Call) for n in ast.walk(node))
    assert not any(isinstance(n, ast.Attribute) and n.attr in {'home','getenv','environ'} for n in ast.walk(tree))


def test_kis_wiring_source_only_preserves_env_and_two_explicit_server_consumers():
    source = _AI/'agents/flow/infrastructure/kis_client.py'
    tree = ast.parse(source.read_text())
    functions = {n.name:n for n in tree.body if isinstance(n, ast.FunctionDef)}
    get = functions['_get_token']
    assert [a.arg for a in get.args.args] == ['client','app_key','app_secret','base_url']
    delegated = next(n for n in ast.walk(get) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id=='get_token')
    assert [ast.unparse(n) for n in delegated.args[:4]] == ['_TOKEN_CACHE_PATH','base_url','app_key','app_secret']
    for name in ('fetch_supply_demand', 'fetch_daily_quotes'):
        call = next(n for n in ast.walk(functions[name]) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id=='_get_token')
        assert [ast.unparse(n) for n in call.args] == ['client','app_key','app_secret','base_url']
    issue = functions['_issue_token']
    validation = next(n for n in ast.walk(issue) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id=='validate_issued_response')
    assert [ast.unparse(a) for a in validation.args] == ['body']
    assert not any(isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id=='float' for n in ast.walk(issue))
    load = functions['_load_credentials']
    dotenv = next(n for n in ast.walk(load) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id=='load_dotenv')
    assert {k.arg:ast.unparse(k.value) for k in dotenv.keywords} == {'dotenv_path':'_ENV_FILE','override':'False'}
    assert '_read_cache' not in functions and '_write_cache' not in functions
