"""Hugging Face Spaces (Gradio / Docker) & Cloud self-bootstrapping launcher for AtlasRec."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO_URL = "https://github.com/Tanvir284/atlasrec-personalized-recommendation-engine.git"
WORK_DIR = Path("/tmp/atlasrec") if not Path("packages/ml").exists() else Path.cwd()


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None):
    print(f"[AtlasRec Bootstrap] $ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=str(cwd or WORK_DIR), env=env or os.environ.copy(), check=True)


def ensure_node():
    if shutil.which("node") and shutil.which("npm"):
        return
    node_dir = Path("/tmp/node-v22")
    node_bin = node_dir / "bin"
    if not (node_bin / "node").exists():
        print("[AtlasRec Bootstrap] Downloading Node.js 22 LTS Linux binary...", flush=True)
        tar_path = Path("/tmp/node.tar.xz")
        urllib.request.urlretrieve(
            "https://nodejs.org/dist/v22.14.0/node-v22.14.0-linux-x64.tar.xz",
            tar_path,
        )
        node_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["tar", "-xJf", str(tar_path), "-C", str(node_dir), "--strip-components=1"],
            check=True,
        )
    os.environ["PATH"] = f"{node_bin}:{os.environ.get('PATH', '')}"


def main():
    if not Path("packages/ml").exists():
        if WORK_DIR.exists():
            shutil.rmtree(WORK_DIR)
        run(["git", "clone", "--depth", "1", REPO_URL, str(WORK_DIR)], cwd=Path("/tmp"))

    print("[AtlasRec Bootstrap] Installing Python ML & FastAPI packages...", flush=True)
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "fastapi",
            "uvicorn",
            "sqlalchemy",
            "alembic",
            "argon2-cffi",
            "pydantic-settings",
            "scikit-learn",
            "scipy",
            "numpy",
            "faiss-cpu",
            "lightgbm",
            "redis",
            "celery",
            "httpx",
        ]
    )
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "--no-deps",
            "-e",
            "packages/ml",
            "-e",
            "services/api",
        ]
    )

    ensure_node()
    if not (WORK_DIR / "apps/web/.next").exists():
        print("[AtlasRec Bootstrap] Installing frontend packages & building Next.js 15 app...", flush=True)
        run(["npm", "ci"])
        run(["npm", "run", "build", "--workspace", "apps/web"])

    env = os.environ.copy()
    env["API_INTERNAL_URL"] = "http://127.0.0.1:8000"
    env["HOST"] = "127.0.0.1"
    env["PORT"] = "8000"

    print("[AtlasRec Bootstrap] Starting FastAPI + 20,500-Product ML Engine on 127.0.0.1:8000...", flush=True)
    subprocess.Popen([sys.executable, "scripts/live_server.py"], cwd=str(WORK_DIR), env=env)

    web_port = os.environ.get("GRADIO_SERVER_PORT") or os.environ.get("PORT") or "7860"
    print(f"[AtlasRec Bootstrap] Starting Next.js Storefront on 0.0.0.0:{web_port}...", flush=True)
    os.execvpe(
        "npm",
        ["npm", "run", "start", "--workspace", "apps/web", "--", "--hostname", "0.0.0.0", "--port", str(web_port)],
        {**os.environ, "API_INTERNAL_URL": "http://127.0.0.1:8000", "NODE_ENV": "production"},
    )


if __name__ == "__main__":
    main()
