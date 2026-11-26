"""Call each hosted provider once and log latency to runs.jsonl.

    python -m pipeline.smoke_test

Also lists the Gemini models your key can see, so you can confirm the exact
text and TTS model ids before putting them in storyboard.json."""
from __future__ import annotations

import base64
import time

import requests

from .common import OUT, ensure_dirs, load_env, log_call, need


def gemini_models() -> None:
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200",
                     headers={"x-goog-api-key": need("GEMINI_API_KEY")}, timeout=30)
    r.raise_for_status()
    names = [m["name"].split("/")[-1] for m in r.json().get("models", [])]
    print("  Gemini text models:", ", ".join(n for n in names if "flash" in n and "tts" not in n and "image" not in n))
    print("  Gemini TTS models: ", ", ".join(n for n in names if "tts" in n))


def gemini_text(model: str) -> None:
    t0 = time.time()
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                      headers={"x-goog-api-key": need("GEMINI_API_KEY")}, timeout=60,
                      json={"contents": [{"parts": [{"text": "Translate to Amharic: my world"}]}]})
    ok = r.ok
    log_call("smoke", model, latency_s=time.time() - t0, status="ok" if ok else "error",
             error=None if ok else r.text, extra={"usage": r.json().get("usageMetadata", {}) if ok else {}})
    print(f"  text {model}: {'ok' if ok else r.status_code} in {time.time() - t0:.1f}s",
          r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()[:60] if ok else r.text[:200])


def gemini_tts(model: str, voice: str) -> None:
    from .narration import write_wav
    t0 = time.time()
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                      headers={"x-goog-api-key": need("GEMINI_API_KEY")}, timeout=120,
                      json={"contents": [{"parts": [{"text": "Say warmly in Amharic: ሰላም፣ እንኳን ደህና መጣችሁ።"}]}],
                            "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
                                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}}}})
    ok = r.ok
    log_call("smoke", model, params={"voice": voice}, latency_s=time.time() - t0,
             status="ok" if ok else "error", error=None if ok else r.text)
    if ok:
        ensure_dirs(OUT / "smoke")
        pcm = base64.b64decode(r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]["data"])
        write_wav(OUT / "smoke" / "tts.wav", pcm)
    print(f"  tts {model}: {'ok -> outputs/smoke/tts.wav' if ok else r.status_code} in {time.time() - t0:.1f}s",
          "" if ok else r.text[:200])


def cloudflare(model: str) -> None:
    t0 = time.time()
    url = f"https://api.cloudflare.com/client/v4/accounts/{need('CLOUDFLARE_ACCOUNT_ID')}/ai/run/{model}"
    headers = {"Authorization": f"Bearer {need('CLOUDFLARE_API_TOKEN')}"}
    prompt = "a small clay pot on a wooden table, warm morning light, painterly"
    if "flux-2" in model:
        r = requests.post(url, headers=headers, timeout=120,
                          files={"prompt": (None, prompt), "seed": (None, "1"),
                                 "width": (None, "512"), "height": (None, "512")})
    else:
        r = requests.post(url, headers=headers, timeout=120, json={"prompt": prompt, "steps": 4})
    ok = r.ok and bool(r.json().get("result", {}).get("image"))
    log_call("smoke", model, seed=1, latency_s=time.time() - t0, status="ok" if ok else "error",
             error=None if ok else r.text)
    if ok:
        ensure_dirs(OUT / "smoke")
        (OUT / "smoke" / "flux.jpg").write_bytes(base64.b64decode(r.json()["result"]["image"]))
    print(f"  image {model}: {'ok -> outputs/smoke/flux.jpg' if ok else r.status_code} in {time.time() - t0:.1f}s",
          "" if ok else r.text[:200])


def main() -> None:
    load_env()
    import json
    from .common import STORYBOARD
    sb = json.loads(STORYBOARD.read_text(encoding="utf-8"))
    m = sb["models"]
    for name, fn in [("gemini models", gemini_models),
                     ("gemini text", lambda: gemini_text(m["text"]["model"])),
                     ("gemini tts", lambda: gemini_tts(m["tts"]["model"], m["tts"]["voice"])),
                     ("cloudflare", lambda: cloudflare(m["image"]["model"]))]:
        print(name)
        try:
            fn()
        except Exception as e:
            print(f"  FAILED: {e}")


if __name__ == "__main__":
    main()
