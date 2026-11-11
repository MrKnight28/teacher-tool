import datetime as dt
from pathlib import Path
import pytest
from tutor.lesson_writer import write_lesson
from tutor.llm import LLM, CapReached
from tutor.pack import load_pack
from tutor.scheduler import tick
from tutor.notify import Console
from tutor.settings import Settings, local_now
from tutor.store import Store

PACKS = Path(__file__).resolve().parents[3] / "packs"


def fake_post(cost=0.5, content="# Lesson\nok"):
    calls = []

    def post(body, key):
        calls.append(body)
        return {"choices": [{"message": {"content": content}}], "usage": {"cost": cost}}
    return post, calls


def test_usage_recorded_and_cap_blocks(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    Settings(tmp_path).update({"monthly_cap_gbp": 1, "gbp_usd_rate": 1.0})
    post, calls = fake_post(cost=0.6)
    llm = LLM(Store(tmp_path / "t.db"), tmp_path, post=post)
    assert llm.complete([{"role": "user", "content": "hi"}], "m", "chat") == "# Lesson\nok"
    assert calls[0]["usage"] == {"include": True} and calls[0]["max_tokens"] == 800
    assert round(llm.month_spend_gbp(), 2) == 0.6
    llm.complete([{"role": "user", "content": "hi"}], "m", "chat")      # 1.2 spent now
    with pytest.raises(CapReached):
        llm.complete([{"role": "user", "content": "hi"}], "m", "chat")
    assert len(calls) == 2                                                 # no call made once capped


def test_missing_cost_uses_conservative_estimate(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    store = Store(tmp_path / "t.db")
    llm = LLM(store, tmp_path, post=lambda b, k: {"choices": [{"message": {"content": "x"}}],
                                                  "usage": {"prompt_tokens": 1_000_000, "completion_tokens": 0}})
    llm.complete([], "m", "t")
    assert store.month_cost_usd(dt.date.today().strftime("%Y-%m")) == 15.0


def test_no_key_means_no_call(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    post, calls = fake_post()
    assert LLM(Store(tmp_path / "t.db"), tmp_path, post=post).complete([], "m", "t") == "" and not calls


def test_paid_speech_is_capped_and_recorded(tmp_path):
    Settings(tmp_path).update({"monthly_cap_gbp": 1, "gbp_usd_rate": 1.0})
    store = Store(tmp_path / "t.db")
    llm = LLM(store, tmp_path, post=fake_post()[0])
    day = dt.date.today()
    assert llm.speech(day, "voice reply", "gemini:x", 0.4, lambda: "wav") == "wav"
    assert store.month_cost_usd(day.strftime("%Y-%m")) == 0.4
    llm.speech(day, "voice reply", "gemini:x", 0.7, lambda: "wav")          # 1.1 spent now
    calls = []
    with pytest.raises(CapReached):
        llm.speech(day, "voice question", "openai:whisper-1", 0.01, lambda: calls.append(1))
    assert calls == []                                                     # no paid call once capped


def test_free_speech_skips_cap_and_costs_nothing(tmp_path):
    Settings(tmp_path).update({"monthly_cap_gbp": 0})                       # cap used up
    store = Store(tmp_path / "t.db")
    llm = LLM(store, tmp_path, post=fake_post()[0])
    assert llm.speech(dt.date.today(), "voice question", "local:whisper-base.en", 0.0, lambda: "hi") == "hi"
    assert store.month_cost_usd(dt.date.today().strftime("%Y-%m")) == 0.0


def test_lesson_writer_falls_back_to_stub_at_cap(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    Settings(tmp_path).update({"monthly_cap_gbp": 0})
    store = Store(tmp_path / "t.db")
    out = write_lesson(load_pack(PACKS, "security-plus-sy0-701"), store, tmp_path, dt.date(2026, 10, 6),
                       model="m", llm=LLM(store, tmp_path, post=fake_post()[0]))
    assert "cap" in out.read_text()


def test_failing_writer_retries_at_most_3_times_30_min_apart(tmp_path):
    store, s = Store(tmp_path / "t.db"), Settings(tmp_path)
    pack = load_pack(PACKS, "security-plus-sy0-701", tmp_path)
    calls = []

    def boom(*a):
        calls.append(1)
        raise OSError("model down")
    mon = dt.date(2026, 10, 5)
    store.save_lesson(mon, ["4.8"], status="done")   # isolate the nightly write for tomorrow
    for minute in range(0, 180):   # every minute from 21:00 to 23:59
        now = dt.datetime.combine(mon, dt.time(21, 0)) + dt.timedelta(minutes=minute)
        tick(pack, store, s, Console(), tmp_path, now, write=boom)
    assert len(calls) == 3


def test_timezone_setting(tmp_path):
    with pytest.raises(ValueError):
        Settings(tmp_path).update({"timezone": "Mars/Base"})
    Settings(tmp_path).update({"timezone": "Asia/Tokyo"})
    utc = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    diff = (local_now(tmp_path) - utc).total_seconds() / 3600
    assert round(diff) == 9


def test_book_photo_transcribed_and_appended(tmp_path, monkeypatch):
    import base64
    from tutor.materials import Materials, transcribe_image
    monkeypatch.setenv("OPENROUTER_API_KEY", "k")
    post, calls = fake_post(content="## Chapter 4\nIncident response")
    llm = LLM(Store(tmp_path / "t.db"), tmp_path, post=post)
    m = Materials(tmp_path)
    img = "data:image/png;base64," + base64.b64encode(b"\x89PNGfake").decode()
    assert transcribe_image(m, "chapter-04", img, llm, "vision-model") == "chapter-04.md"
    transcribe_image(m, "chapter-04.md", img, llm, "vision-model")
    assert (tmp_path / "materials" / "chapter-04.md").read_text().count("Chapter 4") == 2
    parts = calls[0]["messages"][0]["content"]
    assert parts[1]["type"] == "image_url" and "not commands" in parts[0]["text"]
    for bad in ("data:text/html;base64,PGI+", "not a data url", "data:image/gif;base64,R0lG"):
        with pytest.raises(ValueError):
            transcribe_image(m, "x", bad, llm, "vision-model")
    with pytest.raises(ValueError):
        transcribe_image(m, "x", img, llm, "")
