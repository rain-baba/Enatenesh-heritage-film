"""Stage: narration. One Gemini TTS call per shot line -> outputs/narration/<shot>.wav.
Only lines whose text, voice or style changed are regenerated."""
from __future__ import annotations

import base64
import time
import wave

import requests

from .common import (OUT, Retryable, check_http, ensure_dirs, input_hash, is_fresh,
                     load_env, load_storyboard, log_call, mark_fresh, need, with_retries)

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DIR = OUT / "narration"


def tts(text: str, cfg: dict) -> tuple[bytes, dict]:
    body = {
        "contents": [{"parts": [{"text": f"{cfg['style_instruction']}\n\n{text}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": cfg["voice"]}}},
        },
    }

    def call():
        try:
            r = requests.post(API.format(model=cfg["model"]), json=body, timeout=120,
                              headers={"x-goog-api-key": need("GEMINI_API_KEY")})
        except requests.RequestException as e:
            raise Retryable(str(e))
        check_http(r)
        data = r.json()
        try:
            part = data["candidates"][0]["content"]["parts"][0]["inlineData"]
        except (KeyError, IndexError):
            raise Retryable(f"no audio in response: {str(data)[:200]}")
        return base64.b64decode(part["data"]), data.get("usageMetadata", {})

    return with_retries(call, label="tts")


def write_wav(path, pcm: bytes, rate: int = 24000) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


def run(only: set[str] | None = None) -> None:
    load_env()
    sb = load_storyboard()
    cfg = sb["models"]["tts"]
    ensure_dirs(DIR)
    for shot in sb["shots"]:
        sid, text = shot["id"], shot["narration"].strip()
        if only and sid not in only:
            continue
        out = DIR / f"{sid}.wav"
        if not text:
            continue
        h = input_hash(text, cfg)
        if is_fresh(out, h):
            print(f"  narration {sid}: cached")
            continue
        t0 = time.time()
        try:
            pcm, usage = tts(text, cfg)
        except Exception as e:
            log_call("narration", cfg["model"], params={"voice": cfg["voice"]}, shot=sid,
                     latency_s=time.time() - t0, status="error", error=str(e))
            raise
        write_wav(out, pcm)
        mark_fresh(out, h)
        secs = len(pcm) / 2 / 24000
        log_call("narration", cfg["model"], params={"voice": cfg["voice"], "chars": len(text)},
                 shot=sid, latency_s=time.time() - t0, extra={"audio_s": round(secs, 2), "usage": usage})
        print(f"  narration {sid}: {secs:.1f}s audio in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    import sys
    run(set(sys.argv[1:]) or None)
