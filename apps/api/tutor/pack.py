"""Load a course pack (config, objectives, soul) from disk."""
from __future__ import annotations
import datetime as dt
from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass
class Pack:
    root: Path
    config: dict
    domains: dict[int, dict]
    objectives: list[dict]
    soul: str

    def objective(self, oid: str) -> dict:
        for o in self.objectives:
            if o["id"] == oid:
                return o
        raise KeyError(oid)

    def domain_weight(self, oid: str) -> float:
        return float(self.domains[int(oid.split(".")[0])]["weight"])

    def is_study_day(self, day: dt.date) -> bool:
        names = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        if names[day.weekday()] in self.config.get("rest_days", []):
            return False
        for r in self.config.get("pause_ranges", []):
            if r["start"] <= day <= r["end"]:
                return False
        if self.config.get("paused"):
            return False
        exam = self.config.get("exam_date")
        return not (exam and day >= exam)


def load_pack(packs_dir: Path, pack_id: str, data_dir: Path | None = None) -> Pack:
    root = Path(packs_dir) / pack_id
    config = yaml.safe_load((root / "pack.yaml").read_text())
    obj = yaml.safe_load((root / config["objectives_file"]).read_text())
    soul = (root / config["soul_file"]).read_text()
    if data_dir is not None:
        from .settings import Settings
        so = Path(data_dir) / "soul.md"
        if so.exists():
            soul = so.read_text()
        st = Settings(data_dir).get()
        config["rest_days"], config["lesson_time"] = st["rest_days"], st["lesson_time"]
        config["paused"] = st["paused"]
        # Saved dates (wizard or admin panel) override the pack's defaults.
        if st["exam_date"]:
            config["exam_date"] = dt.date.fromisoformat(st["exam_date"])
        if st["pause_start"] is not None:  # "" means no trip pause at all
            config["pause_ranges"] = ([] if not st["pause_start"] else
                                      [{"start": dt.date.fromisoformat(st["pause_start"]),
                                        "end": dt.date.fromisoformat(st["pause_end"] or st["pause_start"])}])
    pack =Pack(root, config, {d["id"]: d for d in obj["domains"]}, obj["objectives"], soul)
    for o in pack.objectives:  # fail early on a broken pack
        pack.domain_weight(o["id"])
    return pack
