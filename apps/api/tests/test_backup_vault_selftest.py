import datetime as dt
import zipfile
from pathlib import Path
from tutor.backup import backup
from tutor.pack import load_pack
from tutor.selftest import run_checks
from tutor.server import App
from tutor.store import Store

PACKS = Path(__file__).resolve().parents[3] / "packs"


def test_backup_zips_data_and_keeps_14(tmp_path):
    data = tmp_path / "data"
    store = Store(data / "progress.db")
    store.save_lesson(dt.date(2026, 10, 5), ["4.8"])
    (data / "materials").mkdir()
    (data / "materials" / "n.md").write_text("notes")
    dest = tmp_path / "bk"
    for i in range(16):
        out = backup(data, dest, dt.date(2026, 10, 1) + dt.timedelta(days=i))
    assert len(list(dest.glob("teacher-tool-*.zip"))) == 14
    names = zipfile.ZipFile(out).namelist()
    assert "progress.db" in names and "materials/n.md" in names
    assert not list(dest.glob("*.tmp")) and not list(dest.glob(".snapshot.db"))


def test_vault_note_written_only_to_tutor_folder(tmp_path, monkeypatch):
    vault = tmp_path / "Tutor"
    vault.mkdir()
    monkeypatch.setenv("TUTOR_VAULT_DIR", str(vault))
    store = Store(tmp_path / "t.db")
    day = dt.date(2026, 10, 6)
    store.save_lesson(day, ["4.8"])
    app = App(load_pack(PACKS, "security-plus-sy0-701"), store, tmp_path, token="t")
    assert app.finish(day, "IR phases were hard")
    note = (vault / f"{day} Security+.md").read_text()
    assert "4.8 Explain appropriate incident response activities" in note and "IR phases were hard" in note
    assert [p.name for p in vault.iterdir()] == [f"{day} Security+.md"]


def test_vault_missing_is_harmless(tmp_path, monkeypatch):
    monkeypatch.setenv("TUTOR_VAULT_DIR", str(tmp_path / "nope"))
    store = Store(tmp_path / "t.db")
    store.save_lesson(dt.date(2026, 10, 6), ["4.8"])
    assert App(load_pack(PACKS, "security-plus-sy0-701"), store, tmp_path, token="t").finish(dt.date(2026, 10, 6), "x")


def test_selftest_checks(tmp_path, monkeypatch):
    for k in ("OPENROUTER_API_KEY", "MODEL_PLAN", "MODEL_TEACH", "MODEL_MARK", "OPENCLAW_HOOK_URL", "NTFY_URL",
              "NOTIFY_WEBHOOK_URL", "GEMINI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("TUTOR_BACKUP_DIR", str(tmp_path))
    c = {x["name"]: x for x in run_checks(tmp_path)}
    assert c["Data folder"]["ok"] and c["Backup folder"]["ok"]
    assert not c["OpenRouter"]["ok"] and not c["Models"]["ok"] and not c["Reminder channel"]["ok"]
    monkeypatch.setenv("TUTOR_BACKUP_DIR", str(tmp_path / "missing" / "dir"))
    assert not {x["name"]: x for x in run_checks(tmp_path)}["Backup folder"]["ok"]


def test_backup_zip_is_owner_only(tmp_path):
    import os
    import stat
    if os.name == "nt":
        return
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "notes.json").write_text("[]")
    out = backup(tmp_path / "data", tmp_path / "dest", dt.date(2026, 10, 7))
    assert stat.S_IMODE(out.stat().st_mode) == 0o600
