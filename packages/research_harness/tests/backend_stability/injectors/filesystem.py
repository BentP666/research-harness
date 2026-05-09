"""Filesystem fault injectors.

- readonly_path: chmod a directory to 0o555 so writes raise PermissionError
- path_too_long: expose a temp path that exceeds POSIX PATH_MAX
- missing_pdf:   symlink a paper's pdf_path to /nonexistent
- disk_full:     patch ``os.write``/``Path.write_text`` to raise ENOSPC

These are coarse: on macOS some fail modes (true ENOSPC on real FS) are
hard to force without a tmpfs. Prefer monkeypatch where the real syscall
is painful to set up.
"""

from __future__ import annotations

import contextlib
import errno
import os
from collections.abc import Iterator
from pathlib import Path

import pytest


@contextlib.contextmanager
def readonly_path(path: Path) -> Iterator[Path]:
    """chmod ``path`` to 0o555, restore on exit. Path must already exist."""
    if not path.exists():
        raise FileNotFoundError(path)
    original = path.stat().st_mode
    os.chmod(path, 0o555)
    try:
        yield path
    finally:
        os.chmod(path, original)


@contextlib.contextmanager
def disk_full_on_write(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Patch Path.write_text and Path.write_bytes to raise ENOSPC.

    Uses pytest monkeypatch so fixtures can pass their own instance. Does
    NOT touch os.write globally — that would break pytest itself.
    """
    original_text = Path.write_text
    original_bytes = Path.write_bytes

    def _enospc(*args, **kwargs):  # noqa: ANN002,ANN003 — signature passthrough
        raise OSError(errno.ENOSPC, "simulated disk full")

    monkeypatch.setattr(Path, "write_text", _enospc)
    monkeypatch.setattr(Path, "write_bytes", _enospc)
    try:
        yield
    finally:
        monkeypatch.setattr(Path, "write_text", original_text)
        monkeypatch.setattr(Path, "write_bytes", original_bytes)


@contextlib.contextmanager
def missing_pdf(db_path_override: Path | None = None) -> Iterator[Path]:
    """Yield a nonexistent path that looks like a valid pdf_path.

    Callers use the returned path to mutate a paper row, then let the
    code under test try to read it — it should report missing_pdf, not
    crash.
    """
    fake = Path(db_path_override or "/tmp/rh-never-exists-xyzzy.pdf")
    if fake.exists():
        fake.unlink()
    try:
        yield fake
    finally:
        if fake.exists():
            fake.unlink()


__all__ = ["readonly_path", "disk_full_on_write", "missing_pdf"]
