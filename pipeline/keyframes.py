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
CANDS = OUT / "candidates"
CANDIDATE_SEEDS = 3


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
        if r.status_code == 400 and '"code":3030' in r.text.replace(" ", ""):
            raise Flagged(r.text[:300])
        check_http(r)
        res = r.json().get("result", {})
        img = res.get("image") if isinstance(res, dict) else None
        if not img:
            raise Retryable(f"no image in response: {r.text[:200]}")
        return base64.b64decode(img)

    return with_retries(call, label="flux")


def _save_png(raw: bytes, out: Path) -> None:
    Image.open(io.BytesIO(raw)).convert("RGB").save(out, "PNG")


class Flagged(Exception):
    """The provider's safety filter rejected the output (Cloudflare error 3030)."""


SEED_STEP = 1000  # on a flagged output, try seed, seed+1000, seed+2000


def _one(kind: str, key: str, prompt: str, seed: int, cfg: dict, refs: list[Path], out: Path) -> bool:
    """Generate one image unless cached. Returns False if every seed was flagged."""
    h = input_hash(prompt, seed, cfg, [file_sha(p) for p in refs])
    if is_fresh(out, h):
        print(f"  {kind} {key}: cached")
        return True
    params = {"prompt": prompt, "width": cfg["width"], "height": cfg["height"], "refs": [p.name for p in refs]}
    for s in (seed, seed + SEED_STEP, seed + 2 * SEED_STEP):
        t0 = time.time()
        try:
            raw = generate(prompt, s, cfg, refs)
        except Flagged as e:
            log_call(kind, cfg["model"], params=params, seed=s, shot=key, latency_s=time.time() - t0,
                     status="flagged", error=str(e))
            print(f"  {kind} {key}: seed {s} flagged by the safety filter, trying another seed")
            continue
        except Exception as e:
            log_call(kind, cfg["model"], params=params, seed=s, shot=key, latency_s=time.time() - t0,
                     status="error", error=str(e))
            raise
        _save_png(raw, out)
        mark_fresh(out, h)
        log_call(kind, cfg["model"], seed=s, shot=key, latency_s=time.time() - t0, params=params)
        print(f"  {kind} {key}: {time.time() - t0:.1f}s (seed {s})")
        return True
    print(f"  {kind} {key}: FLAGGED on 3 seeds; rephrase its prompt in storyboard.json")
    return False


def shot_cfg(cfg: dict, shot: dict) -> dict:
    """The stage's image config, with this shot's model override if it has one."""
    return {**cfg, "model": shot["image_model"]} if "image_model" in shot else cfg


def build_prompt(sb: dict, shot: dict, refs: list[str]) -> str:
    chars = {c["id"]: c for c in sb["style"]["characters"]}
    outfits = shot.get("outfits", {})
    parts = []
    if refs:
        keep = ("face, hair and proportions as in the reference images; clothing as described"
                if outfits else "face, hair, clothing and proportions exactly as in the reference images")
        parts.append(" ".join(f"Image {i} shows the {cid}." for i, cid in enumerate(refs))
                     + f" Keep each character's {keep}.")
    parts.append(shot["image_prompt"])
    for cid in shot["characters"]:
        desc = chars[cid]["description"]
        if cid in outfits:  # swap the clothing clause for this shot only
            desc = desc.split(", wearing")[0] + f", wearing {outfits[cid]}"
        parts.append(f"The {cid}: {desc}")
    parts.append(sb["style"]["style_block"])
    parts.append("Subject centered in the frame. No text, no letters, no watermark.")
    return " ".join(parts)


def run(only: set[str] | None = None) -> None:
    load_env()
    sb = load_storyboard()
    cfg = sb["models"]["image"]
    ensure_dirs(REFS, KEYS)

    failed = []
    # 1. character references (sheet) first
    for c in sb["style"]["characters"]:
        prompt = f"{c['sheet_prompt']} {c['description']} {sb['style']['style_block']} Plain background. No text."
        if not _one("reference", c["id"], prompt, c["seed"], cfg, [], REFS / f"{c['id']}.png"):
            failed.append(f"reference {c['id']}")
    if failed:
        raise SystemExit(f"keyframes: cannot continue without references: {failed}")

    # 2. keyframes conditioned on references
    use_refs = cfg.get("use_references", True)
    for shot in sb["shots"]:
        if only and shot["id"] not in only:
            continue
        ref_ids = shot["characters"] if use_refs else []
        prompt = build_prompt(sb, shot, ref_ids)
        if not _one("keyframe", shot["id"], prompt, shot["seed"], shot_cfg(cfg, shot),
                    [REFS / f"{cid}.png" for cid in ref_ids], KEYS / f"{shot['id']}.png"):
            failed.append(shot["id"])
    if failed:
        raise SystemExit(f"keyframes: flagged on every seed: {failed}. Rephrase those prompts and rerun.")

def candidates(shot_ids: set[str]) -> None:
    """Generate CANDIDATE_SEEDS options per shot into outputs/candidates/<shot>_seed<N>.png.
    Pick one by setting that shot's seed in storyboard.json, then rerun keyframes."""
    load_env()
    sb = load_storyboard()
    cfg = sb["models"]["image"]
    ensure_dirs(CANDS)
    for shot in sb["shots"]:
        if shot["id"] not in shot_ids:
            continue
        ref_ids = shot["characters"] if cfg.get("use_references", True) else []
        prompt = build_prompt(sb, shot, ref_ids)
        refs = [REFS / f"{cid}.png" for cid in ref_ids]
        for i in range(CANDIDATE_SEEDS):
            seed = shot["seed"] + i * 7
            _one("candidate", shot["id"], prompt, seed, shot_cfg(cfg, shot), refs,
                 CANDS / f"{shot['id']}_seed{seed}.png")


if __name__ == "__main__":
    import sys
    run(set(sys.argv[1:]) or None)
