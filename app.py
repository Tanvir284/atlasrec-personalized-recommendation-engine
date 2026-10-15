"""Minimal Hugging Face Spaces bootstrapper — clones GitHub repo and runs scripts/hf_entry.py."""
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = "https://github.com/Tanvir284/atlasrec-personalized-recommendation-engine.git"
WORK = Path("/tmp/atlasrec")

if __name__ == "__main__":
    if WORK.exists():
        shutil.rmtree(WORK)
    subprocess.run(["git", "clone", "--depth", "1", REPO, str(WORK)], check=True)
    os.execv(sys.executable, [sys.executable, str(WORK / "scripts" / "hf_entry.py")])
