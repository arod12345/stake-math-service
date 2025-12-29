from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import Iterable


def safe_join(root: Path, *parts: str) -> Path:
    """Join paths but prevent escaping the root."""
    p = (root.joinpath(*parts)).resolve()
    root_resolved = root.resolve()
    if root_resolved == p:
        return p
    if root_resolved not in p.parents:
        raise ValueError("Invalid path (escapes workspace root).")
    return p


def new_workspace_id() -> str:
    return uuid.uuid4().hex


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def workspace_root(workspaces_dir: Path, workspace_id: str) -> Path:
    return safe_join(workspaces_dir, workspace_id)


def workspace_games_root(workspaces_dir: Path, workspace_id: str) -> Path:
    return safe_join(workspace_root(workspaces_dir, workspace_id), "games")


def ensure_workspace_structure(workspaces_dir: Path, workspace_id: str) -> Path:
    """Create workspace layout and return workspace root."""
    ws_root = workspace_root(workspaces_dir, workspace_id)
    ensure_dir(ws_root)
    games_root = workspace_games_root(workspaces_dir, workspace_id)
    ensure_dir(games_root)
    # Make games a package so importlib can load games.<id> modules
    init_py = safe_join(games_root, "__init__.py")
    if not init_py.exists():
        init_py.write_text("# workspace games package\n", encoding="utf-8")
    return ws_root


def copy_template_game(
    *,
    repo_math_sdk_dir: Path,
    workspaces_dir: Path,
    workspace_id: str,
    game_id: str,
    overwrite: bool,
) -> Path:
    """
    Copy `packages/math-sdk/games/template/` into workspace `games/<game_id>/`.
    Also creates `games/<game_id>/reels/` with placeholder CSVs required by the template config.
    """
    ensure_workspace_structure(workspaces_dir, workspace_id)
    src_template = repo_math_sdk_dir / "games" / "template"
    if not src_template.exists():
        raise FileNotFoundError(f"Template folder not found: {src_template}")

    dst_game = safe_join(workspace_games_root(workspaces_dir, workspace_id), game_id)
    if dst_game.exists():
        if not overwrite:
            raise FileExistsError(f"Game already exists: {game_id}")
        shutil.rmtree(dst_game)

    shutil.copytree(src_template, dst_game)

    # Ensure reels folder exists (template config references BR0.csv / FR0.csv)
    reels_dir = safe_join(dst_game, "reels")
    ensure_dir(reels_dir)
    for name in ("BR0.csv", "FR0.csv"):
        f = safe_join(reels_dir, name)
        if not f.exists():
            # 5 reels x 1 row placeholder symbol "A"
            f.write_text("A,A,A,A,A\n", encoding="utf-8")

    # Auto-fill game_id in copied game_config.py to reduce footguns.
    cfg_path = safe_join(dst_game, "game_config.py")
    if cfg_path.exists():
        text = cfg_path.read_text(encoding="utf-8")
        # very conservative replace: only replace the first occurrence of self.game_id = ""
        marker = 'self.game_id = ""'
        if marker in text:
            text = text.replace(marker, f'self.game_id = "{game_id}"', 1)
            cfg_path.write_text(text, encoding="utf-8")

    return dst_game


def iter_tree(root: Path, base: Path) -> Iterable[dict]:
    """Return a JSONable directory tree."""
    for entry in sorted(root.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        rel = entry.relative_to(base).as_posix()
        if entry.is_dir():
            yield {"type": "dir", "path": rel}
            yield from iter_tree(entry, base)
        else:
            yield {"type": "file", "path": rel, "size": entry.stat().st_size}


