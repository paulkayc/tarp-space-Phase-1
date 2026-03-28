from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.auth import get_current_user_id

router = APIRouter()


NodeType = Literal[
    "start",
    "end",
    "agent",
    "classify",
    "if_else",
    "tool",
    "guardrail",
    "transform",
    "set_state",
    "user_approval",
    "loop",
]


class GraphNode(BaseModel):
    id: str = Field(min_length=1)
    type: NodeType
    name: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    label: str | None = None
    condition: str | None = None


class GraphPayload(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]


class BuilderProjectCreate(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    description: str | None = None


class BuilderProjectResponse(BaseModel):
    id: str
    name: str
    description: str | None
    status: str
    owner_id: str
    created_at: datetime
    updated_at: datetime


class BuilderVersionCreate(BaseModel):
    graph: GraphPayload
    notes: str | None = None


class BuilderVersionResponse(BaseModel):
    id: str
    project_id: str
    version_number: int
    status: str
    notes: str | None
    schema_version: str
    created_at: datetime
    graph: GraphPayload


class ValidateResponse(BaseModel):
    valid: bool
    errors: list[str]
    warnings: list[str]


class SimulateRequest(BaseModel):
    input_text: str = Field(min_length=1)


class SimulateResponse(BaseModel):
    run_id: str
    status: str
    trace: list[dict[str, Any]]
    output: dict[str, Any]


class GenerateResponse(BaseModel):
    artifact_hash: str
    files: dict[str, str]


class ImportResponse(BaseModel):
    imported: bool
    agent_slug: str
    runtime_registration: dict[str, Any]


class PublishResponse(BaseModel):
    published: bool
    published_at: datetime
    version_id: str


@dataclass
class BuilderProject:
    id: UUID
    owner_id: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass
class BuilderVersion:
    id: UUID
    project_id: UUID
    version_number: int
    status: str
    notes: str | None
    schema_version: str
    created_at: datetime
    graph: GraphPayload


@dataclass
class BuilderRun:
    id: UUID
    version_id: UUID
    status: str
    trace: list[dict[str, Any]] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)


class AgentBuilderStore:
    """In-memory repository for builder resources.

    This keeps the feature functional in Phase 1 without requiring migrations,
    while preserving API contracts that can later be backed by SQLAlchemy.
    """

    projects: dict[UUID, BuilderProject] = {}
    versions: dict[UUID, BuilderVersion] = {}
    project_versions: dict[UUID, list[UUID]] = {}
    runs: dict[UUID, BuilderRun] = {}

    @classmethod
    def create_project(cls, owner_id: UUID, name: str, description: str | None) -> BuilderProject:
        now = datetime.now(timezone.utc)
        project = BuilderProject(
            id=uuid4(),
            owner_id=owner_id,
            name=name,
            description=description,
            status="draft",
            created_at=now,
            updated_at=now,
        )
        cls.projects[project.id] = project
        cls.project_versions[project.id] = []
        return project

    @classmethod
    def get_project(cls, owner_id: UUID, project_id: UUID) -> BuilderProject:
        project = cls.projects.get(project_id)
        if project is None or project.owner_id != owner_id:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Project not found"})
        return project

    @classmethod
    def list_projects(cls, owner_id: UUID) -> list[BuilderProject]:
        return [p for p in cls.projects.values() if p.owner_id == owner_id]

    @classmethod
    def create_version(cls, project: BuilderProject, payload: BuilderVersionCreate) -> BuilderVersion:
        existing = cls.project_versions.get(project.id, [])
        version = BuilderVersion(
            id=uuid4(),
            project_id=project.id,
            version_number=len(existing) + 1,
            status="draft",
            notes=payload.notes,
            schema_version="1.0",
            created_at=datetime.now(timezone.utc),
            graph=payload.graph,
        )
        cls.versions[version.id] = version
        cls.project_versions[project.id].append(version.id)
        project.updated_at = datetime.now(timezone.utc)
        return version

    @classmethod
    def get_version(cls, owner_id: UUID, version_id: UUID) -> BuilderVersion:
        version = cls.versions.get(version_id)
        if version is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Version not found"})
        cls.get_project(owner_id=owner_id, project_id=version.project_id)
        return version


def _to_project_response(project: BuilderProject) -> BuilderProjectResponse:
    return BuilderProjectResponse(
        id=str(project.id),
        name=project.name,
        description=project.description,
        status=project.status,
        owner_id=str(project.owner_id),
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def _to_version_response(version: BuilderVersion) -> BuilderVersionResponse:
    return BuilderVersionResponse(
        id=str(version.id),
        project_id=str(version.project_id),
        version_number=version.version_number,
        status=version.status,
        notes=version.notes,
        schema_version=version.schema_version,
        created_at=version.created_at,
        graph=version.graph,
    )


def _validate_graph(graph: GraphPayload) -> ValidateResponse:
    errors: list[str] = []
    warnings: list[str] = []

    node_ids = {n.id for n in graph.nodes}
    starts = [n for n in graph.nodes if n.type == "start"]
    ends = [n for n in graph.nodes if n.type == "end"]

    if len(starts) != 1:
        errors.append("Graph must have exactly one start node.")
    if len(ends) < 1:
        errors.append("Graph must have at least one end node.")

    outgoing: dict[str, list[GraphEdge]] = {n.id: [] for n in graph.nodes}
    for edge in graph.edges:
        if edge.source not in node_ids or edge.target not in node_ids:
            errors.append(f"Edge {edge.source} -> {edge.target} references unknown node id.")
            continue
        outgoing[edge.source].append(edge)

    for node in graph.nodes:
        if node.type != "end" and len(outgoing[node.id]) == 0:
            errors.append(f"Node '{node.name}' has no outgoing edge.")

    guardrail_count = sum(1 for node in graph.nodes if node.type == "guardrail")
    if guardrail_count == 0:
        warnings.append("No guardrail nodes found. Add input/output guardrails before publishing.")

    loop_nodes = [n for n in graph.nodes if n.type == "loop"]
    for node in loop_nodes:
        max_iterations = node.config.get("max_iterations")
        if not isinstance(max_iterations, int) or max_iterations < 1:
            errors.append(f"Loop node '{node.name}' requires a positive integer max_iterations.")

    return ValidateResponse(valid=len(errors) == 0, errors=errors, warnings=warnings)


def _simulate(graph: GraphPayload, input_text: str) -> SimulateResponse:
    run_id = uuid4()
    trace: list[dict[str, Any]] = []

    for node in graph.nodes:
        trace.append(
            {
                "node_id": node.id,
                "node_type": node.type,
                "node_name": node.name,
                "status": "executed",
                "preview": f"Executed {node.type} node",
            }
        )

    output = {
        "final_text": f"Simulation completed for input: {input_text}",
        "nodes_executed": len(trace),
    }

    AgentBuilderStore.runs[run_id] = BuilderRun(
        id=run_id,
        version_id=uuid4(),
        status="completed",
        trace=trace,
        output=output,
    )

    return SimulateResponse(
        run_id=str(run_id),
        status="completed",
        trace=trace,
        output=output,
    )


def _generate_files(version: BuilderVersion) -> GenerateResponse:
    slug = version.graph.nodes[0].name.lower().replace(" ", "-") if version.graph.nodes else "agent"
    files = {
        f"backend/app/agents/generated/{slug}/agent.manifest.json": (
            '{\n'
            f'  "version_id": "{version.id}",\n'
            f'  "schema_version": "{version.schema_version}",\n'
            f'  "node_count": {len(version.graph.nodes)}\n'
            '}'
        ),
        f"backend/app/agents/generated/{slug}/workflow.graph.json": version.graph.model_dump_json(indent=2),
        f"backend/app/agents/generated/{slug}/runtime_adapter.py": (
            "from app.agents.personal_agent.runtime import PersonalAgentRuntime\n\n"
            "def load_generated_agent() -> dict:\n"
            f"    return {{'version_id': '{version.id}', 'status': 'loaded'}}\n"
        ),
    }

    artifact_hash = f"v{version.version_number}-{len(version.graph.nodes)}-{len(version.graph.edges)}"
    return GenerateResponse(artifact_hash=artifact_hash, files=files)


@router.post("/projects", response_model=BuilderProjectResponse)
def create_project(
    payload: BuilderProjectCreate,
    current_user_id: str = Depends(get_current_user_id),
):
    project = AgentBuilderStore.create_project(
        owner_id=UUID(current_user_id),
        name=payload.name,
        description=payload.description,
    )
    return _to_project_response(project)


@router.get("/projects", response_model=list[BuilderProjectResponse])
def list_projects(current_user_id: str = Depends(get_current_user_id)):
    projects = AgentBuilderStore.list_projects(owner_id=UUID(current_user_id))
    return [_to_project_response(project) for project in projects]


@router.get("/projects/{project_id}", response_model=BuilderProjectResponse)
def get_project(project_id: UUID, current_user_id: str = Depends(get_current_user_id)):
    project = AgentBuilderStore.get_project(owner_id=UUID(current_user_id), project_id=project_id)
    return _to_project_response(project)


@router.post("/projects/{project_id}/versions", response_model=BuilderVersionResponse)
def create_version(
    project_id: UUID,
    payload: BuilderVersionCreate,
    current_user_id: str = Depends(get_current_user_id),
):
    project = AgentBuilderStore.get_project(owner_id=UUID(current_user_id), project_id=project_id)
    version = AgentBuilderStore.create_version(project=project, payload=payload)
    return _to_version_response(version)


@router.post("/versions/{version_id}/validate", response_model=ValidateResponse)
def validate_version(version_id: UUID, current_user_id: str = Depends(get_current_user_id)):
    version = AgentBuilderStore.get_version(owner_id=UUID(current_user_id), version_id=version_id)
    return _validate_graph(version.graph)


@router.post("/versions/{version_id}/simulate", response_model=SimulateResponse)
def simulate_version(
    version_id: UUID,
    payload: SimulateRequest,
    current_user_id: str = Depends(get_current_user_id),
):
    version = AgentBuilderStore.get_version(owner_id=UUID(current_user_id), version_id=version_id)
    if not version.graph.nodes:
        raise HTTPException(status_code=400, detail={"error": "invalid_graph", "message": "Graph has no nodes"})
    return _simulate(version.graph, payload.input_text)


@router.post("/versions/{version_id}/generate", response_model=GenerateResponse)
def generate_version(version_id: UUID, current_user_id: str = Depends(get_current_user_id)):
    version = AgentBuilderStore.get_version(owner_id=UUID(current_user_id), version_id=version_id)
    validation = _validate_graph(version.graph)
    if not validation.valid:
        raise HTTPException(
            status_code=422,
            detail={"error": "validation_failed", "message": "Graph has blocking errors", "details": validation.errors},
        )
    version.status = "generated"
    return _generate_files(version)


@router.post("/versions/{version_id}/import", response_model=ImportResponse)
def import_version(version_id: UUID, current_user_id: str = Depends(get_current_user_id)):
    version = AgentBuilderStore.get_version(owner_id=UUID(current_user_id), version_id=version_id)
    slug = f"agent-{version.version_number}"
    version.status = "imported"
    return ImportResponse(
        imported=True,
        agent_slug=slug,
        runtime_registration={
            "registry": "personal_agent.generated",
            "entrypoint": f"backend/app/agents/generated/{slug}/runtime_adapter.py",
            "version_id": str(version.id),
        },
    )


@router.post("/versions/{version_id}/publish", response_model=PublishResponse)
def publish_version(version_id: UUID, current_user_id: str = Depends(get_current_user_id)):
    version = AgentBuilderStore.get_version(owner_id=UUID(current_user_id), version_id=version_id)
    validation = _validate_graph(version.graph)
    if not validation.valid:
        raise HTTPException(
            status_code=422,
            detail={"error": "validation_failed", "message": "Cannot publish invalid graph", "details": validation.errors},
        )
    version.status = "published"
    project = AgentBuilderStore.projects[version.project_id]
    project.status = "published"
    project.updated_at = datetime.now(timezone.utc)
    return PublishResponse(published=True, published_at=datetime.now(timezone.utc), version_id=str(version.id))
