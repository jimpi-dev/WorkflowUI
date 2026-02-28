# WorkflowUI Docker

This folder contains everything needed to build and run WorkflowUI in a container.

## Build

From the **parent directory** (WorkflowUI), so the build context includes `frontend/`, `backend/`, and `app.config.json`:

```bash
docker build -f docker/Dockerfile -t workflowui .
```

## Run

### With docker run

```bash
docker run -p 3000:3000 workflowui
```

Open http://localhost:3000. To persist the database and optional data (one shared volume):

```bash
docker run -p 3000:3000 \
  -v workflowui-data:/data \
  -e WORKFLOWUI_DB_PATH=/data/workflow.db \
  -e MEDIA_STORAGE_ROOT_PATH=/data/media_storage \
  -e INPUT_DATA_DIR=/data/input_data \
  workflowui
```

Or use separate mounts for media storage and input images:

```bash
docker run -p 3000:3000 \
  -v workflowui-data:/data \
  -v workflowui-media:/media \
  -v workflowui-inputs:/inputs \
  -e WORKFLOWUI_DB_PATH=/data/workflow.db \
  -e MEDIA_STORAGE_ENABLED=true \
  -e MEDIA_STORAGE_ROOT_PATH=/media \
  -e INPUT_DATA_DIR=/inputs \
  workflowui
```

### With docker-compose

Copy the example env file and start:

```bash
cp .env.example .env
# Edit .env if needed (port, ComfyUI URL, paths)
docker-compose up -d
```

Open http://localhost:3000 (or the port you set in `.env` as `WEB_APP_PORT`).

**Persistent data:** You can use one shared volume or separate mounts. Each path is just a directory in the container—point it to whichever mount you use.

- **One volume:** Mount `workflowui-data` at `/data` and set `WORKFLOWUI_DB_PATH=/data/workflow.db`, `INPUT_DATA_DIR=/data/input_data`, `MEDIA_STORAGE_ROOT_PATH=/data/media_storage` (and `MEDIA_STORAGE_ENABLED=true`).
- **Separate mounts:** Add more volumes (e.g. `workflowui-media:/media`, `workflowui-inputs:/inputs`) in `docker-compose.yml`, then set `MEDIA_STORAGE_ROOT_PATH=/media` and `INPUT_DATA_DIR=/inputs`. The media storage root and input data dir can each have their own mount.

## Configurable environment variables

| Variable | Purpose | Default |
|----------|---------|---------|
| **PORT** | Port the app listens on inside the container | 3000 |
| **WORKFLOWUI_DB_PATH** | (Optional) SQLite DB file path; unset = app default | (none) |
| **COMFYUI_URL** | ComfyUI base URL | http://localhost:8188/ |
| **INPUT_DATA_DIR** | Directory for uploaded input media (images, etc.) | input_data |
| **MEDIA_STORAGE_ENABLED** | Enable local media storage | false |
| **MEDIA_STORAGE_ROOT_PATH** | Root path for local storage (saved outputs); use `/data/media_storage` with the volume mount | media_storage |
| **MEDIA_STORAGE_DELETE_REMOTE** | Delete on ComfyUI after save | false |

When ComfyUI runs on the host, use `COMFYUI_URL=http://host.docker.internal:8188/` (Docker Desktop) or the host’s IP.

WorkflowUI plugin minimum version is **not** configurable via env; it is fixed in application code.
