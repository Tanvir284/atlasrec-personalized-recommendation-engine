"""Hugging Face Spaces & Cloud self-bootstrapping runtime for AtlasRec."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

# Register a @spaces.GPU function if running on Hugging Face ZeroGPU hardware
try:
    import spaces  # type: ignore

    @spaces.GPU
    def _atlasrec_zero_gpu_ready():
        return {"status": "ok"}

except Exception:
    pass

ROOT_DIR = Path(__file__).resolve().parent.parent


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None):
    print(f"[AtlasRec HF] $ {' '.join(cmd)}", flush=True)
    subprocess.run(cmd, cwd=str(cwd or ROOT_DIR), env=env or os.environ.copy(), check=True)


def ensure_node():
    if shutil.which("node") and shutil.which("npm"):
        return
    node_dir = Path("/tmp/node-v22")
    node_bin = node_dir / "bin"
    if not (node_bin / "node").exists():
        print("[AtlasRec HF] Downloading Node.js 22 LTS Linux binary...", flush=True)
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
    os.chdir(ROOT_DIR)
    py_path = f"{ROOT_DIR / 'packages' / 'ml'}:{ROOT_DIR / 'services' / 'api'}"
    if os.environ.get("PYTHONPATH"):
        py_path = f"{py_path}:{os.environ['PYTHONPATH']}"
    os.environ["PYTHONPATH"] = py_path

    print("[AtlasRec HF] Installing Python ML & FastAPI dependencies...", flush=True)
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "--root-user-action=ignore",
            "fastapi",
            "uvicorn",
            "sqlalchemy",
            "alembic",
            "argon2-cffi",
            "pydantic-settings",
            "scikit-learn",
            "scipy",
            "numpy",
            "pandas",
            "faiss-cpu",
            "lightgbm",
            "redis",
            "celery",
            "pyyaml",
            "httpx",
        ]
    )

    ensure_node()
    if not (ROOT_DIR / "apps" / "web" / ".next").exists():
        print("[AtlasRec HF] Installing frontend packages & building Next.js 15 storefront...", flush=True)
        run(["npm", "ci"])
        run(["npm", "run", "build", "--workspace", "apps/web"])

    api_env = os.environ.copy()
    api_env["PYTHONPATH"] = py_path
    api_env["API_INTERNAL_URL"] = "http://127.0.0.1:8000"
    api_env["HOST"] = "127.0.0.1"
    api_env["PORT"] = "8000"

    print("[AtlasRec HF] Launching FastAPI + 20,500-Product ML Engine on 127.0.0.1:8000...", flush=True)
    subprocess.Popen([sys.executable, "scripts/live_server.py"], cwd=str(ROOT_DIR), env=api_env)

    web_port = os.environ.get("GRADIO_SERVER_PORT") or os.environ.get("PORT") or "7860"
    print(f"[AtlasRec HF] Starting Next.js Storefront on 0.0.0.0:{web_port}...", flush=True)
    web_env = {
        **os.environ,
        "PYTHONPATH": py_path,
        "API_INTERNAL_URL": "http://127.0.0.1:8000",
        "NODE_ENV": "production",
    }
    # Keep this Python process alive so ZeroGPU's @spaces.GPU registration remains active
    subprocess.run(
        [
            "npm",
            "run",
            "start",
            "--workspace",
            "apps/web",
            "--",
            "--hostname",
            "0.0.0.0",
            "--port",
            str(web_port),
        ],
        cwd=str(ROOT_DIR),
        env=web_env,
        check=True,
    )


if __name__ == "__main__":
    main()
