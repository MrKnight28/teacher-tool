"""Admin page data: the settings form, benchmark results, the setup commands, and spend."""
from __future__ import annotations
import os
from ..bench import sttbench as SB
from .. import timing as T
from .. import tts as TT
from ..bench import voicebench as VB


class AdminMixin:
    def setup_info(self):
        ts = os.environ.get("TS_HOSTNAME")
        return {
            "tailscale_url": f"https://{ts}.<your-tailnet>.ts.net" if ts else "",
            "whatsapp_to": os.environ.get("WHATSAPP_TO", ""),
            "commands": {
                "rerun_setup_windows": ".\\setup.ps1",
                "rerun_setup_linux": "./setup.sh",
                "repair_whatsapp": "docker compose --profile whatsapp --profile whatsapp-cli run --rm openclaw-cli channels login --channel whatsapp",
                "logs": "docker compose logs -f --tail 100",
            },
        }

    def admin_state(self):
        # Show the dates in effect (saved setting or pack default), so the form never looks blank.
        s, ranges = self.settings.get(), self.pack.config.get("pause_ranges") or []
        s.update(exam_date=str(self.pack.config.get("exam_date") or ""),
                 pause_start=str(ranges[0]["start"]) if ranges else "",
                 pause_end=str(ranges[0]["end"]) if ranges else "")
        return {"soul": self.soul, "context": self.context, "settings": s,
                "materials": self.materials.list(),
                "voicebench": VB.last_result(self.data), "sttbench": SB.last_result(self.data),
                "timings": T.recent(), "tts": TT.ready(), "chains": T.chains_summary(),
                "spend": {"month_gbp": round(self.llm.month_spend_gbp(), 2), "remaining_gbp": round(self.llm.remaining_gbp(), 2)}}
