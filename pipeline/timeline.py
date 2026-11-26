"""The edit is cut to the voice: each shot lasts as long as its narration line
plus padding (never less than min_shot_s). Shots and assembly both use this."""
from __future__ import annotations

from .common import OUT, duration_of


def build(sb: dict) -> list[dict]:
    t = sb["timing"]
    cur = 0.0
    rows = []
    for shot in sb["shots"]:
        wav = OUT / "narration" / f"{shot['id']}.wav"
        voice = duration_of(wav) if shot["narration"].strip() and wav.exists() else 0.0
        dur = max(t["min_shot_s"], shot.get("min_duration_s", 0),
                  t["pad_before_s"] + voice + t["pad_after_s"])
        rows.append({
            "id": shot["id"], "start": round(cur, 3), "duration": round(dur, 3),
            "voice_start": round(cur + t["pad_before_s"], 3), "voice_len": round(voice, 3),
            "wav": wav if voice else None, "subtitle": shot["subtitle_en"],
        })
        cur += dur
    return rows


def total(rows: list[dict]) -> float:
    return rows[-1]["start"] + rows[-1]["duration"] if rows else 0.0
