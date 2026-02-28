PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS workflow_definition (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    deleted_at INTEGER NULL
);

CREATE TABLE IF NOT EXISTS workflow_version (
    id TEXT PRIMARY KEY,
    workflow_id TEXT NOT NULL REFERENCES workflow_definition(id),
    version INTEGER NOT NULL,
    graph_hash TEXT NOT NULL,
    original_graph_json TEXT NOT NULL,
    detected_inputs_json TEXT NOT NULL,
    detected_outputs_json TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    UNIQUE(workflow_id, version)
);

CREATE TABLE IF NOT EXISTS workflow_app (
    id TEXT PRIMARY KEY,
    workflow_version_id TEXT NOT NULL REFERENCES workflow_version(id),
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    ui_config_json TEXT NOT NULL,
    default_inputs_json TEXT,
    default_outputs_json TEXT,
    is_public INTEGER NOT NULL,
    created_at INTEGER NOT NULL,
    app_version TEXT NOT NULL DEFAULT '1.0.0',
    comfyui_url TEXT,
    header_color TEXT
);

CREATE TABLE IF NOT EXISTS project (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT,
    description TEXT,
    created_at INTEGER NOT NULL,
    updated_at INTEGER NOT NULL,
    metadata_json TEXT,
    tags_json TEXT,
    storage_mode TEXT DEFAULT 'inherit',
    header_color TEXT,
    archived_at INTEGER NULL
);

CREATE TABLE IF NOT EXISTS run (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES project(id),
    workflow_version_id TEXT NOT NULL REFERENCES workflow_version(id),
    app_id TEXT REFERENCES workflow_app(id),
    status TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    prompt_id TEXT,
    seed INTEGER,
    images_json TEXT,
    execution_time REAL,
    error TEXT,
    queue_position INTEGER,
    input_snapshot_json TEXT,
    metadata_snapshot_json TEXT,
    run_group_id TEXT,
    comfyui_url TEXT,
    local_storage_status TEXT DEFAULT 'none',
    remote_status TEXT DEFAULT 'unknown',
    local_path TEXT
);

CREATE INDEX IF NOT EXISTS idx_workflow_definition_name ON workflow_definition(name);
CREATE INDEX IF NOT EXISTS idx_workflow_version_workflow_id ON workflow_version(workflow_id);
CREATE INDEX IF NOT EXISTS idx_workflow_app_slug ON workflow_app(slug);
CREATE TABLE IF NOT EXISTS app_preset (
    id TEXT PRIMARY KEY,
    app_id TEXT NOT NULL REFERENCES workflow_app(id),
    name TEXT NOT NULL,
    description TEXT,
    keys_json TEXT NOT NULL,
    values_json TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_run_app_id ON run(app_id);
CREATE INDEX IF NOT EXISTS idx_run_prompt_id ON run(prompt_id);
CREATE INDEX IF NOT EXISTS idx_project_slug ON project(slug);
CREATE INDEX IF NOT EXISTS idx_app_preset_app_id ON app_preset(app_id);
/* idx_run_project_id is created in migrate.py when run table is recreated */
