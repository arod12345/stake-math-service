from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .runner import run_pipeline, validate_game
from .settings import get_settings
from .workspaces import (
    copy_template_game,
    ensure_workspace_structure,
    iter_tree,
    new_workspace_id,
    safe_join,
    workspace_games_root,
    workspace_root,
)


app = FastAPI(title="Stake Math SDK Service", version="0.1.0")
settings = get_settings()

_cors_origins = [o.strip() for o in os.environ.get("STAKE_MATH_CORS_ORIGINS", "*").split(",") if o.strip()]
if "*" in _cors_origins:
    allow_origins = ["*"]
else:
    allow_origins = _cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def repo_math_sdk_dir() -> Path:
    # monorepo path: <repo>/packages/math-sdk
    p = settings.repo_root / "packages" / "math-sdk"
    if not p.exists():
        raise RuntimeError(f"Cannot locate math-sdk at {p}")
    return p


class CreateWorkspaceResponse(BaseModel):
    workspaceId: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/workspaces", response_model=CreateWorkspaceResponse)
def create_workspace() -> CreateWorkspaceResponse:
    ws = new_workspace_id()
    ensure_workspace_structure(settings.workspaces_dir, ws)
    return CreateWorkspaceResponse(workspaceId=ws)


class CreateGameRequest(BaseModel):
    gameId: str = Field(min_length=1)
    overwrite: bool = False


class CreateGameResponse(BaseModel):
    workspaceId: str
    gameId: str
    root: str


@app.post("/v1/workspaces/{workspace_id}/games", response_model=CreateGameResponse)
def create_game_from_template(workspace_id: str, req: CreateGameRequest) -> CreateGameResponse:
    try:
        dst = copy_template_game(
            repo_math_sdk_dir=repo_math_sdk_dir(),
            workspaces_dir=settings.workspaces_dir,
            workspace_id=workspace_id,
            game_id=req.gameId,
            overwrite=req.overwrite,
        )
        return CreateGameResponse(workspaceId=workspace_id, gameId=req.gameId, root=str(dst))
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(e)) from e


class TreeResponse(BaseModel):
    workspaceId: str
    entries: list[dict[str, Any]]


@app.get("/v1/workspaces/{workspace_id}/tree", response_model=TreeResponse)
def tree(workspace_id: str) -> TreeResponse:
    ws_root = workspace_root(settings.workspaces_dir, workspace_id)
    if not ws_root.exists():
        raise HTTPException(status_code=404, detail="workspace not found")
    return TreeResponse(workspaceId=workspace_id, entries=list(iter_tree(ws_root, ws_root)))


@app.get("/v1/workspaces/{workspace_id}/file")
def read_file(workspace_id: str, path: str = Query(min_length=1)) -> dict[str, Any]:
    ws_root = workspace_root(settings.workspaces_dir, workspace_id)
    if not ws_root.exists():
        raise HTTPException(status_code=404, detail="workspace not found")
    fp = safe_join(ws_root, path)
    if not fp.exists() or fp.is_dir():
        raise HTTPException(status_code=404, detail="file not found")
    return {"path": path, "content": fp.read_text(encoding="utf-8")}


class WriteFileRequest(BaseModel):
    content: str


@app.put("/v1/workspaces/{workspace_id}/file")
def write_file(workspace_id: str, path: str = Query(min_length=1), req: WriteFileRequest = ...) -> dict[str, str]:
    ws_root = workspace_root(settings.workspaces_dir, workspace_id)
    if not ws_root.exists():
        raise HTTPException(status_code=404, detail="workspace not found")
    fp = safe_join(ws_root, path)
    if fp.exists() and fp.is_dir():
        raise HTTPException(status_code=400, detail="path is a directory")
    fp.parent.mkdir(parents=True, exist_ok=True)
    fp.write_text(req.content, encoding="utf-8")
    return {"path": path}


class ValidateRequest(BaseModel):
    gameId: str = Field(min_length=1)


@app.post("/v1/workspaces/{workspace_id}/validate")
def validate(workspace_id: str, req: ValidateRequest) -> dict[str, Any]:
    games_root = workspace_games_root(settings.workspaces_dir, workspace_id)
    if not games_root.exists():
        raise HTTPException(status_code=404, detail="workspace not found")
    res = validate_game(games_root, req.gameId)
    return {"ok": res.ok, "error": res.error, "traceback": res.traceback}


class RunRequest(BaseModel):
    gameId: str = Field(min_length=1)
    runSims: bool = True
    runOptimization: bool = False
    runAnalysis: bool = False
    numSimArgs: dict[str, int] = Field(default_factory=lambda: {"base": 100})
    threads: int = 1
    batchSize: int = 1000
    compress: bool = True
    profiling: bool = False
    rustThreads: int = 4


@app.post("/v1/workspaces/{workspace_id}/run")
def run(workspace_id: str, req: RunRequest) -> dict[str, Any]:
    games_root = workspace_games_root(settings.workspaces_dir, workspace_id)
    if not games_root.exists():
        raise HTTPException(status_code=404, detail="workspace not found")

    res = run_pipeline(
        workspace_games_root=games_root,
        game_id=req.gameId,
        run_sims=req.runSims,
        run_optimization=req.runOptimization,
        run_analysis=req.runAnalysis,
        num_sim_args=req.numSimArgs,
        threads=req.threads,
        batch_size=req.batchSize,
        compress=req.compress,
        profiling=req.profiling,
        rust_threads=req.rustThreads,
    )
    if not res.ok:
        raise HTTPException(status_code=400, detail={"error": res.error, "traceback": res.traceback})

    # Return common artifact locations (relative to workspace)
    game_library = safe_join(games_root, req.gameId, "library")
    return {
        "ok": True,
        "artifacts": {
            "library": str(game_library),
            "configs": str(game_library / "configs"),
            "publish_files": str(game_library / "publish_files"),
            "books": str(game_library / "books"),
            "lookup_tables": str(game_library / "lookup_tables"),
            "forces": str(game_library / "forces"),
        },
    }


@app.get("/v1/workspaces/{workspace_id}/download")
def download_file(workspace_id: str, path: str = Query(min_length=1)) -> FileResponse:
    ws_root = workspace_root(settings.workspaces_dir, workspace_id)
    if not ws_root.exists():
        raise HTTPException(status_code=404, detail="workspace not found")
    fp = safe_join(ws_root, path)
    if not fp.exists() or fp.is_dir():
        raise HTTPException(status_code=404, detail="file not found")

    media_type, _ = mimetypes.guess_type(fp.name)
    return FileResponse(path=str(fp), media_type=media_type or "application/octet-stream", filename=fp.name)


