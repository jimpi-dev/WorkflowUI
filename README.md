# WorkflowUI

**Turn ComfyUI workflows into web apps.** Import workflow JSON, build custom apps with forms and defaults, run workflows through a queue, and organize results in projects.

**WorkflowUI enables you to simplify access to ComfyUI workflows and share them with others.**

---

## Features

| Area                   | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
|------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Import**             | Import ComfyUI workflows directly by browsing from ComfyUI backend or as exported API format. the app analyzes inputs/outputs and stores versioned workflow definitions. Idempotent import (same graph hash = no duplicate version).                                                                                                                                                                                                                                                                                                                                                                                        |
| **Metadata 2.0**       | Workflow and Apps-MetaData can be shared with each downloaded image, share the images to allow others to recreate the same image with the same workflow and apps and its parameters! <br/> <br/> ComfyUI Metadata is untouched and remains full compatible with ComfyUI!  <br/> <br/> ⚠️ <mark> ***Install the [WorkflowUIPlugin](https://github.com/jimpi-dev/WorkflowUIPlugin)*** for best metadata support, in order to be able to reproduce a generation, the metadata will contain as much information as possible! Search for "WorkflowUIPlugin" on ComfyUI custom nodes manager! </mark> |
| **Workflows**          | Stored definitions and versions with detected inputs/outputs; view and manage from the Workflows page.                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| **Apps**               | Create *Apps* from any imported workflow version: custom title, form layout, default values. Open any app by its name.                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| **Projects**           | Organize runs in named projects (name, description, tags) or use  "Quick runs" which is a built-in project for one-off generations.                                                                                                                                                                                                                                                                                                                                                                                                                                              |
| **Generation Lineage** | Generated output can be used as input for another app, the application preserves the lineage. You can follow each generations history! Isnt this great?                                                                                                                                                                                                                                                                                                                                                                                                                          
| **Queued execution**   | Queueing System! - Enqueue as much generations as you want and manage your queue, you can even pause the queue and resume your generations the next time you start the App!                                                                                                                                                                                                                                                                                                                                                    
| **Media & config**     | Optional local media storage; backend proxies ComfyUI `/view` and `/upload/image`; multi-ComfyUI via app-level URL. *requires [WorkflowUIPlugin](https://github.com/jimpi-dev/WorkflowUIPlugin) for best functionality                                                                                                                                                                                                                                                                                                                                                           |

Hint: To toggle the theme, you have click on a certain part of the apps logo

## Upcoming features
- Constantly adding support for more node classes! Check for updates!
- Create and use App Presets! Save your favorite values into fully customizable App presets
- App repository - share workflows/apps with others
- When importing a workflow, check for used models (checkpoints, clip, vae) and highlight models not found for better user experience
- Multi tenancy
- Better UI on mobile devices (its not great right now, but it does work 🫡)
- Improve media viewer, maybe even integrate custom media gallery
- Notify about new version available
- More DB Connectors, e.g. Postgres support
- More sophisticated queueing system (store queue to db, multi user queuing for single and multi comfy instances)

## Known Issues
- Media does sometimes not show up in the gallery, only page reload fixes it, will be fixed in next release
- Only one Seed value (Master Seed) can be generated and passed to ComfyUI, will be made more configurable
- Edge cases on media deletion on local storage 

## Sneak peek - App and Features

![Send to App Flow](./Docs/AppsBoth.jpg)
![Send to App Flow](./Docs/CreateAppBoth.jpg)
![Send to App Flow](./Docs/AppComplexity.jpg)
![Send to App Flow](./Docs/QuickRunsBoth.jpg)
![Send to App Flow](./Docs/MixedProjectComfyConsole.jpg)
![Send to App Flow](./Docs/ComfyConsoleAndQueue.png)
![Send to App Flow](./Docs/SendToAppFlow.jpg)
![Send to App Flow](./Docs/HonorableMentions.jpg)

---

## Prerequisites


| Component    | Required                                                          |
|--------------|-------------------------------------------------------------------|
| **Backend**  | **Python 3.x** (e.g. 3.10+) and **pip**                           |
| **Frontend** | **Node.js** (LTS, e.g. 18+) and **npm**                           |
| **ComfyUI**  | **ComfyUI** (running on any network accessible from your machine) |


### ComfyUI Plugin
To use the full feature set of WorkflowUI, you need to install the ComfyUI plugin
which can be found here: [WorkflowUIPlugin](https://github.com/jimpi-dev/WorkflowUIPlugin)

---

### Docker

Run WorkflowUI in a single container (frontend built as static files, served by the backend).

⚠️ **check the config parameters tables, in order to understand the possible env variables to be provided with the docker image**

 Find the [docker image on the docker hub](https://hub.docker.com/r/jimpi/workflowui)

### Build with dockerfile

**Build** (from project root):

```bash
docker build -f docker/Dockerfile -t workflowui .
```

---

## Quick Start (for non docker users)

### install

**Windows (PowerShell):**

```powershell
.\install.ps1
```

**Linux / macOS:**

```bash
chmod +x install.sh start.sh
./install.sh
```

This installs:
- Backend: `pip install -r backend/requirements.txt`
- Frontend: `npm install` in `frontend/`

### 3. Start the application

**Windows (PowerShell):**

```powershell
.\start.ps1
```

Two windows open (backend + frontend). Close them to stop.

**Linux / macOS:**

```bash
./start.sh
```
---

## Configuration

### Frontend: `app.config.json` (project root)

Edit before starting or rebuilding the frontend.

| Option | Description |
|--------|-------------|
| `backendUrl` | Backend API base URL (e.g. `http://localhost:8000`). Empty = same origin (e.g. behind reverse proxy). Can be overridden at dev/runtime via `BACKEND_URL` env. |

After changing `app.config.json`, restart the dev server or run `npm run build` in `frontend/`.

### Backend: `.env` (project root)

Optional. Copy from `.env.example`:

| Variable | Description                                                                                                                                         |
|----------|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| `COMFYUI_URL` | ComfyUI API URL (default: `http://localhost:8188/`).                                                                                                |
| `MEDIA_STORAGE_ENABLED` | `true` / `false` — enables local media storage options, if false the user cannot download generated media to the applications media storage folder. |
| `MEDIA_STORAGE_ROOT_PATH` | Root directory for local media (default: `media_storage`).                                                                                          |
| `MEDIA_STORAGE_DELETE_REMOTE` | Delete remote files after successful local save.                                                                                                    |
| `INPUT_DATA_DIR` | Directory for uploaded media (default: `input_data`).                                                                                               |
| `WORKFLOWUI_EMBED_METADATA_ON_DOWNLOAD` | Append metadata when user downloads image from UI. This settings can be turned on/off on App-Level.                                                 |
| `WORKFLOWUI_EMBED_METADATA_ON_SAVE` | Append metadata when saving run to local storage (using save icon). This settings can be turned on/off on App-Level.                                                                               |
| `WORKFLOWUI_CORS_ORIGINS` | Optional. Comma-separated list of allowed frontend origins for CORS (e.g. `http://localhost:5173,http://127.0.0.1:5173`). Defaults to these two when unset. |
| `WORKFLOWUI_AUTH_ENABLED` | Optional auth feature flag. When true, users must authenticate before accessing app content/API. |
| `WORKFLOWUI_AUTH_ENABLED` | Optional auth feature flag. When true, users must authenticate before accessing app content/API. |
| `WORKFLOWUI_AUTH_SECRET` | Secret used for signing auth tokens. Set a strong value in production. |
| `WORKFLOWUI_AUTH_TOKEN_TTL_SECONDS` | Taken lifetime in seconds (default `86400`). |
| `WORKFLOWUI_AUTH_ADMIN_USERNAME` | Bootstrap admin username (created automatically if missing). |
| `WORKFLOWUI_AUTH_ADMIN_PASSWORD` | Bootstrap admin password (change immediately in production). |

### Changing dev ports without CORS issues

- The helper scripts `start.ps1` (Windows) and `start.sh` (Linux/macOS) define backend and frontend dev ports at the top of the file (`BackendPort`/`BACKEND_PORT` and `FrontendPort`/`FRONTEND_PORT`).
- When you change these values and run the script:
  - The backend is started on the chosen backend port and gets `WORKFLOWUI_CORS_ORIGINS` set to match the frontend origin(s) on that port.
  - The frontend dev server (Vite/SvelteKit) is started on the chosen frontend port and receives:
    - `BACKEND_URL=http://localhost:<BackendPort>` so proxy/API calls hit the correct backend.
    - `FRONTEND_PORT`/`PORT` to bind Vite to the desired port.
- This means any user cloning the repo can adjust only those two variables in the start script and avoid CORS errors when using non-default dev ports.

## Tech stack

- **Backend:** [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/), SQLite
- **Frontend:** [SvelteKit](https://kit.svelte.dev/), [Svelte 5](https://svelte.dev/), [Vite](https://vitejs.dev/)
- **Integration:** ComfyUI HTTP API (queue, prompt, history, view, upload) + **WorkflowUIPlugin**

---

## Documentation
- The application 'home' page does feature a blog style content, sharing updates and knowledge in the future.

---

## License

See [LICENSE](LICENSE) in this repository
