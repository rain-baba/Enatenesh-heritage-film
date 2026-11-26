"""Stage: references and keyframes on Cloudflare Workers AI (FLUX.2 klein).

1. One reference image per character (the "character sheet"), from its sheet_prompt.
2. One keyframe per shot, conditioned on the reference images of the characters
   in that shot, with the style block and character descriptions in every prompt.

Outputs: outputs/refs/<char>.png, outputs/keyframes/<shot>.png
"""
from __future__ import annotations

import base64
import io
import time
from pathlib import Path

import requests
from PIL import Image

from .common import (OUT, Retryable, check_http, ensure_dirs, file_sha, input_hash, is_fresh,
                     load_env, load_storyboard, log_call, mark_fresh, need, with_retries)

URL = "https://api.cloudflare.com/client/v4/accounts/{acct}/ai/run/{model}"
REFS = OUT / "refs"
KEYS = OUT / "keyframes"


def _ref_bytes(path: Path) -> bytes:
    """Workers AI wants reference images under 512x512."""
    im = Image.open(path).convert("RGB")
    im.thumbnail((511, 511))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def generate(prompt: str, seed: int, cfg: dict, refs: list[Path]) -> bytes:
    url = URL.format(acct=need("CLOUDFLARE_ACCOUNT_ID"), model=cfg["model"])
    headers = {"Authorization": f"Bearer {need('CLOUDFLARE_API_TOKEN')}"}
    multipart = "flux-2" in cfg["model"]

    def call():
        try:
            if multipart:
                fields = {"prompt": (None, prompt), "seed": (None, str(seed)),
                          "width": (None, str(cfg["width"])), "height": (None, str(cfg["height"]))}
                for i, p in enumerate(refs[:4]):
                    fields[f"input_image_{i}"] = (p.name, _ref_bytes(p), "image/png")
                r = requests.post(url, headers=headers, files=fields, timeout=120)
            else:  # FLUX.1 schnell: JSON, no references
                r = requests.post(url, headers=headers, timeout=120,
                                  json={"prompt": prompt, "seed": seed, "steps": 8})
        except requests.RequestException as e:
            raise Retryable(str(e))
        check_http(r)
        res = r.json().get("result", {})
        img = res.get("image") if isinstance(res, dict) else None
        if not img:
            raise Retryable(f"no image in response: {r.text[:200]}")
        return base64.b64decode(img)

    return with_retries(call, label="flux")


def _save_png(raw: bytes, out: Path) -> None:
    Image.open(io.BytesIO(raw)).convert("RGB").save(out, "PNG")


def _one(kind: str, key: str, prompt: str, seed: int, cfg: dict, refs: list[Path], out: Path) -> None:
    h = input_hash(prompt, seed, cfg, [file_sha(p) for p in refs])
    if is_fresh(out, h):
        print(f"  {kind} {key}: cached")
        return
    t0 = time.time()
    try:
        raw = generate(prompt, seed, cfg, refs)
    except Exception as e:
        log_call(kind, cfg["model"], params={"prompt": prompt}, seed=seed, shot=key,
                 latency_s=time.time() - t0, status="error", error=str(e))
        raise
    _save_png(raw, out)
    mark_fresh(out, h)
    log_call(kind, cfg["model"], seed=seed, shot=key, latency_s=time.time() - t0,
             params={"prompt": prompt, "width": cfg["width"], "height": cfg["height"],
                     "refs": [p.name for p in refs]})
    print(f"  {kind} {key}: {time.time() - t0:.1f}s")


def build_prompt(sb: dict, shot: dict, refs: list[str]) -> str:
    chars = {c["id"]: c for c in sb["style"]["characters"]}
    parts = []
    if refs:
        parts.append(" ".join(f"Image {i} shows the {cid}." for i, cid in enumerate(refs))
                     + " Keep each character's face, hair, clothing and proportions exactly as in the reference images.")
    parts.append(shot["image_prompt"])
    for cid in shot["characters"]:
        parts.append(f"The {cid}: {chars[cid]['description']}")
    parts.append(sb["style"]["style_block"])
    parts.append("Subject centered in the frame. No text, no letters, no watermark.")
    return " ".join(parts)


def run(only: set[str] | None = None) -> None:
    load_env()
    sb = load_storyboard()
    cfg = sb["models"]["image"]
    ensure_dirs(REFS, KEYS)

    # 1. character references (sheet) first
    for c in sb["style"]["characters"]:
        prompt = f"{c['sheet_prompt']} {c['description']} {sb['style']['style_block']} Plain background. No text."
        _one("reference", c["id"], prompt, c["seed"], cfg, [], REFS / f"{c['id']}.png")

    # 2. keyframes conditioned on references
    use_refs = cfg.get("use_references", True)
    for shot in sb["shots"]:
        if only and shot["id"] not in only:
            continue
        ref_ids = shot["characters"] if use_refs else []
        prompt = build_prompt(sb, shot, ref_ids)
        _one("keyframe", shot["id"], prompt, shot["seed"], cfg,
             [REFS / f"{cid}.png" for cid in ref_ids], KEYS / f"{shot['id']}.png")


if __name__ == "__main__":
    import sys
    run(set(sys.argv[1:]) or None)
