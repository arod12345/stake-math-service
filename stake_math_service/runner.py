from __future__ import annotations

import importlib
import os
import sys
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RunResult:
    ok: bool
    error: str | None = None
    traceback: str | None = None


def _patch_math_sdk_paths(games_root: Path) -> None:
    """
    math-sdk uses a global constant PATH_TO_GAMES = <repo>/games.
    For hosted workspaces we monkeypatch it to point at the workspace games folder.
    """
    from src.config import paths as sdk_paths  # type: ignore

    sdk_paths.PATH_TO_GAMES = str(games_root)


def _import_game_classes(game_id: str) -> tuple[type[Any], type[Any]]:
    cfg_mod = importlib.import_module(f"games.{game_id}.game_config")
    gs_mod = importlib.import_module(f"games.{game_id}.gamestate")
    cfg_cls = getattr(cfg_mod, "GameConfig")
    gs_cls = getattr(gs_mod, "GameState")
    return cfg_cls, gs_cls


def validate_game(workspace_games_root: Path, game_id: str) -> RunResult:
    """
    Validate that the game can be imported and instantiated.
    This does NOT run simulations.
    """
    try:
        _patch_math_sdk_paths(workspace_games_root)
        # ensure workspace root is importable
        ws_root = workspace_games_root.parent
        sys.path.insert(0, str(ws_root))
        try:
            cfg_cls, gs_cls = _import_game_classes(game_id)
            cfg = cfg_cls()
            _ = gs_cls(cfg)
        finally:
            if sys.path and sys.path[0] == str(ws_root):
                sys.path.pop(0)
        return RunResult(ok=True)
    except Exception as e:  # noqa: BLE001
        return RunResult(ok=False, error=str(e), traceback=traceback.format_exc())


def run_pipeline(
    *,
    workspace_games_root: Path,
    game_id: str,
    run_sims: bool,
    run_optimization: bool,
    run_analysis: bool,
    num_sim_args: dict[str, int],
    threads: int,
    batch_size: int,
    compress: bool,
    profiling: bool,
    rust_threads: int,
) -> RunResult:
    """
    Execute the same core pipeline used by game `run.py`, but without invoking user-provided
    scripts. This avoids surprises like AWS uploads.
    """
    try:
        if run_optimization or run_analysis:
            # optimization program is optional and may require Rust; keep opt toggles explicit.
            os.environ.setdefault("RUST_BACKTRACE", "1")

        _patch_math_sdk_paths(workspace_games_root)
        ws_root = workspace_games_root.parent
        sys.path.insert(0, str(ws_root))
        try:
            cfg_cls, gs_cls = _import_game_classes(game_id)
            config = cfg_cls()
            gamestate = gs_cls(config)

            from src.state.run_sims import create_books  # type: ignore
            from src.write_data.write_configs import generate_configs  # type: ignore

            if run_sims:
                create_books(
                    gamestate,
                    config,
                    num_sim_args,
                    batch_size,
                    threads,
                    compress,
                    profiling,
                )

            # Always generate configs, just like example run.py
            generate_configs(gamestate)

            if run_optimization:
                # Optional: requires Rust/cargo in runtime image
                from optimization_program.run_script import OptimizationExecution  # type: ignore

                target_modes = list(num_sim_args.keys())
                OptimizationExecution().run_all_modes(config, target_modes, rust_threads)
                generate_configs(gamestate)

            if run_analysis:
                from utils.game_analytics.run_analysis import create_stat_sheet  # type: ignore

                create_stat_sheet(config.game_id, custom_keys=None)

        finally:
            if sys.path and sys.path[0] == str(ws_root):
                sys.path.pop(0)

        return RunResult(ok=True)
    except Exception as e:  # noqa: BLE001
        return RunResult(ok=False, error=str(e), traceback=traceback.format_exc())


