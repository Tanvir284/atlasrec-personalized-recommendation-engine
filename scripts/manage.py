"""Cross-platform launcher. Doctor uses only the standard library."""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def npm_command():
    node = shutil.which("node")
    if node:
        bundled = Path(node).parent / "node_modules/npm/bin/npm-cli.js"
        if bundled.exists():
            return [node, str(bundled)]
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm:
        raise RuntimeError("Install Node with npm; PATH may point to a broken npm shim.")
    return [npm]


def runtime():
    python = ROOT / (".venv/Scripts/python.exe" if os.name == "nt" else ".venv/bin/python")
    if not python.exists():
        raise RuntimeError("Install Python 3.12, then run: uv sync --python 3.12 --frozen")
    value = str(python)
    # MLflow migration names can cross MAX_PATH in Codex worktree directories.
    return "\\\\?\\" + value if os.name == "nt" and len(value) > 150 else value


def execute(command, env=None):
    print("+", " ".join(map(str, command)), flush=True)
    result = subprocess.run(command, cwd=ROOT, env={**os.environ, "MLFLOW_DISABLE_AGENT_HINT": "1", **(env or {})})
    if result.returncode:
        raise RuntimeError(f"Command exited with code {result.returncode}")
    return result.returncode


def doctor():
    report = {"platform": platform.platform(), "launcher_python": platform.python_version(),
              "cpu_threads": os.cpu_count(), "project": str(ROOT), "tools": {}, "ports": {}}
    for tool in ("uv", "node", "docker", "git"):
        report["tools"][tool] = shutil.which(tool)
    try:
        report["npm"] = npm_command()
    except RuntimeError as e:
        report["npm_error"] = str(e)
    try:
        p = subprocess.run(["docker", "version", "--format", "{{json .Server.Version}}"], capture_output=True, timeout=20)
        report["docker_ready"] = p.returncode == 0
        if p.returncode:
            report["docker_error"] = p.stderr.decode(errors="replace")[:1000]
    except (OSError, subprocess.TimeoutExpired) as e:
        report["docker_ready"], report["docker_error"] = False, str(e)
    for port in (3000, 8000):
        with socket.socket() as s:
            s.settimeout(0.25)
            report["ports"][port] = "in use" if s.connect_ex(("127.0.0.1", port)) == 0 else "available"
    if os.name == "nt":
        report["windows_note"] = "Docker needs working WSL2. See docs/WINDOWS.md. A long checkout path can affect MLflow."
    print(json.dumps(report, indent=2))
    return 0 if report["docker_ready"] else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["doctor", "start", "demo", "verify", "research", "benchmark", "stop", "reset"])
    parser.add_argument("--config")
    parser.add_argument("--yes-reset-demo", action="store_true")
    args = parser.parse_args()
    os.chdir(ROOT)
    if args.command == "doctor":
        raise SystemExit(doctor())
    if args.command == "start":
        if not (ROOT / ".env").exists():
            raise RuntimeError("Initialize a documented demo or real-data installation first; .env is missing.")
        execute(["docker", "compose", "-p", "atlasrec", "up", "-d", "--wait", "--wait-timeout", "300"])
        print("AtlasRec restarted with its configured catalog and model: http://localhost:3000")
    elif args.command == "demo":
        if not (ROOT / ".env").exists():
            (ROOT / ".env").write_text((ROOT / ".env.example").read_text(), encoding="utf-8")
        profile = dict(line.split("=", 1) for line in (ROOT / ".env").read_text().splitlines()
                       if line and not line.startswith("#") and "=" in line).get("ATLASREC_PROFILE")
        if profile != "demo":
            raise RuntimeError("This installation uses real data. Use: python scripts/manage.py start")
        execute(["docker", "compose", "-p", "atlasrec", "up", "--build", "-d", "--wait", "--wait-timeout", "300"])
        execute(["docker", "compose", "-p", "atlasrec", "exec", "-T", "api", "python", "scripts/bootstrap.py"])
        print("Shop: http://localhost:3000 · workbench: http://localhost:3000/admin")
        print("Demo access: docs/DEMO.md")
    elif args.command == "verify":
        commands = [
            [runtime(), "-m", "ruff", "check", "packages", "services", "scripts", "tests"],
            [runtime(), "-m", "pytest", "-q"],
            npm_command() + ["run", "lint"],
            npm_command() + ["run", "format:check"],
            npm_command() + ["run", "build"],
        ]
        outcomes = []
        for command in commands:
            try:
                execute(command)
                outcomes.append({"command": command, "exit_code": 0})
            except RuntimeError as e:
                outcomes.append({"command": command, "error": str(e)})
        path = ROOT / "docs/evidence/verification.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(outcomes, indent=2), encoding="utf-8")
        if any("error" in r for r in outcomes):
            raise SystemExit(1)
    elif args.command in ("research", "benchmark"):
        execute([runtime(), "-m", "atlasrec_ml.cli", args.command if args.command == "benchmark" else "train", "--config",
                 args.config or ("configs/research.yaml" if args.command == "research" else "configs/benchmark.yaml")])
    elif args.command == "stop":
        execute(["docker", "compose", "-p", "atlasrec", "down"])
    elif args.command == "reset":
        if not args.yes_reset_demo:
            raise RuntimeError("Reset deletes only atlasrec demo volumes. Re-run with --yes-reset-demo after confirming.")
        profile = dict(line.split("=", 1) for line in (ROOT / ".env").read_text().splitlines() if line and not line.startswith("#") and "=" in line).get("ATLASREC_PROFILE")
        if profile != "demo":
            raise RuntimeError("Reset is restricted to the explicit demo profile")
        execute(["docker", "compose", "-p", "atlasrec", "down", "--volumes"])


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
