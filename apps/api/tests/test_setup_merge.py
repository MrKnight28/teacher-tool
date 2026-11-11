import json

from tutor.setup_core import _merge, apply, recommend


def test_merge_overlays_owned_keys_and_keeps_the_rest():
    old = {"hooks": {"token": "old", "path": "/hooks", "custom": 1}, "channels": {"whatsapp": {"dmPolicy": "open"}},
           "user": {"theme": "dark"}}
    new = {"hooks": {"token": "new", "path": "/hooks"}, "channels": {"whatsapp": {"dmPolicy": "allowlist"}}}
    out = _merge(old, new)
    assert out["hooks"] == {"token": "new", "path": "/hooks", "custom": 1}
    assert out["channels"]["whatsapp"]["dmPolicy"] == "allowlist"
    assert out["user"] == {"theme": "dark"}


def test_rerun_setup_keeps_keys_the_user_added(tmp_path):
    form = {"use_whatsapp": "on", "whatsapp_to": "+447700900000"}
    apply(tmp_path, form, recommend([]))
    cfg_path = tmp_path / "openclaw" / "config" / "openclaw.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["myNote"] = "keep me"
    cfg_path.write_text(json.dumps(cfg))
    apply(tmp_path, form, recommend([]))
    again = json.loads(cfg_path.read_text())
    assert again["myNote"] == "keep me"
    assert again["channels"]["whatsapp"]["allowFrom"] == ["+447700900000"]
