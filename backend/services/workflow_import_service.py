import json
import time
import uuid
from typing import Any

from services.graph_hash import graph_hash
from services.workflow_analyzer import analyze_workflow, _normalize_to_api_format

class ImportResult:
    def __init__(
        self,
        workflow_id: str,
        version: int,
        graph_hash: str,
        detected_inputs: list[Any],
        detected_outputs: list[Any],
        workflow_version_id: str,
        is_new: bool,
        *,
        internal_nodes: list[Any] | None = None,
    ):
        self.workflow_id = workflow_id
        self.version = version
        self.graph_hash = graph_hash
        self.detected_inputs = detected_inputs
        self.detected_outputs = detected_outputs
        self.workflow_version_id = workflow_version_id
        self.is_new = is_new
        self.internal_nodes = internal_nodes or []


class WorkflowImportService:
    def __init__(self, workflow_repo: Any):
        self._repo = workflow_repo

    def preview_import(self, name: str, graph: dict[str, Any]) -> dict[str, Any]:
        if not name or not name.strip():
            raise ValueError("name is required")
        if not isinstance(graph, dict) or not graph:
            raise ValueError("graph must be a non-empty object")
        new_hash = graph_hash(graph)
        analyzed = analyze_workflow(graph)
        detected_inputs = analyzed["inputs"]
        detected_outputs = analyzed["outputs"]
        internal_nodes = analyzed.get("internal_nodes") or []
        existing = self._repo.get_workflow_by_name(name.strip())
        if existing is None:
            return {
                "graph_hash": new_hash,
                "detected_inputs": detected_inputs,
                "detected_outputs": detected_outputs,
                "internal_nodes": internal_nodes,
                "is_new_workflow": True,
                "is_new_version": True,
                "existing_workflow_id": None,
                "existing_version": None,
            }
        latest = self._repo.get_latest_version(existing.id)
        if latest is None:
            return {
                "graph_hash": new_hash,
                "detected_inputs": detected_inputs,
                "detected_outputs": detected_outputs,
                "internal_nodes": internal_nodes,
                "is_new_workflow": False,
                "is_new_version": True,
                "existing_workflow_id": existing.id,
                "existing_version": None,
            }
        if latest.graph_hash == new_hash:
            return {
                "graph_hash": new_hash,
                "detected_inputs": detected_inputs,
                "detected_outputs": detected_outputs,
                "internal_nodes": internal_nodes,
                "is_new_workflow": False,
                "is_new_version": False,
                "existing_workflow_id": existing.id,
                "existing_version": latest.version,
            }
        return {
            "graph_hash": new_hash,
            "detected_inputs": detected_inputs,
            "detected_outputs": detected_outputs,
            "internal_nodes": internal_nodes,
            "is_new_workflow": False,
            "is_new_version": True,
            "existing_workflow_id": existing.id,
            "existing_version": latest.version,
        }

    def import_workflow(
        self, name: str, graph: dict[str, Any], *, force_new_version: bool = False, created_from_image_import: bool = False
    ) -> ImportResult:
        if not name or not name.strip():
            raise ValueError("name is required")
        if not isinstance(graph, dict) or not graph:
            raise ValueError("graph must be a non-empty object")

        graph = _normalize_to_api_format(graph)
        new_hash = graph_hash(graph)
        analyzed = analyze_workflow(graph)
        detected_inputs = analyzed["inputs"]
        detected_outputs = analyzed["outputs"]
        internal_nodes = analyzed.get("internal_nodes") or []
        detected_inputs_json = json.dumps(detected_inputs)
        detected_outputs_json = json.dumps(detected_outputs)
        created_at_ms = int(time.time() * 1000)

        existing = self._repo.get_workflow_by_name(name.strip())

        if existing is None:
            wf_id = str(uuid.uuid4())
            version_id = str(uuid.uuid4())
            original_graph_json = json.dumps(graph)

            def do_create(conn: Any) -> None:
                self._repo.create_workflow_definition(wf_id, name.strip(), created_at_ms, conn=conn, created_from_image_import=created_from_image_import)
                self._repo.create_workflow_version(
                    version_id,
                    wf_id,
                    1,
                    new_hash,
                    original_graph_json,
                    detected_inputs_json,
                    detected_outputs_json,
                    created_at_ms,
                    conn=conn,
                )

            self._repo.run_in_transaction(do_create)
            return ImportResult(
                workflow_id=wf_id,
                version=1,
                graph_hash=new_hash,
                detected_inputs=detected_inputs,
                detected_outputs=detected_outputs,
                workflow_version_id=version_id,
                is_new=True,
                internal_nodes=internal_nodes,
            )

        latest = self._repo.get_latest_version(existing.id)
        if latest is None:
            raise RuntimeError("Workflow definition has no version")
        if latest.graph_hash == new_hash and not force_new_version:
            reanalyzed = analyze_workflow(json.loads(latest.original_graph_json))
            raise IdempotentImport(
                workflow_id=existing.id,
                version=latest.version,
                graph_hash=latest.graph_hash,
                workflow_version_id=latest.id,
                detected_inputs=json.loads(latest.detected_inputs_json),
                detected_outputs=json.loads(latest.detected_outputs_json),
                internal_nodes=reanalyzed.get("internal_nodes") or [],
            )

        version_id = str(uuid.uuid4())
        new_version = latest.version + 1
        original_graph_json = json.dumps(graph)
        self._repo.create_workflow_version(
            version_id,
            existing.id,
            new_version,
            new_hash,
            original_graph_json,
            detected_inputs_json,
            detected_outputs_json,
            created_at_ms,
        )
        return ImportResult(
            workflow_id=existing.id,
            version=new_version,
            graph_hash=new_hash,
            detected_inputs=detected_inputs,
            detected_outputs=detected_outputs,
            workflow_version_id=version_id,
            is_new=True,
            internal_nodes=internal_nodes,
        )


class IdempotentImport(Exception):
    def __init__(
        self,
        workflow_id: str,
        version: int,
        graph_hash: str,
        workflow_version_id: str,
        detected_inputs: list[Any],
        detected_outputs: list[Any],
        *,
        internal_nodes: list[Any] | None = None,
    ):
        self.workflow_id = workflow_id
        self.version = version
        self.graph_hash = graph_hash
        self.workflow_version_id = workflow_version_id
        self.detected_inputs = detected_inputs
        self.detected_outputs = detected_outputs
        self.internal_nodes = internal_nodes or []
        super().__init__("Import is duplicate of latest version")
