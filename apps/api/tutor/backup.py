"""Nightly backup of the data folder (progress, lessons, materials, settings) to a mounted folder. Keeps 14."""
from __future__ import annotations
import datetime as dt
import sqlite3
import zipfile
from pathlib import Path

KEEP = 14


def backup(data_dir: Path, dest: Path, day: dt.date, keep: int = KEEP) -> Path:
    data_dir, dest = Path(data_dir), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / f"teacher-tool-{day}.zip"
    tmp = out.with_suffix(".tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(data_dir.rglob("*")):
            if not p.is_file():
                continue
            if p.suffix == ".db":  # consistent snapshot of the live database
                snap = dest / ".snapshot.db"
                src = sqlite3.connect(str(p))
                dst = sqlite3.connect(str(snap))
                src.backup(dst)
                src.close(); dst.close()
                z.write(snap, p.relative_to(data_dir).as_posix())
                snap.unlink()
            else:
                z.write(p, p.relative_to(data_dir).as_posix())
    tmp.replace(out)
    try:
        out.chmod(0o600)   # transcripts, chat and recordings: owner only
    except OSError:
        pass
    for old in sorted(dest.glob("teacher-tool-*.zip"))[:-keep]:
        old.unlink()
    return out
