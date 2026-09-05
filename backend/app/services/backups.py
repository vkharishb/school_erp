import asyncio
import hashlib
import os
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import unquote, urlparse

from app.core.config import get_settings

settings = get_settings()


def _db_env() -> dict[str, str]:
    raw = settings.database_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlparse(raw)
    env = os.environ.copy()
    env["PGHOST"] = parsed.hostname or "localhost"
    env["PGPORT"] = str(parsed.port or 5432)
    if parsed.username:
        env["PGUSER"] = unquote(parsed.username)
    if parsed.password:
        env["PGPASSWORD"] = unquote(parsed.password)
    env["PGDATABASE"] = parsed.path.lstrip("/")
    query = parsed.query.lower()
    if "sslmode=require" in query or "ssl=require" in query:
        env["PGSSLMODE"] = "require"
    return env


def _secure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        path.chmod(0o700)
    except OSError:
        pass
    return path


def _backup_dir() -> Path:
    return _secure_dir(Path(settings.backup_dir).resolve())


def _offsite_backup_dir() -> Path | None:
    raw = (settings.backup_offsite_dir or "").strip()
    if not raw:
        return None
    path = Path(raw).resolve()
    if path == _backup_dir():
        raise RuntimeError("BACKUP_OFFSITE_DIR must be different from BACKUP_DIR")
    return _secure_dir(path)


def _safe_backup_path(name: str) -> Path:
    if not name or Path(name).name != name or not name.endswith(".dump"):
        raise ValueError("Invalid backup name")
    directory = _backup_dir()
    path = (directory / name).resolve()
    if path.parent != directory:
        raise ValueError("Invalid backup path")
    return path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_checksum(path: Path, sha256: str) -> None:
    checksum_path = path.with_suffix(path.suffix + ".sha256")
    checksum_path.write_text(f"{sha256}  {path.name}\n", encoding="utf-8")
    try:
        checksum_path.chmod(0o600)
    except OSError:
        pass


def _resolve_executable(command: str) -> str:
    candidate = Path(command)
    if candidate.is_absolute() or candidate.parent != Path("."):
        if candidate.exists() and candidate.is_file():
            return str(candidate)
        raise RuntimeError(f"Backup executable not found: {command}")
    resolved = shutil.which(command)
    if not resolved:
        setting = "PG_RESTORE_PATH" if "restore" in command.lower() else "PG_DUMP_PATH"
        raise RuntimeError(
            f"{command} was not found on PATH. Set {setting} to the PostgreSQL executable path."
        )
    return resolved


def _run_blocking(args: tuple[str, ...], timeout: int) -> tuple[str, str]:
    command = (_resolve_executable(args[0]), *args[1:])
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            env=_db_env(),
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"Backup command timed out after {timeout} seconds") from exc
    except OSError as exc:
        raise RuntimeError(f"Unable to start backup command: {exc}") from exc

    stdout = completed.stdout.decode(errors="replace")
    stderr = completed.stderr.decode(errors="replace")
    if completed.returncode != 0:
        message = stderr.strip()[-2000:]
        raise RuntimeError(message or f"Command failed with status {completed.returncode}")
    return stdout, stderr


async def _run(*args: str, timeout: int = 900) -> tuple[str, str]:
    # Portable across Windows/Linux ASGI event loops.
    return await asyncio.to_thread(_run_blocking, tuple(args), timeout)


def backup_metadata(path: Path) -> dict:
    stat = path.stat()
    return {
        "name": path.name,
        "size_bytes": stat.st_size,
        "sha256": sha256_file(path),
        "created_at": datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
    }


def list_backups() -> list[dict]:
    return [
        backup_metadata(p)
        for p in sorted(
            _backup_dir().glob("schoolerp_*.dump"), key=lambda x: x.stat().st_mtime, reverse=True
        )
    ]


def _dump_files(directory: Path) -> list[Path]:
    return sorted(directory.glob("schoolerp_*.dump"), key=lambda x: x.stat().st_mtime, reverse=True)


def prune_backups(retain: int) -> None:
    files = _dump_files(_backup_dir())
    for path in files[max(retain, 1) :]:
        path.unlink(missing_ok=True)
        path.with_suffix(path.suffix + ".sha256").unlink(missing_ok=True)


def _month_distance(now: datetime, value: datetime) -> int:
    return (now.year - value.year) * 12 + now.month - value.month


def prune_offsite_backups() -> None:
    """Keep tiered off-site recovery points: daily, weekly and monthly.

    Only the newest backup in each UTC day/week/month bucket is retained for the
    configured horizon. The newest off-site backup is always preserved.
    """
    directory = _offsite_backup_dir()
    if not directory:
        return
    files = _dump_files(directory)
    if not files:
        return
    now = datetime.now(UTC)
    keep: set[Path] = {files[0]}
    daily: set[tuple[int, int]] = set()
    weekly: set[tuple[int, int]] = set()
    monthly: set[tuple[int, int]] = set()
    for path in files:
        created = datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
        age_days = (now.date() - created.date()).days
        iso = created.isocalendar()
        if 0 <= age_days < settings.backup_daily_retention_days:
            key = (created.year, created.timetuple().tm_yday)
            if key not in daily:
                daily.add(key)
                keep.add(path)
        age_weeks = age_days // 7
        if 0 <= age_weeks < settings.backup_weekly_retention_weeks:
            key = (iso.year, iso.week)
            if key not in weekly:
                weekly.add(key)
                keep.add(path)
        if 0 <= _month_distance(now, created) < settings.backup_monthly_retention_months:
            key = (created.year, created.month)
            if key not in monthly:
                monthly.add(key)
                keep.add(path)
    for path in files:
        if path not in keep:
            path.unlink(missing_ok=True)
            path.with_suffix(path.suffix + ".sha256").unlink(missing_ok=True)


def _sync_offsite(path: Path, sha256: str) -> dict:
    directory = _offsite_backup_dir()
    if not directory:
        return {"configured": False, "synced": False}
    target = directory / path.name
    shutil.copy2(path, target)
    _write_checksum(target, sha256)
    if sha256_file(target) != sha256:
        target.unlink(missing_ok=True)
        target.with_suffix(target.suffix + ".sha256").unlink(missing_ok=True)
        raise RuntimeError("Off-site backup checksum verification failed after copy")
    prune_offsite_backups()
    return {"configured": True, "synced": True, "path": str(target)}


async def create_backup(*, label: str = "manual") -> dict:
    _backup_dir()
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    safe_label = "".join(c for c in label.lower() if c.isalnum() or c in "-_")[:24] or "manual"
    name = f"schoolerp_{stamp}_{safe_label}.dump"
    path = _safe_backup_path(name)
    await _run(
        settings.pg_dump_path,
        "--format=custom",
        "--no-owner",
        "--no-privileges",
        "--file",
        str(path),
    )
    try:
        path.chmod(0o600)
    except OSError:
        pass
    item = backup_metadata(path)
    _write_checksum(path, item["sha256"])
    offsite_error = None
    try:
        offsite = await asyncio.to_thread(_sync_offsite, path, item["sha256"])
    except Exception as exc:  # local backup remains a valid recovery point
        offsite = {"configured": bool((settings.backup_offsite_dir or "").strip()), "synced": False}
        offsite_error = str(exc)[-500:]
    prune_backups(settings.backup_retention_count)
    return {**item, "offsite": offsite, "offsite_error": offsite_error}


def get_backup_path(name: str) -> Path:
    path = _safe_backup_path(name)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(name)
    return path


def delete_backup(name: str) -> None:
    path = get_backup_path(name)
    path.unlink()
    path.with_suffix(path.suffix + ".sha256").unlink(missing_ok=True)


def has_recent_successful_backup(max_age_hours: int | None = None) -> bool:
    items = list_backups()
    if not items:
        return False
    max_age = max_age_hours or settings.archive_backup_max_age_hours
    latest = datetime.fromisoformat(items[0]["created_at"])
    return datetime.now(UTC) - latest <= timedelta(hours=max_age)


def backup_status() -> dict:
    local = list_backups()
    offsite_dir = _offsite_backup_dir()
    offsite_files = _dump_files(offsite_dir) if offsite_dir else []
    return {
        "last_local_backup": local[0]["created_at"] if local else None,
        "local_count": len(local),
        "offsite_configured": offsite_dir is not None,
        "offsite_count": len(offsite_files),
        "last_offsite_backup": datetime.fromtimestamp(
            offsite_files[0].stat().st_mtime, tz=UTC
        ).isoformat()
        if offsite_files
        else None,
        "recent_backup_ready_for_archive": has_recent_successful_backup(),
        "archive_backup_max_age_hours": settings.archive_backup_max_age_hours,
        "retention": {
            "local_latest": settings.backup_retention_count,
            "daily_days": settings.backup_daily_retention_days,
            "weekly_weeks": settings.backup_weekly_retention_weeks,
            "monthly_months": settings.backup_monthly_retention_months,
        },
    }


async def restore_backup(name: str, expected_sha256: str) -> dict:
    path = get_backup_path(name)
    actual = sha256_file(path)
    if not expected_sha256 or actual.lower() != expected_sha256.lower():
        raise ValueError("Backup checksum verification failed")
    safety = await create_backup(label="pre-restore")
    await _run(
        settings.pg_restore_path,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        "--exit-on-error",
        "--dbname",
        _db_env()["PGDATABASE"],
        str(path),
        timeout=1800,
    )
    return {"restored": name, "sha256": actual, "safety_backup": safety["name"]}
