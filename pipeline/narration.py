"""Stage: narration. One Gemini TTS call per shot line -> outputs/narration/<shot>.wav.
Only lines whose text, voice or style changed are regenerated.

Guards learned the hard way (FAILURES.md F3, F4):
- the style goes in a short "Say ...:" prefix; a long instruction was read aloud;
- audio far longer than the text can need is rejected and retried;
- each free-tier TTS model has its own daily quota, so when one is exhausted (HTTP 429)
  or keeps producing implausible audio, the next model in `fallback_models` is used.
  User test 1 heard the voice change where the model changed, so fallback_models is now
  empty: the stage stops rather than mixing voices;
- leading and trailing silence is trimmed so the edit is cut to the voice."""
from __future__ import annotations

import base64
import time
import wave

import requests

from .common import (OUT, Retryable, duration_of, ensure_dirs, ffmpeg, input_hash, is_fresh,
                     load_env, load_storyboard, log_call, mark_fresh, need, with_retries)

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
DIR = OUT / "narration"


class ModelUnusable(Exception):
    """This model cannot serve us now (quota exhausted or keeps failing); try the next one."""


def tts(text: str, model: str, cfg: dict) -> tuple[bytes, dict]:
    body = {
        "contents": [{"parts": [{"text": f"{cfg['style_instruction']}: {text}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": cfg["voice"]}}},
        },
    }

    def call():
        try:
            r = requests.post(API.format(model=model), json=body, timeout=120,
                              headers={"x-goog-api-key": need("GEMINI_API_KEY")})
        except requests.RequestException as e:
            raise Retryable(str(e))
        if r.status_code == 429:
            if "PerDay" in r.text or "per day" in r.text.lower():
                raise ModelUnusable(f"daily quota exhausted for {model}")
            raise Retryable("HTTP 429 rate limit")
        if r.status_code >= 500:
            raise Retryable(f"HTTP {r.status_code}")
        if r.status_code >= 400:
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        data = r.json()
        try:
            part = data["candidates"][0]["content"]["parts"][0]["inlineData"]
        except (KeyError, IndexError):
            raise Retryable(f"no audio in response: {str(data)[:200]}")
        return base64.b64decode(part["data"]), data.get("usageMetadata", {})

    try:
        return with_retries(call, attempts=4, base_delay=10, label=f"tts {model}")
    except Retryable as e:  # still rate-limited after backing off: give up on this model
        raise ModelUnusable(str(e))


def max_plausible_s(text: str) -> float:
    """Generous ceiling: natural Amharic narration measured at ~8 chars/s (s07, v1)."""
    return len(text) / 6 + 3


def trim_silence(path) -> None:
    tmp = path.with_name(path.stem + ".tmp.wav")
    trim = "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05"
    ffmpeg("-i", str(path), "-af", f"{trim},areverse,{trim},areverse", str(tmp))
    try:
        ok = duration_of(tmp) > 0.3
    except ValueError:
        ok = False
    if ok:
        tmp.replace(path)
    else:  # trimming removed (almost) everything: keep the original
        tmp.unlink(missing_ok=True)


def write_wav(path, pcm: bytes, rate: int = 24000) -> None:
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)


def speak(sid: str, text: str, model: str, cfg: dict) -> tuple[bytes, float]:
    """Up to 3 tries on one model; implausibly long audio is logged as rejected."""
    params = {"voice": cfg["voice"], "chars": len(text)}
    for i in range(1, 4):
        t0 = time.time()
        pcm, usage = tts(text, model, cfg)
        secs = len(pcm) / 2 / 24000
        if secs <= max_plausible_s(text):
            log_call("narration", model, params=params, shot=sid, latency_s=time.time() - t0,
                     extra={"audio_s": round(secs, 2), "usage": usage})
            return pcm, secs
        log_call("narration", model, params=params, shot=sid, latency_s=time.time() - t0,
                 status="rejected", error=f"audio {secs:.1f}s > plausible {max_plausible_s(text):.1f}s",
                 extra={"audio_s": round(secs, 2), "usage": usage})
        print(f"  [{sid}] {model}: {secs:.1f}s for {len(text)} chars, rejected (try {i}/3)")
    raise ModelUnusable(f"{model} kept returning implausible audio")


def run(only: set[str] | None = None) -> None:
    load_env()
    sb = load_storyboard()
    cfg = sb["models"]["tts"]
    models = [cfg["model"], *cfg.get("fallback_models", [])]
    unusable: set[str] = set()
    ensure_dirs(DIR)
    for shot in sb["shots"]:
        sid, text = shot["id"], shot["narration"].strip()
        if (only and sid not in only) or not text:
            continue
        out = DIR / f"{sid}.wav"
        # the cache key is what determines the sound: text, model, voice, style
        h = input_hash(text, cfg["model"], cfg["voice"], cfg["style_instruction"])
        if is_fresh(out, h):
            print(f"  narration {sid}: cached")
            continue
        t0 = time.time()
        for model in models:
            if model in unusable:
                continue
            try:
                pcm, secs = speak(sid, text, model, cfg)
                break
            except ModelUnusable as e:
                unusable.add(model)
                log_call("narration", model, shot=sid, latency_s=time.time() - t0,
                         status="error", error=str(e))
                print(f"  [{sid}] {e}; switching model")
        else:
            raise SystemExit(f"narration {sid}: every TTS model failed ({', '.join(models)}). "
                             "Wait for the quota to reset or add a model to fallback_models.")
        write_wav(out, pcm)
        trim_silence(out)
        mark_fresh(out, h)
        print(f"  narration {sid}: {model}, {duration_of(out):.1f}s audio in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    import sys
    run(set(sys.argv[1:]) or None)
