from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    repo_root: Path
    workspaces_dir: Path
    max_run_seconds: int


def get_settings() -> Settings:
    # Assume service is run from repo root OR inside a container with /app as repo root.
    # We resolve relative workspace dir from current working directory.
    repo_root = Path(os.getcwd()).resolve()
    workspaces_dir = Path(os.environ.get("STAKE_MATH_WORKSPACES_DIR", ".stake-math-workspaces")).resolve()
    max_run_seconds = int(os.environ.get("STAKE_MATH_MAX_RUN_SECONDS", "120"))
    return Settings(repo_root=repo_root, workspaces_dir=workspaces_dir, max_run_seconds=max_run_seconds)


