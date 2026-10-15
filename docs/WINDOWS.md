# Windows setup issue observed 2026-10-05 (Asia/Dhaka)

Docker Desktop startup failed with DockerDesktop/Wsl/ExecError. Direct
wsl --version, wsl --status and wsl --install --no-distribution --web-download
all returned "The system cannot find the file specified". The System32 launcher
exists, WslService runs, but C:\\Program Files\\WSL\\wsl.exe was absent.

This is a host prerequisite failure, not an AtlasRec training failure.
A Microsoft x64 WSL 3.0.1 MSI repair installer was selected from the official release:
https://github.com/microsoft/WSL/releases/tag/3.0.1
Expected size: 367669248 bytes; SHA256:
28b1a0d013640a2ac95898ea705fa186e5b4ff767a1c1b49257161bc106599c6

Only install a verified Microsoft-signed installer. No restart is performed by AtlasRec.
Microsoft's documented offline installation path:
https://learn.microsoft.com/en-us/windows/wsl/install#offline-install

After repair, check wsl --version. Enable Virtual Machine Platform if disabled from
an Administrator PowerShell:
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
Windows may require a manual restart. Then start Docker Desktop and rerun doctor.

The Codex worktree path also crossed Windows MAX_PATH for an MLflow migration.
scripts/manage.py uses Python's extended path prefix for long Windows runtime paths.
The original Desktop project folder has a shorter path. A short checkout such as
C:\\src\\AtlasRec is another supported workaround; do not move/delete user files automatically.

PATH contained a broken npm shim in AppData/Roaming/npm. manage.py selects the npm CLI
bundled next to node.exe when available. Direct fallback:
node "C:\\Program Files\\nodejs\\node_modules\\npm\\bin\\npm-cli.js" ci

## Repair executed on this host

The Microsoft-signed WSL 3.0.1 MSI installed successfully with exit code 0, without an
automatic Windows reboot. wsl --version now reports 3.0.1. Docker server 29.8.1 responds;
AtlasRec PostgreSQL and Redis are healthy. The initial Docker build encountered transient
DNS failure; an in-container DNS probe resolved the package registries, and the retry
downloaded the dependencies. Final app integration is recorded in BUILD_REPORT.

This host has about 8GB RAM. A probe during parallel builds saw only about 220MB free.
Next builds now use two workers and memory optimization; keep native and container builds
sequential and stop unused test servers. Temporary development servers are not the demo.
