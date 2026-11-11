import datetime as dt
from pathlib import Path
from tutor.notify import Console, Fallback, Notifier
from tutor.pack import load_pack
from tutor.scheduler import tick, _in_quiet
from tutor.settings import Settings
from tutor.store import Store

PACKS = Path(__file__).resolve().parents[3] / "packs"
MON = dt.date(2026, 10, 5)


def setup(tmp_path, **changes):
    s = Settings(tmp_path)
    if changes:
        s.update(changes)
    store = Store(tmp_path / "t.db")
    return load_pack(PACKS, "security-plus-sy0-701", tmp_path), store, s, Console()


def at(h, m=0, day=MON):
    return dt.datetime.combine(day, dt.time(h, m))


def run(p, store, s, n, tmp_path, now):
    return tick(p, store, s, n, tmp_path, now, write=lambda *a: None)


def test_reminder_then_late_ladder_then_missed(tmp_path):
    p, store, s, n = setup(tmp_path)
    store.save_lesson(MON, ["4.8", "2.4"])
    assert run(p, store, s, n, tmp_path, at(8, 40)) == []          # too early
    assert run(p, store, s, n, tmp_path, at(8, 50)) == ["reminder"]
    assert run(p, store, s, n, tmp_path, at(8, 55)) == []          # no duplicate
    assert run(p, store, s, n, tmp_path, at(9, 6)) == ["late_5"]
    assert run(p, store, s, n, tmp_path, at(9, 21)) == ["late_20"]
    assert run(p, store, s, n, tmp_path, at(9, 30)) == []
    assert run(p, store, s, n, tmp_path, at(10, 0)) == ["missed"]
    assert store.lesson(MON)["status"] == "missed"
    assert store.missed_objectives(MON + dt.timedelta(days=1)) == ["4.8", "2.4"]
    assert len(n.sent) == 4 and "4.8" in n.sent[0]


def test_no_nudges_once_started(tmp_path):
    p, store, s, n = setup(tmp_path)
    store.save_lesson(MON, ["4.8"], status="started")
    assert run(p, store, s, n, tmp_path, at(9, 30)) == []
    assert run(p, store, s, n, tmp_path, at(11, 0)) == []
    assert store.lesson(MON)["status"] == "started"


def test_daily_cap_quiet_hours_pause_and_rest_days(tmp_path):
    p, store, s, n = setup(tmp_path, max_messages_per_day=1)
    store.save_lesson(MON, ["4.8"])
    assert run(p, store, s, n, tmp_path, at(8, 50)) == ["reminder"]
    assert run(p, store, s, n, tmp_path, at(9, 6)) == []            # cap of 1 reached
    assert _in_quiet(at(23), "22:00", "07:00") and _in_quiet(at(6), "22:00", "07:00")
    assert not _in_quiet(at(9), "22:00", "07:00")
    p2, store2, s2, n2 = setup(tmp_path / "b", paused=True)
    store2.save_lesson(MON, ["4.8"])
    assert run(p2, store2, s2, n2, tmp_path, at(9, 30)) == []
    sat = dt.date(2026, 10, 10)
    p3, store3, s3, n3 = setup(tmp_path / "c")
    store3.save_lesson(sat, ["4.8"])
    assert run(p3, store3, s3, n3, tmp_path, at(9, 30, sat)) == []


def test_nightly_writes_tomorrow_once_and_skips_rest_days(tmp_path):
    p, store, s, n = setup(tmp_path, checkin_time="")   # the evening check-in is tested in test_whatsapp.py
    calls = []

    def fake_write(pack, st, d, day):
        calls.append(day)
        st.save_lesson(day, ["1.1"])
        return d / "x.md"
    store.save_lesson(MON, ["4.8"], status="done")       # today's lesson already exists
    assert tick(p, store, s, n, tmp_path, at(20, 59), write=fake_write) == []
    assert tick(p, store, s, n, tmp_path, at(21, 0), write=fake_write) == ["wrote_lesson"]
    assert tick(p, store, s, n, tmp_path, at(22, 0), write=fake_write) == []
    assert calls == [MON + dt.timedelta(days=1)]
    fri = dt.date(2026, 10, 9)
    store.save_lesson(fri, ["4.8"], status="done")
    assert tick(p, store, s, n, tmp_path, at(21, 0, fri), write=fake_write) == []   # Saturday is a rest day


def test_tone_changes_wording(tmp_path):
    p, store, s, n = setup(tmp_path, tone="strict")
    store.save_lesson(MON, ["4.8"])
    run(p, store, s, n, tmp_path, at(8, 50))
    assert "days away" in n.sent[0]


def test_fallback_channel_used_when_first_fails(tmp_path):
    class Down(Notifier):
        def send(self, text):
            return False
    c = Console()
    assert Fallback([Down(), c]).send("hi") and c.sent == ["hi"]
    assert not Fallback([Down()]).send("hi")


def test_failed_send_is_retried_next_tick(tmp_path):
    class Flaky(Notifier):
        def __init__(self):
            self.n = 0

        def send(self, text):
            self.n += 1
            return self.n > 1
    p, store, s, _ = setup(tmp_path)
    store.save_lesson(MON, ["4.8"])
    f = Flaky()
    assert tick(p, store, s, f, tmp_path, at(8, 50), write=lambda *a: None) == []
    assert tick(p, store, s, f, tmp_path, at(8, 51), write=lambda *a: None) == ["reminder"]


def test_openclaw_hook_payload(monkeypatch):
    import json as _j
    from tutor import notify
    seen = {}

    class R:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def read(self, *a): return b'{"ok": true, "runId": "x"}'

    def fake_open(req, timeout):
        seen["url"], seen["body"], seen["auth"] = req.full_url, _j.loads(req.data), req.headers["Authorization"]
        return R()
    monkeypatch.setattr(notify.urllib.request, "urlopen", fake_open)
    assert notify.OpenClawHook("http://openclaw:18789/", "hooktok", "+447700900000").send("Lesson at 09:00")
    assert seen["url"] == "http://openclaw:18789/hooks/agent" and seen["auth"] == "Bearer hooktok"
    b = seen["body"]
    assert b["deliver"] is True and b["channel"] == "whatsapp" and b["to"] == "+447700900000"
    assert "Lesson at 09:00" in b["message"]


def test_nightly_backup_once_per_day(tmp_path):
    p, store, s, n = setup(tmp_path)
    bk = tmp_path / "bk"
    assert "backup" not in tick(p, store, s, n, tmp_path, at(1, 59), write=lambda *a: None, backup_dir=bk)
    assert "backup" in tick(p, store, s, n, tmp_path, at(2, 0), write=lambda *a: None, backup_dir=bk)
    assert "backup" not in tick(p, store, s, n, tmp_path, at(2, 1), write=lambda *a: None, backup_dir=bk)
    assert len(list(bk.glob("*.zip"))) == 1
    assert store.sent_count(MON) == 0          # backups don't use up the daily message cap



def test_catch_up_writes_todays_missing_lesson_without_nagging(tmp_path):
    p, store, s, n = setup(tmp_path)
    calls = []

    def fake_write(pack, st, d, day):
        calls.append(day)
        st.save_lesson(day, ["4.8"])
        return d / "x.md"
    assert tick(p, store, s, n, tmp_path, at(11, 47), write=fake_write) == ["wrote_today"]
    assert calls == [MON]
    assert tick(p, store, s, n, tmp_path, at(12, 30), write=fake_write) == []   # no 'missed' for a late catch-up
    assert store.lesson(MON)["status"] == "planned" and n.sent == []


def test_catch_up_before_lesson_time_still_gets_reminders(tmp_path):
    p, store, s, n = setup(tmp_path)
    def fake_write(pack, st, d, day):
        st.save_lesson(day, ["4.8"])
        return d / "x.md"
    assert tick(p, store, s, n, tmp_path, at(7, 30), write=fake_write) == ["wrote_today"]
    assert tick(p, store, s, n, tmp_path, at(8, 50), write=fake_write) == ["reminder"]


def test_write_failure_is_recorded_with_reason(tmp_path):
    p, store, s, n = setup(tmp_path)
    def boom(*a):
        raise OSError("HTTP Error 402: Payment Required")
    r = tick(p, store, s, n, tmp_path, at(10, 0), write=boom)
    assert r and r[0].startswith("write_failed") and "402" in r[0]
    assert "402" in store.events(1)[0]["detail"] and store.events(1)[0]["kind"] == "write_failed"


def test_the_store_waits_for_a_lock_instead_of_failing(tmp_path):
    from tutor.store import Store
    assert Store(tmp_path / "t.db").db.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
