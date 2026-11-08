"""Scoped KIS token storage. Stdlib only; no import-time I/O or credential discovery.

The caller supplies the base path, exact credentials, server, clock and issuer.
This protects against unsafe cache entries and partial writes, not malicious
same-uid processes, issuance races or power-loss directory durability.
"""

import hashlib
import json
import math
import os
from pathlib import Path
import secrets
import stat
from contextlib import contextmanager

MAX_BYTES = 64 * 1024
MARGIN_SECONDS = 60


class TokenCacheError(RuntimeError):
    def __init__(self, *, committed=False):
        self.committed = committed
        super().__init__("KIS token cache update failed after replacement." if committed
                         else "KIS token cache operation failed.")


def _number(value):
    if type(value) not in (int, float):
        raise ValueError
    result = float(value)
    if not math.isfinite(result):
        raise ValueError
    return result


def _token(value):
    if type(value) is not str or not value or len(value) > MAX_BYTES:
        raise ValueError
    if not all(33 <= ord(char) <= 126 for char in value):
        raise ValueError
    return value


def _digest(value):
    if type(value) is not str or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError
    return value


def scope_digest(base_url, app_key, app_secret):
    try:
        if any(type(value) is not str or not value for value in (base_url, app_key, app_secret)):
            raise ValueError
        raw = json.dumps(["verith-kis-token-v2", base_url.rstrip("/"), app_key, app_secret],
                         ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
    except Exception:
        raise TokenCacheError() from None


def scoped_path(base_path, digest):
    try:
        _digest(digest)
        base = Path(base_path)
        if not base.name or ".." in base.parts:
            raise ValueError
        return base.with_name(base.stem + "." + digest + base.suffix)
    except Exception:
        raise TokenCacheError() from None


def validate_issued_response(body):
    """Validate original JSON types before conversion; never invent a lifetime."""
    try:
        if type(body) is not dict:
            raise ValueError
        token, lifetime = _token(body["access_token"]), _number(body["expires_in"])
        if lifetime <= MARGIN_SECONDS:
            raise ValueError
        return token, lifetime
    except Exception:
        raise TokenCacheError() from None


def _safe_file(info):
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600):
        raise TokenCacheError()


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


@contextmanager
def _directory(parent, *, create):
    """Check the explicit component chain; open only the caller's directory.

    Metadata checks never enumerate ancestors. Recheck identities around the
    no-follow directory open, then do entry I/O relative to that directory FD.
    """
    parent = Path(parent)
    if ".." in parent.parts:
        raise TokenCacheError()
    parent = Path(os.path.abspath(parent))
    chain = [*reversed(parent.parents), parent]
    identities = []
    for component in chain:
        try:
            info = component.lstat()
        except FileNotFoundError:
            if not create:
                raise
            try:
                os.mkdir(component, 0o700)
            except FileExistsError:
                pass
            info = component.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise TokenCacheError()
        identities.append((info.st_dev, info.st_ino))
    fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) & 0o022
                or (info.st_dev, info.st_ino) != identities[-1]):
            raise TokenCacheError()
        for component, expected in zip(chain, identities):
            current = component.lstat()
            if not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != expected:
                raise TokenCacheError()
        yield fd
    finally:
        os.close(fd)


def _same_directory(parent, fd):
    try:
        with _directory(parent, create=False) as current:
            a, b = os.fstat(current), os.fstat(fd)
            if (a.st_dev, a.st_ino) != (b.st_dev, b.st_ino):
                raise TokenCacheError()
    except Exception:
        raise TokenCacheError() from None


def _entry(fd, name):
    try:
        info = os.stat(name, dir_fd=fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    _safe_file(info)  # Reject FIFO/device/directory before any potentially blocking open.
    return info


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError


def _read(fd, name, digest, now):
    before = _entry(fd, name)
    if before is None:
        return None
    try:
        raw_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=fd)
    except Exception:
        raise TokenCacheError() from None
    try:
        opened = os.fstat(raw_fd)
        _safe_file(opened)
        if _identity(opened) != _identity(before):
            raise TokenCacheError()
        with os.fdopen(raw_fd, "rb") as source:
            raw_fd = None
            raw = source.read(MAX_BYTES + 1)
            after = os.fstat(source.fileno())
        current = _entry(fd, name)
        if current is None or _identity(after) != _identity(before) or _identity(current) != _identity(before):
            raise TokenCacheError()
    finally:
        if raw_fd is not None:
            os.close(raw_fd)
    if len(raw) > MAX_BYTES:
        return None
    try:
        data = json.loads(raw.decode("utf-8"), object_pairs_hook=_object, parse_constant=_invalid_constant)
        if type(data) is not dict or set(data) != {"schema_version", "scope_digest", "token", "expires_at"}:
            return None
        if type(data["schema_version"]) is not int or data["schema_version"] != 2:
            return None
        if data["scope_digest"] != digest:
            return None
        token, expires = _token(data["token"]), _number(data["expires_at"])
        return token if now < expires - MARGIN_SECONDS else None
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError):
        return None


def read_cache(path, digest, now):
    try:
        now = _number(now)
        _digest(digest)
        path = Path(path)
        try:
            with _directory(path.parent, create=False) as fd:
                result = _read(fd, path.name, digest, now)
                _same_directory(path.parent, fd)
                return result
        except FileNotFoundError:
            return None
    except Exception:
        raise TokenCacheError() from None


def _record_bytes(digest, token, expires_at):
    raw = json.dumps({"schema_version": 2, "scope_digest": _digest(digest),
                      "token": _token(token), "expires_at": _number(expires_at)},
                     separators=(",", ":"), allow_nan=False).encode("utf-8")
    if len(raw) > MAX_BYTES:
        raise TokenCacheError()
    return raw


def _write(fd, path, raw):
    before = _entry(fd, path.name)
    name = ".kis-token-" + secrets.token_hex(16) + ".tmp"
    raw_fd = None
    temporary = None
    committed = False
    try:
        raw_fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
                         | os.O_NONBLOCK | os.O_CLOEXEC, 0o600, dir_fd=fd)
        temporary = os.fstat(raw_fd)
        os.fchmod(raw_fd, 0o600)  # Mandatory, before the first token byte.
        _safe_file(os.fstat(raw_fd))
        with os.fdopen(raw_fd, "wb") as output:
            raw_fd = None
            if output.write(raw) != len(raw):
                raise TokenCacheError()
            output.flush()
            os.fsync(output.fileno())
            temporary = os.fstat(output.fileno())
        _same_directory(path.parent, fd)
        current = _entry(fd, path.name)
        if (None if current is None else _identity(current)) != (None if before is None else _identity(before)):
            raise TokenCacheError()
        candidate = _entry(fd, name)
        if candidate is None or _identity(candidate) != _identity(temporary):
            raise TokenCacheError()
        os.replace(name, path.name, src_dir_fd=fd, dst_dir_fd=fd)
        committed = True
        final = _entry(fd, path.name)
        if final is None or _identity(final) != _identity(temporary):
            raise TokenCacheError(committed=True)
        return True
    except Exception:
        raise TokenCacheError(committed=committed) from None
    finally:
        if raw_fd is not None:
            os.close(raw_fd)
        if not committed and temporary is not None:
            # Only this invocation's exact temp inode; never unlink a replacement.
            current = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if (current.st_dev, current.st_ino) == (temporary.st_dev, temporary.st_ino):
                os.unlink(name, dir_fd=fd)


def write_cache(path, digest, token, expires_at):
    committed = False
    try:
        raw = _record_bytes(digest, token, expires_at)
        path = Path(path)
        with _directory(path.parent, create=True) as fd:
            committed = _write(fd, path, raw)
    except TokenCacheError as error:
        raise TokenCacheError(committed=error.committed) from None
    except Exception:
        raise TokenCacheError(committed=committed) from None


def get_token(base_path, base_url, app_key, app_secret, now, issuer):
    """Cache first. At most one issuer call; unsafe I/O never becomes a miss."""
    committed = False
    try:
        now = _number(now)
        digest = scope_digest(base_url, app_key, app_secret)
        path = scoped_path(base_path, digest)
        with _directory(path.parent, create=True) as fd:
            cached = _read(fd, path.name, digest, now)
            _same_directory(path.parent, fd)
            if cached is not None:
                return cached
            token, lifetime = validate_issued_response(issuer())
            expires = _number(now + lifetime)
            committed = _write(fd, path, _record_bytes(digest, token, expires))
            return token
    except TokenCacheError as error:
        raise TokenCacheError(committed=error.committed) from None
    except Exception:
        raise TokenCacheError(committed=committed) from None
