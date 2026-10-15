"""Hugging Face Spaces & Cloud self-bootstrapping runtime for AtlasRec."""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def register_zerogpu():
    """Satisfy Hugging Face ZeroGPU startup check on an internal port (7861) while Next.js serves 7860."""
    try:
        import gradio as gr  # type: ignore
        import spaces  # type: ignore

        @spaces.GPU
        def _atlasrec_gpu_warmup():
            return "AtlasRec GPU Ready"

        orig_port = os.environ.get("GRADIO_SERVER_PORT")
        os.environ["GRADIO_SERVER_PORT"] = "7861"
        demo = gr.Interface(fn=_atlasrec_gpu_warmup, inputs=[], outputs="text")
        demo.launch(
            server_name="127.0.0.1",
            server_port=7861,
            prevent_thread_lock=True,
            quiet=True,
        )
        if orig_port:
            os.environ["GRADIO_SERVER_PORT"] = orig_port
        else:
            os.environ.pop("GRADIO_SERVER_PORT", None)
        print("[AtlasRec HF] Registered @spaces.GPU warmup hook on internal port 7861.", flush=True)
    except Exception as exc:
        print(f"[AtlasRec HF] ZeroGPU hook note: {exc}", flush=True)


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
    # Register @spaces.GPU immediately so ZeroGPU daemon detects it during startup
    register_zerogpu()

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
