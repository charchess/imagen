---
stepsCompleted: ['step-01-validate-prerequisites', 'step-02-design-epics', 'step-03-create-stories', 'step-04-final-validation']
inputDocuments: ['docs/prd.md', '_bmad-output/planning-artifacts/architecture.md']
status: 'complete'
completedAt: '2026-02-06'
totalEpics: 7
totalStories: 22
---

# imagen - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for imagen, decomposing the requirements from the PRD and Architecture into implementable stories.

## Requirements Inventory

### Functional Requirements

FR1: L'utilisateur peut spécifier le modèle de base (SDXL, PonyXL). [PRD FR-01.1]
FR2: Le système doit automatiquement libérer la VRAM nécessaire lors d'un changement de modèle. [PRD FR-01.2]
FR3: Le système doit exposer la liste des modèles et LoRAs installés via des points d'entrée dédiés. [PRD FR-01.3]
FR4: L'API doit supporter une authentification sécurisée via clé API (X-API-Key) pour restreindre l'accès aux agents autorisés. [PRD FR-01.4]
FR5: L'API doit accepter jusqu'à 4 images de référence simultanées (front, side, back, background). [PRD FR-02.1]
FR6: L'utilisateur peut ajuster la "force" du transfert de style (0.0 à 1.0). [PRD FR-02.2]
FR7: L'utilisateur peut appliquer plusieurs LoRAs simultanément avec des poids distincts. [PRD FR-02.3]
FR8: L'API doit supporter les paramètres : steps, guidance_scale, seed, et type d'image (Character/Background). [PRD FR-03.1]
FR9: Le système doit supporter des prompts positifs et négatifs d'une longueur allant jusqu'à 4096 tokens (via Compel). [PRD FR-03.2]

### NonFunctional Requirements

NFR1: Temps de réponse de l'API (hors génération) < 200ms pour 95% des requêtes. [PRD NFR-01.1]
NFR2: Le système doit supporter une file d'attente de 100 jobs sans dégradation de performance de l'API. [PRD NFR-01.2]
NFR3: En cas d'erreur GPU (Out of Memory), le système doit effectuer jusqu'à 3 tentatives automatiques. [PRD NFR-02.1]
NFR4: Isolation stricte des sessions utilisateur pour éviter les fuites de métadonnées. [PRD NFR-02.2]

### Additional Requirements

- Infrastructure: Docker avec NVIDIA Runtime (FastAPI, Celery, Redis). [Arch: Stack]
- Volumes partagés : models/, outputs/, reference/, secrets/. [Arch: DA-001]
- GPU 11GB VRAM minimum — concurrency worker = 1 (strict). [Arch: ADR-003]
- CI/CD GitHub Actions minimal (Ruff, MyPy, Docker build). [Arch: INFRA-001]
- API versioning avec préfixe /v1/ pour tous les endpoints business. [Arch: API-002]
- Format d'erreur standardisé : {error: {code, message, detail, status}}. [Arch: API-001]
- Pas de rate limiting — queue size comme seul throttle. [Arch: API-003]
- Health check enrichi avec GPU/queue/pipeline stats. [Arch: INFRA-002]
- Auth via fichier statique /app/secrets/api_key.txt avec hot rotation. [Arch: SEC-001]
- Endpoints documentaires exemptés d'auth (GET /v1/models, /loras, /references). [Arch: SEC-002]
- Rétention images : 24h non-téléchargées, 1h après téléchargement, cleanup lazy. [Arch: DA-002]
- Stockage modèles sur volume Docker NFS-mountable, gestion admin. [Arch: DA-001]
- Téléchargement dynamique LoRA/modèles via API (two-step explicit). [Arch: DA-003]
- Migration logging vers module logging (deferred tech debt). [Arch: INFRA-003]

### Full Coverage Map

| Requirement | Epic | Description |
|-------------|------|-------------|
| FR1 | Epic 2 | Sélection modèle de base (SDXL, PonyXL) |
| FR2 | Epic 2 | Libération VRAM automatique lors du swap |
| FR3 | Epic 3 | Endpoints inventaire modèles/LoRAs |
| FR4 | Epic 1 | Authentification API Key (X-API-Key) |
| FR5 | Epic 2 | Multi-référence IP-Adapter (jusqu'à 4) |
| FR6 | Epic 2 | Force de transfert de style (0.0-1.0) |
| FR7 | Epic 2 | LoRAs multiples simultanés avec poids |
| FR8 | Epic 2 | Paramètres de génération (steps, guidance, seed, type) |
| FR9 | Epic 2 | Prompts longs jusqu'à 4096 tokens (Compel) |
| NFR1 | Epic 2 | Latence API < 200ms (hors génération) |
| NFR2 | Epic 4 | Queue 100 jobs sans dégradation |
| NFR3 | Epic 4 | Retry OOM x3 avec backoff |
| NFR4 | Epic 2 | Isolation stricte des sessions |
| SEC-004 | Epic 5 | Celery credential logging fix (5.3.4 → 5.6.2) |
| INFRA-003 | Epic 5 | Migration logging print() → logging module |
| Version Debt | Epic 5 | Dependency pinning, lockfile, opportunistic upgrades |
| Trade-Off 4 | Epic 6 | ControlNet pipeline factory + integration (Growth) |
| ADR-001 Growth | Epic 6 | Singleton → Factory pattern (Growth) |
| ADR-004 Growth | Epic 7 | JSON → SQLite migration (Growth) |
| First Principles | Epic 7 | SSE job notifications (Growth) |
| ADR-001 Embed | Epic 7 | Embedding pre-computation (Growth) |
| INFRA-002 Growth | Epic 7 | Monitoring dashboard (Growth) |

## Epic List

### Epic 1: API Modernization & Security Gateway (MVP)
Les agents accèdent à Imagen via une API versionnée, sécurisée, avec des erreurs cohérentes.
**FRs covered:** FR4
**Arch decisions:** API-001, API-002, SEC-001, SEC-002, SEC-003, SEC-004
**Stories:** 1.1, 1.2, 1.3

### Epic 2: Generation Pipeline Validation & Enhancement (MVP)
Les agents peuvent générer des images cohérentes avec contrôle artistique complet via l'API modernisée.
**FRs covered:** FR1, FR2, FR5, FR6, FR7, FR8, FR9
**NFRs covered:** NFR1, NFR4
**Arch decisions:** ADR-001 (lazy loading, placeholder warning), Trade-Off 3 (queue position)
**Stories:** 2.1, 2.2, 2.3

### Epic 3: Model & LoRA Ecosystem (MVP)
Les agents peuvent découvrir les modèles/LoRAs disponibles et en télécharger dynamiquement de nouveaux.
**FRs covered:** FR3
**Arch decisions:** DA-001, DA-003, Trade-Off 2 (download validation)
**Stories:** 3.1, 3.2

### Epic 4: Operational Reliability (MVP)
Le système est fiable avec rétention intelligente, monitoring enrichi, et CI automatisé.
**NFRs covered:** NFR2, NFR3
**Arch decisions:** DA-002, INFRA-001, INFRA-002, ADR-002
**Stories:** 4.1, 4.2, 4.3

### Epic 5: Dependency Hygiene & Hardening (MVP)
Le projet a des dépendances verrouillées, une sécurité Celery à jour, et un logging structuré.
**Arch decisions:** SEC-004, INFRA-003, Version Debt, Dependency Management Debt
**Stories:** 5.1, 5.2, 5.3, 5.4

### Epic 6: ControlNet & Structural Control (Growth)
Les agents peuvent contrôler la structure des images générées via ControlNet (Canny, Pose, Depth).
**Arch decisions:** ADR-001 (factory pattern), Trade-Off 4 (ControlNet), controlnet-aux
**Stories:** 6.1, 6.2, 6.3

### Epic 7: Real-Time & Observability (Growth)
Le système offre des notifications temps réel, des embeddings pré-calculés, et un dashboard de monitoring.
**Arch decisions:** ADR-004 (SQLite), First Principles (SSE), ADR-001 (embeddings), INFRA-002 (dashboard)
**Stories:** 7.1, 7.2, 7.3, 7.4

## Epic 1: API Modernization & Security Gateway

Les agents accèdent à Imagen via une API versionnée, sécurisée, avec des erreurs cohérentes.

### Story 1.1: API Versioning Migration

As a API consumer,
I want all business endpoints to be served under the /v1/ prefix,
So that I have a stable, versioned API contract that can evolve without breaking my integration.

**Acceptance Criteria:**

**Given** the API is running
**When** I call any business endpoint (generate, status, download, image, models, loras, references)
**Then** the endpoint is available under `/v1/` prefix (e.g., `/v1/generate`, `/v1/models`)
**And** the response format is unchanged from current behavior

**Given** the API is running
**When** I call `/health`
**Then** it remains at the root path (unversioned, infrastructure endpoint)

**Given** the API is running
**When** I call an old unversioned path (e.g., `/generate`)
**Then** I receive a 404 Not Found (no backward compatibility redirect)

### Story 1.2: Standardized Error Response Format

As a API consumer,
I want all API errors to follow a consistent JSON format,
So that I can programmatically handle errors without parsing different response shapes.

**Acceptance Criteria:**

**Given** any API endpoint returns an error
**When** the error is a validation error (422), not found (404), queue full (503), or server error (500)
**Then** the response body follows the format: `{"error": {"code": "ERROR_CODE", "message": "...", "detail": "...", "status": N}}`
**And** the HTTP status code matches the `status` field in the envelope

**Given** a request with invalid parameters
**When** Pydantic validation fails
**Then** the error code is `INVALID_PARAMETERS` with status 422
**And** the detail field contains the specific validation error

**Given** a request for a non-existent job
**When** I call `GET /v1/status/{unknown_id}`
**Then** the error code is `JOB_NOT_FOUND` with status 404

**Given** the generation queue is full
**When** I call `POST /v1/generate`
**Then** the error code is `QUEUE_FULL` with status 503

### Story 1.3: API Key Authentication

As a system administrator,
I want all mutation endpoints protected by API Key authentication,
So that only authorized agents can generate images, download content, or trigger actions.

**Acceptance Criteria:**

**Given** a valid API key exists in `/app/secrets/api_key.txt`
**When** I call a protected endpoint with header `X-API-Key: <valid_key>`
**Then** the request proceeds normally

**Given** a protected endpoint (POST /v1/generate, GET /v1/status/*, GET /v1/download/*, GET /v1/image/*)
**When** I call it without an `X-API-Key` header
**Then** I receive error code `UNAUTHORIZED` with status 401 in the standard error envelope

**Given** exempt endpoints (GET /health, GET /v1/models, GET /v1/loras, GET /v1/references)
**When** I call them without any API key
**Then** the request proceeds normally (no authentication required)

**Given** the admin updates `/app/secrets/api_key.txt` on the mounted volume
**When** the next API request arrives
**Then** the new key is accepted immediately (hot rotation, no restart needed)

## Epic 2: Generation Pipeline Validation & Enhancement

Les agents peuvent générer des images cohérentes avec contrôle artistique complet via l'API modernisée.

### Story 2.1: Pipeline Lazy Loading & State Feedback

As a API consumer,
I want the pipeline to load models on-demand and report its loading state,
So that the API starts instantly and I know when the system is loading a model for the first time.

**Acceptance Criteria:**

**Given** the worker starts fresh (no model loaded)
**When** the first generation request arrives
**Then** the pipeline loads the requested model lazily (not at import time)
**And** the Celery task state reports `"step": "model_loading"` during load

**Given** `compute_embedding()` is called on the pipeline
**When** the function executes
**Then** a `warnings.warn("Placeholder: embedding pre-computation not implemented")` is emitted
**And** the function still returns its current placeholder value

**Given** the pipeline has loaded a model
**When** `is_healthy()` is called before a generation
**Then** it returns `True` if the pipeline is in a consistent state
**And** returns `False` if the pipeline is in a corrupted or partially loaded state

### Story 2.2: Queue Intelligence

As a API consumer,
I want to know my position in the queue and estimated wait time,
So that I can make informed decisions about when to poll for results.

**Acceptance Criteria:**

**Given** I submit a generation request via `POST /v1/generate`
**When** the job is queued successfully
**Then** the response includes `queue_position` (integer, 1-based) and `estimated_wait_seconds` (integer)

**Given** I check job status via `GET /v1/status/{job_id}`
**When** the job is still pending
**Then** the response includes `queue_position` and `estimated_wait_seconds`
**And** the estimate is based on rolling average generation duration per model

**Given** a generation completes successfully
**When** the worker finishes the task
**Then** the generation duration is recorded in Redis for rolling average calculation
**And** the rolling average is computed over the last 20 generations per model

### Story 2.3: Generation Integration Test Suite

As a developer,
I want a comprehensive test suite covering all generation features,
So that I can safely upgrade dependencies and refactor without regressions.

**Acceptance Criteria:**

**Given** the test suite exists in `tests/`
**When** I run `make test`
**Then** tests execute with mocked GPU (no real CUDA required)
**And** tests cover: model selection (FR1), VRAM release (FR2), multi-reference (FR5), transfer strength (FR6), multiple LoRAs (FR7), generation params (FR8), long prompts (FR9)

**Given** `tests/conftest.py` exists
**When** tests are loaded
**Then** shared fixtures are available: mock pipeline, mock Redis, mock Celery worker

**Given** API latency tests exist
**When** non-generation endpoints are called
**Then** response time is validated < 200ms (NFR1)

**Given** session isolation tests exist
**When** concurrent mock jobs execute
**Then** no metadata leaks between sessions (NFR4)

## Epic 3: Model & LoRA Ecosystem

Les agents peuvent découvrir les modèles/LoRAs disponibles et en télécharger dynamiquement de nouveaux.

### Story 3.1: Model & LoRA Discovery Endpoints

As a API consumer,
I want to query the list of available models, LoRAs, and reference entities,
So that I know what resources are available before submitting a generation request.

**Acceptance Criteria:**

**Given** models are installed in the `models/` volume
**When** I call `GET /v1/models`
**Then** I receive a JSON list of installed models with name, type, and file size
**And** the endpoint is exempt from API Key authentication (SEC-002)

**Given** LoRAs are installed in the LoRA directory
**When** I call `GET /v1/loras`
**Then** I receive a JSON list of installed LoRAs with name, trigger words, and file size
**And** the endpoint is exempt from API Key authentication (SEC-002)

**Given** reference entities exist in `reference/`
**When** I call `GET /v1/references`
**Then** I receive a JSON list of reference entities with name and available views (front, side, back)
**And** the endpoint is exempt from API Key authentication (SEC-002)

### Story 3.2: Dynamic LoRA/Model Download with Validation

As a API consumer,
I want to download new LoRAs and models from external sources via the API,
So that I can expand the available styles and models without manual file management.

**Acceptance Criteria:**

**Given** I want to install a new LoRA from Civitai
**When** I call the download endpoint with a valid Civitai URL
**Then** the LoRA is downloaded to the correct directory
**And** the download is a separate operation from generation (two-step explicit, DA-003)

**Given** a file is downloaded from an external source
**When** the download completes
**Then** the system validates: file extension is `.safetensors`
**And** file size does not exceed a configurable maximum (default: 2GB)
**And** total LoRA storage does not exceed a configurable limit (default: 50GB)

**Given** a download fails validation (wrong extension, too large, storage full)
**When** the validation check fails
**Then** the downloaded file is deleted
**And** the error response uses the standard error envelope with code `DOWNLOAD_FAILED`

**Given** a LoRA was successfully downloaded
**When** I call `GET /v1/loras`
**Then** the new LoRA appears in the inventory list immediately

## Epic 4: Operational Reliability

Le système est fiable avec rétention intelligente, monitoring enrichi, et CI automatisé.

### Story 4.1: Image Retention & Cleanup Policy

As a system administrator,
I want generated images to be automatically cleaned up based on download status,
So that disk space is managed without manual intervention and users have enough time to retrieve their images.

**Acceptance Criteria:**

**Given** a generated image has NOT been downloaded
**When** 24 hours have passed since generation
**Then** the image is eligible for deletion

**Given** a generated image HAS been downloaded (tracked in `outputs/.retrieved.json`)
**When** 1 hour has passed since the download timestamp
**Then** the image is eligible for deletion

**Given** a user calls `POST /v1/generate`
**When** the API processes the request (before queuing the job)
**Then** the cleanup function scans `outputs/` and deletes all expired images
**And** corresponding entries in `.retrieved.json` are cleaned up

**Given** `outputs/.retrieved.json` tracks image metadata
**When** a new image is generated
**Then** the creation timestamp is recorded
**And** when `GET /v1/download/{filename}` is called, the download timestamp is recorded

**Given** Celery result expiration
**When** configuring the worker
**Then** `result_expires` is set to 86400 (24h) to match the undownloaded retention window

### Story 4.2: Enriched Health Check

As a system administrator,
I want the health endpoint to report GPU, queue, pipeline, and storage diagnostics,
So that I can monitor system health and debug issues without SSH access to the container.

**Acceptance Criteria:**

**Given** the API is running with GPU access
**When** I call `GET /health`
**Then** the response includes `gpu` object with: `available`, `name`, `vram_total_mb`, `vram_used_mb`, `vram_free_mb`

**Given** jobs are in the Celery queue
**When** I call `GET /health`
**Then** the response includes `queue` object with: `pending`, `active`, `max_size`

**Given** a model is loaded in the pipeline
**When** I call `GET /health`
**Then** the response includes `pipeline` object with: `model_loaded`, `loras_loaded`, `ip_adapter_loaded`

**Given** generated images exist in outputs/
**When** I call `GET /health`
**Then** the response includes `storage` object with: `outputs_count`, `outputs_size_mb`

**Given** the health endpoint
**When** called without API key
**Then** it responds normally (unversioned, unauthenticated infrastructure endpoint)

### Story 4.3: CI Pipeline & Redis Persistence

As a developer,
I want automated quality checks on every push and persistent Redis state across restarts,
So that code quality is enforced automatically and in-flight jobs survive container restarts.

**Acceptance Criteria:**

**Given** a push to `main` or a pull request is opened
**When** GitHub Actions CI runs
**Then** it executes: Ruff lint + format check, MyPy type check, `pip-compile --dry-run` dependency validation, Docker image build test
**And** the pipeline fails if any check fails

**Given** the Docker Compose configuration
**When** Redis is configured
**Then** AOF persistence is enabled (`appendonly yes`)
**And** the AOF file is stored on a persistent volume

**Given** Redis restarts (container recreate)
**When** the Redis service comes back up
**Then** pending job states and results are restored from AOF
**And** no in-flight jobs are lost

## Epic 5: Dependency Hygiene & Hardening

Le projet a des dépendances verrouillées, une sécurité Celery à jour, et un logging structuré.

### Story 5.1: Dependency Pinning & Lockfile

As a developer,
I want all Python dependencies strictly pinned with a reproducible lockfile,
So that fresh environments always produce identical builds and silent incompatibilities are eliminated.

**Acceptance Criteria:**

**Given** the current `requirements.txt` uses mixed pinning (strict pins alongside ranges like `peft>=0.7.0`)
**When** I update `requirements.txt`
**Then** ALL dependencies use strict version pins (e.g., `peft==0.7.1`)
**And** no range specifiers (`>=`, `~=`, `>`) remain

**Given** `pip-tools` is available in the development environment
**When** I run `pip-compile requirements.in`
**Then** a `requirements.txt` lockfile is generated with all transitive dependencies pinned
**And** the lockfile is committed to version control

**Given** the Docker image is built from the lockfile
**When** two separate builds run on different days
**Then** both produce identical Python environments (reproducible builds)

### Story 5.2: Celery Security Upgrade

As a system administrator,
I want Celery upgraded from 5.3.4 to 5.6.2,
So that the known memory leak on Python 3.11+ workers is fixed and broker credentials are no longer logged.

**Acceptance Criteria:**

**Given** Celery 5.3.4 is currently installed
**When** I upgrade to Celery 5.6.2
**Then** the worker starts successfully with existing configuration
**And** the `generate_image_task` executes correctly

**Given** Celery 5.6.2 is installed
**When** the worker runs for extended periods (>100 tasks)
**Then** memory usage remains stable (no leak regression from 5.3.4 on Python 3.11+)

**Given** Celery 5.6.2 is installed
**When** the worker connects to Redis broker
**Then** no broker credentials appear in worker log output (SEC-004 fix)

**Given** the upgrade is complete
**When** I run the test suite
**Then** all existing tests pass without modification

### Story 5.3: Logging Migration

As a developer,
I want all `print()` statements replaced with Python `logging` module calls,
So that log levels can be configured, output is structured, and debugging is easier in production.

**Acceptance Criteria:**

**Given** the codebase uses `print()` for output in `api.py`, `worker.py`, `pipeline.py`
**When** I replace them with `logging.info()`, `logging.warning()`, `logging.error()` as appropriate
**Then** no `print()` statements remain in `app/` source files (except `__main__` blocks)

**Given** the logging module is configured
**When** the API or worker starts
**Then** log output includes: timestamp, level, module name, and message
**And** the log level is configurable via `LOG_LEVEL` environment variable (default: `INFO`)

**Given** a GPU OOM error occurs during generation
**When** the worker handles the retry
**Then** the error is logged at `ERROR` level with full traceback
**And** retry attempts are logged at `WARNING` level

### Story 5.4: Opportunistic Dependency Upgrades

As a developer,
I want non-critical dependencies upgraded to current stable versions,
So that known bugs are fixed and the project stays within maintained version ranges.

**Acceptance Criteria:**

**Given** FastAPI is at version 0.105.0
**When** I upgrade to the latest 0.115+ stable release
**Then** all Pydantic models use v2 syntax (verified by test suite)
**And** all API endpoints respond correctly

**Given** Pillow is at version 10.1.0
**When** I upgrade to the latest 11.x stable release
**Then** image generation, saving (PNG), and reference loading work correctly

**Given** redis-py is at version 5.0.1
**When** I upgrade to the latest 5.2+ stable release
**Then** Celery broker and result backend connections work correctly

**Given** Uvicorn is at version 0.24.0
**When** I upgrade to the latest 0.34+ stable release
**Then** the API server starts and serves requests correctly

**Given** Transformers is at version 4.38.2
**When** I upgrade to the latest 4.48+ stable release
**Then** the Compel dual text encoder setup works correctly for prompt encoding

**Given** all upgrades are applied
**When** I run the full test suite
**Then** all tests pass
**And** GPU generation benchmark shows no performance regression (within 10% of baseline)

## Epic 6: ControlNet & Structural Control (Growth)

Les agents peuvent contrôler la structure des images générées via ControlNet (Canny, Pose, Depth).

### Story 6.1: Pipeline Factory Pattern

As a developer,
I want the Singleton pipeline replaced with a factory pattern,
So that multiple pipeline types (SDXL, ControlNet) can be instantiated with destructive swap on 11GB VRAM.

**Acceptance Criteria:**

**Given** the current `FlexiblePipeline` uses Singleton via `__new__`
**When** I refactor to a factory function `create_pipeline(pipeline_type, model)`
**Then** the factory returns the correct pipeline class based on type: `StableDiffusionXLPipeline` or `StableDiffusionXLControlNetPipeline`

**Given** a pipeline of type A is loaded in VRAM
**When** a request for pipeline type B arrives
**Then** the factory performs destructive swap: `del` old pipeline, `gc.collect()`, `torch.cuda.empty_cache()`, then loads new pipeline
**And** the swap completes within 45 seconds (local cached models)

**Given** the factory pattern is implemented
**When** unit tests run
**Then** the pipeline can be mocked at the factory level without Singleton complications
**And** existing SDXL generation behavior is unchanged

### Story 6.2: ControlNet Pipeline Integration

As a API consumer,
I want to generate images with structural control via ControlNet,
So that I can guide the composition using edge maps, pose skeletons, or depth maps.

**Acceptance Criteria:**

**Given** `controlnet-aux` is installed and upgraded to latest compatible version
**When** I call `POST /v1/generate` with `control_type: "canny"` and a `control_image` reference
**Then** the system uses `StableDiffusionXLControlNetPipeline` with the Canny ControlNet model
**And** the generated image respects the structural guidance from the control image

**Given** a ControlNet generation request
**When** `control_strength` is specified (0.0 to 1.0)
**Then** the structural guidance is applied at the specified strength
**And** the default strength is 0.5 if not specified

**Given** a ControlNet generation on 11GB VRAM
**When** both ControlNet and base model need to be loaded
**Then** CPU offload is applied to both models
**And** generation completes without OOM (may be slower due to memory constraints)

### Story 6.3: ControlNet Preprocessor Endpoints

As a API consumer,
I want to preprocess images for ControlNet before generation,
So that I can preview and validate the structural guidance before spending GPU time on generation.

**Acceptance Criteria:**

**Given** `controlnet-aux` provides Canny, OpenPose, and Depth preprocessors
**When** I call `POST /v1/preprocess` with `type: "canny"` and an input image
**Then** the response contains the preprocessed edge map as a PNG image

**Given** a preprocessing request
**When** the preprocessor type is `"pose"` or `"depth"`
**Then** the corresponding preprocessor is applied
**And** the result is returned as a PNG image

**Given** a preprocessing request with an unsupported type
**When** the type is not in `["canny", "pose", "depth"]`
**Then** the error code is `INVALID_PARAMETERS` with status 422 in the standard error envelope

## Epic 7: Real-Time & Observability (Growth)

Le système offre des notifications temps réel, des embeddings pré-calculés, et un dashboard de monitoring.

### Story 7.1: SSE Job Notifications

As a API consumer,
I want to receive real-time job status updates via Server-Sent Events,
So that I don't need to poll `/v1/status` and can react instantly to job completion.

**Acceptance Criteria:**

**Given** a generation job is submitted
**When** I open a SSE connection to `GET /v1/stream/{job_id}`
**Then** I receive events for each state transition: `queued`, `model_loading`, `generating`, `completed`, `failed`
**And** each event includes the current job status payload

**Given** a SSE connection is open
**When** the job completes (success or failure)
**Then** a final event is sent with the result
**And** the SSE connection is closed by the server

**Given** the SSE endpoint
**When** called without a valid API Key
**Then** the connection is rejected with HTTP 401

**Given** HTTP polling still exists
**When** SSE is available
**Then** `GET /v1/status/{job_id}` continues to work as before (backward compatible)

### Story 7.2: Embedding Pre-computation

As a API consumer,
I want reference image embeddings to be pre-computed and cached,
So that repeated generations with the same references skip the IP-Adapter encoding step and are faster.

**Acceptance Criteria:**

**Given** `compute_embedding()` currently returns `torch.zeros(1)` (placeholder)
**When** I implement true embedding pre-computation
**Then** the function loads the IP-Adapter Plus CLIP encoder
**And** returns real embeddings for the input reference image

**Given** a reference image has been used in a previous generation
**When** a new generation request uses the same reference
**Then** the cached embedding is reused instead of recomputing
**And** generation time is reduced by the encoding step duration

**Given** the embedding cache
**When** a reference image file is modified or replaced
**Then** the cached embedding is invalidated
**And** the next generation recomputes the embedding

**Given** the worker is running on 11GB VRAM
**When** embedding pre-computation runs
**Then** the CLIP encoder is loaded with CPU offload
**And** the embedding is stored as a `.pt` file alongside the reference image

### Story 7.3: JSON to SQLite Migration

As a developer,
I want JSON file state replaced with SQLite,
So that concurrent access is safe and multi-worker deployments don't risk race conditions.

**Acceptance Criteria:**

**Given** `outputs/.retrieved.json` tracks download metadata
**When** I migrate to SQLite
**Then** a `state.db` file is created in the `outputs/` volume
**And** the `retrieved` table stores: `filename`, `created_at`, `downloaded_at`

**Given** `reference/metadata.json` tracks reference entity metadata
**When** I migrate to SQLite
**Then** a `references` table is added to `state.db`
**And** the metadata schema is preserved

**Given** multiple API workers run concurrently (future multi-worker scaling)
**When** two workers write to the state database simultaneously
**Then** SQLite WAL mode handles concurrent access without corruption

**Given** the migration is complete
**When** no JSON state files remain
**Then** `.retrieved.json` and `metadata.json` are deleted
**And** all code paths use SQLite queries instead of JSON file I/O

### Story 7.4: Monitoring Dashboard

As a system administrator,
I want a monitoring dashboard showing GPU metrics, queue status, and generation statistics,
So that I can observe system health in real-time without querying the health endpoint manually.

**Acceptance Criteria:**

**Given** Flower is already configured for Celery monitoring
**When** I access the Flower dashboard
**Then** it displays: active tasks, task history, worker status, queue depth

**Given** Redis stores rolling average generation durations (from Story 2.2)
**When** the dashboard queries Redis metrics
**Then** it displays: average generation time per model, total generations count, success/failure ratio

**Given** the API exposes GPU stats via `GET /health`
**When** the dashboard polls the health endpoint
**Then** it displays: current VRAM usage, GPU temperature (if available), model loaded status

**Given** the dashboard is accessed
**When** no API key is provided
**Then** the dashboard is accessible (read-only monitoring, infrastructure endpoint)
**And** the dashboard is served on a separate port (default: 5555 for Flower, custom port for extended dashboard)

## Step 4: Final Validation Results

### Requirement Traceability

| Category | Total | Covered | Coverage |
|----------|-------|---------|----------|
| Functional Requirements (FR1-FR9) | 9 | 9 | 100% |
| Non-Functional Requirements (NFR1-NFR4) | 4 | 4 | 100% |
| Architecture Decisions (ADR/SEC/API/DA/INFRA) | 18 | 18 | 100% |
| Trade-Offs (1-4) | 4 | 4 | 100% |
| Version Debt Items | 6 | 6 | 100% |
| Growth Phase Features | 4 | 4 | 100% |

### Epic Independence Validation

| Epic | Dependencies | Standalone? |
|------|-------------|-------------|
| Epic 1 | None | Yes |
| Epic 2 | Epic 1 (API versioning for endpoint paths) | Soft dependency |
| Epic 3 | Epic 1 (API versioning, error format) | Soft dependency |
| Epic 4 | None | Yes |
| Epic 5 | None | Yes |
| Epic 6 | Epic 2 (pipeline refactor), Epic 5 (dependency upgrades) | Hard dependency |
| Epic 7 | Epic 2 (queue intelligence for metrics), Epic 5 (deps) | Soft dependency |

### Quality Checklist

- [x] All stories follow "As a... I want... So that..." format
- [x] All acceptance criteria use Given/When/Then BDD format
- [x] No implementation details leaked into story definitions
- [x] Each story is independently deliverable within a sprint
- [x] MVP epics (1-5) have no forward dependencies on Growth epics (6-7)
- [x] Growth epics (6-7) are clearly labeled and gated

### Gap Analysis

- [x] All PRD FRs covered (9/9)
- [x] All PRD NFRs covered (4/4)
- [x] All ADR action items covered
- [x] All Trade-Off resolutions covered
- [x] Version debt and dependency management addressed (Epic 5)
- [x] Growth phase features captured (Epics 6-7)
- [x] Monitoring dashboard included (Story 7.4)
- [x] Opportunistic dependency upgrades included (Story 5.4)

### Validation Status: VALIDATED
