# Imagen Project Memory

## Test Infrastructure
- Python 3.12.3 available via `/usr/bin/python3`
- Venv at `.venv/` with pytest, httpx<0.28, fastapi==0.105.0, pydantic, pillow
- **httpx must be <0.28** for starlette 0.27.0 TestClient compatibility (app kwarg removed in 0.28)
- `tests/conftest.py` mocks heavy ML deps (torch, diffusers, celery, etc.) via sys.modules before app import
- Tests run with: `.venv/bin/python -m pytest tests/ -v`
- `sudo apt-get install python3.12-venv` was needed for venv creation

## App Structure
- No `app/__init__.py` — flat namespace package
- `sys.path.insert(0, ...)` at top of api.py and worker.py for imports
- `pipeline.py` has singleton `FlexiblePipeline` with lazy init (`_initialized = False`)
- `worker.py` calls `multiprocessing.set_start_method('spawn', force=True)` at module level

## API Architecture (after Story 1.1)
- `v1_router = APIRouter(prefix="/v1")` holds all business endpoints
- `app.include_router(v1_router)` registered before `if __name__`
- `/health` stays on `app` object (unversioned)
- StaticFiles `/outputs` and `/reference` stay at root
- 14 business endpoints migrated to /v1/

## Sprint Status
- Sprint status tracked in `_bmad-output/implementation-artifacts/sprint-status.yaml`
- Story files in `_bmad-output/implementation-artifacts/`
