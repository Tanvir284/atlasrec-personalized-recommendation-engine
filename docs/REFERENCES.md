# Sources and compatibility notes (consulted 2026-10-05)

- Next 16.3.8 installed docs: node_modules/next/dist/docs, route.js and App Router guides;
  https://nextjs.org/docs/app/getting-started/installation
- FastAPI background work: https://fastapi.tiangolo.com/tutorial/background-tasks/
- uv CPU index/project lock: https://docs.astral.sh/uv/guides/projects/
- Amazon source/schema: https://amazon-reviews-2023.github.io/
- LightGBM query-group API: https://lightgbm.readthedocs.io/en/stable/pythonapi/lightgbm.LGBMRanker.html
- Microsoft WSL offline repair: https://learn.microsoft.com/en-us/windows/wsl/install#offline-install
- Docker WSL requirements: https://docs.docker.com/desktop/features/wsl/
- Verified Microsoft WSL release: https://github.com/microsoft/WSL/releases/tag/3.0.1

npm/uv lockfiles contain actual resolved dependency versions. CPU torch 2.14.1+cpu,
Next 16.3.8, React 19.3.0, LightGBM 4.7.0 were installed. ESLint 10 failed with the
Next preset's parser; React's lint plugin supports through ESLint 9. The project uses
the actual compatible ESLint 9.39.5 with React rules and native JSX parsing. Removing
the Next preset removed its unpatched braces chain. Upstream marks ESLint 9 deprecated;
upgrade when React plugin support permits. Build remains an independent Next check.
