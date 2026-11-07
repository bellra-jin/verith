"""Env-free project-copy and local-port preparation; no DB/login/process runner.

The interactive DB ownership guard is intentionally not implemented here pending
the instruction author's decision. Imports/direct execution do not read secrets,
copy projects, contact Google, create containers, or start application processes.
"""

from __future__ import annotations
from dataclasses import dataclass, field
import os
from pathlib import Path
import shutil
import socket
import tempfile


class LoginPreparationError(RuntimeError):
    pass


def child_base_environment() -> dict[str, str]:
    """Allowlist only: never inherit parent app/Google/DB/Node options."""
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "LANG": "en_US.UTF-8",
        "TZ": "UTC",
        "NEXT_TELEMETRY_DISABLED": "1",
        "PYTHONNOUSERSITE": "1",
    }


def ensure_local_ports_free(*, socket_factory=socket.socket) -> None:
    """Probe both loopback families without reuse, then close only own sockets.

    Availability is a point-in-time check, not a promise/reservation for a later
    child process. A bind failure never causes another process to be terminated.
    """
    sockets = []
    try:
        for port in (3200, 8200):
            for family, host in (
                (socket.AF_INET, "127.0.0.1"),
                (socket.AF_INET6, "::1"),
            ):
                handle = socket_factory(family, socket.SOCK_STREAM)
                sockets.append(handle)
                handle.bind((host, port))
    except OSError:
        raise LoginPreparationError(
            "Required local verification port is unavailable"
        ) from None
    finally:
        for handle in sockets:
            handle.close()


_FRONTEND_ROOT_FILES = frozenset(
    {
        "package.json",
        "package-lock.json",
        "tsconfig.json",
        "next.config.ts",
        "postcss.config.mjs",
        "eslint.config.mjs",
    }
)
_PUBLIC_ASSETS = frozenset(
    {"window.svg", "globe.svg", "next.svg", "vercel.svg", "file.svg"}
)
_FRONTEND_SOURCE_ROOTS = frozenset(
    {"app", "api", "components", "features", "lib", "types", "utils"}
)
_PRIVATE_PARTS = (
    "private",
    "credential",
    "client_secret",
    "backup",
    "dump",
    "session.log",
    ".key",
    ".pem",
    ".sql",
    ".log",
)


def _allowed_file(relative: Path, project: str) -> bool:
    parts = relative.parts
    lowered = relative.name.lower()
    if any(word in lowered for word in _PRIVATE_PARTS):
        return False
    if project == "backend":
        return relative.as_posix() in {
            "alembic.ini",
            "db/migrations/script.py.mako",
        } or (parts[0] in {"src", "db"} and relative.suffix == ".py")
    if len(parts) == 1:
        return relative.name in _FRONTEND_ROOT_FILES
    if parts[0] == "public":
        return len(parts) == 2 and relative.name in _PUBLIC_ASSETS
    if parts[0] == "src":
        return (
            (len(parts) > 2 and parts[1] in _FRONTEND_SOURCE_ROOTS)
            or relative.as_posix() == "src/proxy.ts"
        ) and relative.suffix in {".ts", ".tsx", ".css", ".ico"}
    return False


def _copy_entry(
    source: Path, destination: Path, *, project_root: Path, project: str
) -> None:
    if source.name.startswith(".env") or source.name in {
        ".git",
        ".venv",
        "node_modules",
        ".next",
        "__pycache__",
    }:
        return
    if source.is_symlink():
        raise LoginPreparationError(
            "Source symlinks are not allowed in an env-free project copy"
        )
    relative = source.relative_to(project_root)
    if source.is_dir():
        if source.name.lower() in {
            "credentials",
            "secrets",
            "keys",
            "backups",
            "dumps",
            "logs",
        }:
            raise LoginPreparationError(
                "Non-source material is outside the project-copy allowlist"
            )
        destination.mkdir()
        for entry in source.iterdir():
            _copy_entry(
                entry,
                destination / entry.name,
                project_root=project_root,
                project=project,
            )
    elif (
        source.is_file()
        and (source.name in {".gitkeep", ".DS_Store"} or source.suffix == ".md")
        and not any(word in source.name.lower() for word in _PRIVATE_PARTS)
    ):
        return
    elif source.is_file() and _allowed_file(relative, project):
        shutil.copyfile(source, destination)
    else:
        raise LoginPreparationError(
            "Non-source material is outside the project-copy allowlist"
        )


@dataclass
class PreparedProjects:
    root: Path
    backend: Path
    frontend: Path
    _identity: tuple[int, int] = field(repr=False)
    _parent: Path = field(repr=False)

    def cleanup(self) -> None:
        if not self.root.exists() and not self.root.is_symlink():
            return
        metadata = self.root.lstat()
        if (
            self.root.is_symlink()
            or self.root.parent != self._parent
            or not self.root.name.startswith(".cf002-google-check-")
            or (metadata.st_dev, metadata.st_ino) != self._identity
        ):
            raise LoginPreparationError(
                "Refusing cleanup of an unowned verification workspace"
            )
        shutil.rmtree(
            self.root
        )  # Does not follow the known node_modules dependency symlink.


def prepare_projects(
    repository: Path, *, temporary_parent: Path | None = None
) -> PreparedProjects:
    """Copy only source/build config. Existing private files are never opened.

    Backend src/db are actual copies, since symlinks would make Path.resolve()
    select the original backend/.env. Node dependencies alone may be linked.
    This creates no DB and is not a credential-use authorization or app launcher.
    """
    repository = repository.resolve()
    parent = (temporary_parent or repository.parent).resolve()
    root = Path(tempfile.mkdtemp(prefix=".cf002-google-check-", dir=parent))
    metadata = root.lstat()
    prepared = PreparedProjects(
        root,
        root / "backend",
        root / "frontend",
        (metadata.st_dev, metadata.st_ino),
        parent,
    )
    try:
        for name, entries in {
            "backend": ("src", "db", "alembic.ini"),
            "frontend": (
                "src",
                "public",
                "package.json",
                "package-lock.json",
                "tsconfig.json",
                "next.config.ts",
                "postcss.config.mjs",
                "eslint.config.mjs",
            ),
        }.items():
            target = root / name
            target.mkdir()
            for entry in entries:
                source = repository / name / entry
                if source.exists() or source.is_symlink():
                    _copy_entry(
                        source,
                        target / entry,
                        project_root=repository / name,
                        project=name,
                    )
        for required in (
            prepared.backend / "src/api/config.py",
            prepared.backend / "db/migrations/env.py",
            prepared.frontend / "next.config.ts",
            prepared.frontend / "package.json",
        ):
            if not required.is_file():
                raise LoginPreparationError(
                    "Required verification project source is missing"
                )
        # Explicitly disable the temporary Backend dotenv source before any app import.
        backend_config = prepared.backend / "src/api/config.py"
        text = backend_config.read_text()
        if text.count("s = Settings()") != 1:
            raise LoginPreparationError("Unexpected Backend settings entry")
        backend_config.write_text(
            text.replace("s = Settings()", "s = Settings(_env_file=None)", 1)
        )
        dependencies = repository / "frontend/node_modules"
        if not dependencies.is_dir():
            raise LoginPreparationError("Existing Frontend dependencies are required")
        (prepared.frontend / "node_modules").symlink_to(
            dependencies, target_is_directory=True
        )
        config = prepared.frontend / "next.config.ts"
        original = config.read_text()
        marker = "const nextConfig: NextConfig = {"
        if original.count(marker) != 1 or "turbopack:" in original:
            raise LoginPreparationError(
                "Unexpected Next config; review the temporary root before proceeding"
            )
        import json

        common_root = os.path.commonpath((str(root), str(repository)))
        config.write_text(
            original.replace(
                marker,
                marker + "\n  turbopack: {root: " + json.dumps(common_root) + "},",
                1,
            )
        )
        return prepared
    except Exception:
        prepared.cleanup()
        raise


if __name__ == "__main__":
    raise SystemExit(
        "Preparation library only: no private input, application, database or Google action executed"
    )
