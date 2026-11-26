"""Shared helpers: storyboard loading and validation, input hashing, caching,
retries and the runs.jsonl call log. Every stage imports from here."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"
RUNS = ROOT / "runs.jsonl"
STORYBOARD = ROOT / "storyboard.json"
SCHEMA = ROOT / "schema" / "storyboard.schema.json"


# ---------- environment ----------

def load_env() -> None:
    """Read KEY=VALUE lines from .env into os.environ (no override)."""
    env = ROOT / ".env"
    if not env.exists():
        return
    for line in env.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def need(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise SystemExit(f"Missing {name}. Copy .env.example to .env and fill it in.")
    return val


# ---------- storyboard ----------

def load_storyboard(path: Path = STORYBOARD) -> dict:
    """Load storyboard.json and validate it against the JSON Schema.
    Raises SystemExit with a readable message if it is invalid."""
    import jsonschema

    sb = json.loads(Path(path).read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(sb), key=lambda e: list(e.path))
    if errors:
        msg = "\n".join(f"  - {'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errors)
        raise SystemExit(f"storyboard.json is invalid:\n{msg}")

    # Checks JSON Schema cannot express.
    ids = [s["id"] for s in sb["shots"]]
    if len(ids) != len(set(ids)):
        raise SystemExit("storyboard.json is invalid: shot ids must be unique")
    chars = {c["id"] for c in sb["style"]["characters"]}
    for s in sb["shots"]:
        unknown = set(s.get("characters", [])) - chars
        if unknown:
            raise SystemExit(f"storyboard.json is invalid: shot {s['id']} uses unknown characters {sorted(unknown)}")
    return sb


# ---------- hashing and caching ----------

def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def input_hash(*parts) -> str:
    """Stable hash of everything that determines an output."""
    blob = json.dumps(parts, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def _sidecar(path: Path) -> Path:
    return path.with_name(path.name + ".hash")


def is_fresh(path: Path, h: str) -> bool:
    """True if `path` exists and was produced from inputs with hash `h`."""
    side = _sidecar(path)
    return path.exists() and side.exists() and side.read_text().strip() == h


def mark_fresh(path: Path, h: str) -> None:
    _sidecar(path).write_text(h)


# ---------- logging ----------

def log_call(stage: str, model: str, *, params: dict | None = None, seed=None,
             latency_s: float, status: str = "ok", shot: str | None = None,
             cost_usd: float = 0.0, gpu_s: float | None = None, error: str | None = None,
             extra: dict | None = None, runs_file: Path = RUNS) -> None:
    """Append one line per model call to runs.jsonl."""
    rec = {
        "id": uuid.uuid4().hex[:12],
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stage": stage,
        "shot": shot,
        "model": model,
        "params": params or {},
        "seed": seed,
        "latency_s": round(latency_s, 3),
        "gpu_s": None if gpu_s is None else round(gpu_s, 1),
        "cost_usd": cost_usd,
        "status": status,
    }
    if error:
        rec["error"] = error[:500]
    if extra:
        rec.update(extra)
    with open(runs_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


class Retryable(Exception):
    """Raised for errors worth retrying (rate limits, 5xx, timeouts)."""


def with_retries(fn, *, attempts: int = 3, base_delay: float = 3.0, label: str = ""):
    """Call fn(); retry Retryable errors with exponential backoff."""
    for i in range(1, attempts + 1):
        try:
            return fn()
        except Retryable as e:
            if i == attempts:
                raise
            wait = base_delay * 2 ** (i - 1)
            print(f"  [{label}] attempt {i} failed ({e}); retrying in {wait:.0f}s")
            time.sleep(wait)


def check_http(resp) -> None:
    """Turn an HTTP response into Retryable / hard errors."""
    if resp.status_code == 429 or resp.status_code >= 500:
        raise Retryable(f"HTTP {resp.status_code}: {resp.text[:200]}")
    if resp.status_code >= 400:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:500]}")


# ---------- media helpers ----------

def ffmpeg(*args: str, cwd: Path | None = None) -> None:
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {' '.join(cmd)}\n{r.stderr[-1500:]}")


def duration_of(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(r.stdout.strip())


def ensure_dirs(*paths: Path) -> None:
    for p in paths:
        p.mkdir(parents=True, exist_ok=True)
