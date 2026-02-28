from dataclasses import dataclass

@dataclass
class Project:
    id: str
    name: str
    slug: str | None
    description: str | None
    created_at: int
    updated_at: int
    metadata_json: str | None = None
    tags_json: str | None = None
    storage_mode: str | None = "inherit"
    header_color: str | None = None
    archived_at: int | None = None
