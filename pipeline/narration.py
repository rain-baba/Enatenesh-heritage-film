"""Stage: narration. One Gemini TTS call per shot line -> outputs/narration/<shot>.wav.
Only lines whose text, voice or style changed are regenerated.

Guards learned from radio cut v1: the style goes in a short "Say ...:" prefix (a long
instruction was read aloud), audio far longer than the text can need is rejected and
retried, and leading/trailing silence is trimmed so the edit is cut to the voice."""
from __future__ import annotations

import base64
import time
import wave

import requests

from .common import (OUT, Retryable, check_http, duration_of, ensure_dirs, ffmpeg, input_hash,
                     is_fresh, load_env, load_storyboard, log_call, mark_fresh, need, with_retries)

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DIR = OUT / "narration"


def tts(text: str, cfg: dict) -> tuple[bytes, dict]:
    body = {
        "contents": [{"parts": [{"text": f"{cfg['style_instruction']}: {text}"}]}],
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


def max_plausible_s(text: str) -> float:
    """Generous ceiling: even slow Amharic narration runs faster than 6 chars/s."""
    return len(text) / 6 + 3


def trim_silence(path) -> None:
    tmp = path.with_name(path.stem + ".tmp.wav")
    trim = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05"
    ffmpeg("-i", str(path), "-af", f"{trim},areverse,{trim},areverse", str(tmp))
    tmp.replace(path)


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

        def attempt():
            pcm, usage = tts(text, cfg)
            secs = len(pcm) / 2 / 24000
            if secs > max_plausible_s(text):
                log_call("narration", cfg["model"], params={"voice": cfg["voice"], "chars": len(text)},
                         shot=sid, latency_s=time.time() - t0, status="rejected",
                         error=f"audio {secs:.1f}s > plausible {max_plausible_s(text):.1f}s",
                         extra={"audio_s": round(secs, 2), "usage": usage})
                raise Retryable(f"{secs:.1f}s of audio for {len(text)} chars")
            return pcm, usage, secs

        try:
            pcm, usage, secs = with_retries(attempt, attempts=3, base_delay=2, label=f"tts {sid}")
        except Exception as e:
            log_call("narration", cfg["model"], params={"voice": cfg["voice"]}, shot=sid,
                     latency_s=time.time() - t0, status="error", error=str(e))
            raise
        write_wav(out, pcm)
        trim_silence(out)
        mark_fresh(out, h)
        trimmed = duration_of(out)
        log_call("narration", cfg["model"], params={"voice": cfg["voice"], "chars": len(text)},
                 shot=sid, latency_s=time.time() - t0,
                 extra={"audio_s": round(secs, 2), "trimmed_s": round(trimmed, 2), "usage": usage})
        print(f"  narration {sid}: {trimmed:.1f}s audio in {time.time() - t0:.1f}s")

if __name__ == "__main__":
    import sys
    run(set(sys.argv[1:]) or None)
