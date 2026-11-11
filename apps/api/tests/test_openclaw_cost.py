import datetime as dt

from tutor.notify import Notifier
from tutor.scheduler import OPENCLAW_TURN_USD, _send
from tutor.settings import Settings
from tutor.store import Store


class FakeOpenClaw(Notifier):
    name = "openclaw"

    def send(self, text):
        return True


class FakeNtfy(Notifier):
    name = "ntfy"

    def send(self, text):
        return True


NOW = dt.datetime(2026, 10, 5, 10, 0)


def test_openclaw_reminder_counts_toward_the_monthly_spend(tmp_path):
    store, s = Store(tmp_path / "t.db"), Settings(tmp_path).get()
    assert _send(store, FakeOpenClaw(), s, NOW, "late", "hi")
    assert store.month_cost_usd("2026-10") == OPENCLAW_TURN_USD


def test_plain_channels_cost_nothing(tmp_path):
    store, s = Store(tmp_path / "t.db"), Settings(tmp_path).get()
    assert _send(store, FakeNtfy(), s, NOW, "late", "hi")
    assert store.month_cost_usd("2026-10") == 0
