"use client";

import { FormEvent, useMemo, useState } from "react";
import {
  BuilderGraph,
  BuilderNode,
  BuilderNodeType,
  BuilderVersion,
  createBuilderProject,
  createBuilderVersion,
  generateBuilderVersion,
  importBuilderVersion,
  publishBuilderVersion,
  simulateBuilderVersion,
  validateBuilderVersion,
} from "@/lib/api";

const NODE_TYPES: BuilderNodeType[] = [
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
];

function defaultGraph(): BuilderGraph {
  return {
    nodes: [
      { id: "start-1", type: "start", name: "Start", config: {} },
      {
        id: "guardrail-in",
        type: "guardrail",
        name: "Input Guardrail",
        config: { policy: "moderation_basic" },
      },
      {
        id: "classifier-1",
        type: "classify",
        name: "Domain Classifier",
        config: { labels: ["commerce", "personnel", "other"] },
      },
      { id: "agent-1", type: "agent", name: "Commerce Agent", config: {} },
      { id: "guardrail-out", type: "guardrail", name: "Output Guardrail", config: {} },
      { id: "end-1", type: "end", name: "End", config: {} },
    ],
    edges: [
      { source: "start-1", target: "guardrail-in" },
      { source: "guardrail-in", target: "classifier-1" },
      { source: "classifier-1", target: "agent-1", label: "commerce" },
      { source: "agent-1", target: "guardrail-out" },
      { source: "guardrail-out", target: "end-1" },
    ],
  };
}

export default function AgentBuilderPage() {
  const [projectName, setProjectName] = useState("Commerce Query Router");
  const [projectDescription, setProjectDescription] = useState(
    "Routes user query to a domain-specific Tarpspace agent",
  );
  const [graph, setGraph] = useState<BuilderGraph>(defaultGraph);
  const [projectId, setProjectId] = useState<string | null>(null);
  const [version, setVersion] = useState<BuilderVersion | null>(null);
  const [simulateInput, setSimulateInput] = useState("How many orders did we sell in 2025?");
  const [logs, setLogs] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const nodeCount = graph.nodes.length;
  const edgeCount = graph.edges.length;

  const selectedSummary = useMemo(
    () =>
      graph.nodes.map((n) => `${n.name} (${n.type})`).join(" → ") ||
      "No nodes yet",
    [graph.nodes],
  );

  const addLog = (message: string) => {
    setLogs((prev) => [`${new Date().toLocaleTimeString()} · ${message}`, ...prev]);
  };

  const addNode = (type: BuilderNodeType) => {
    const nextNode: BuilderNode = {
      id: `${type}-${graph.nodes.length + 1}`,
      type,
      name: `${type.replace("_", " ")} node`,
      config: type === "loop" ? { max_iterations: 3 } : {},
    };

    setGraph((prev) => ({
      ...prev,
      nodes: [...prev.nodes, nextNode],
    }));
    addLog(`Added node ${nextNode.id}`);
  };

  const linkLastTo = (targetNodeId: string) => {
    if (graph.nodes.length < 2) {
      return;
    }
    const source = graph.nodes[graph.nodes.length - 2];
    const target = graph.nodes.find((n) => n.id === targetNodeId);
    if (!target) {
      return;
    }
    setGraph((prev) => ({
      ...prev,
      edges: [...prev.edges, { source: source.id, target: target.id }],
    }));
    addLog(`Connected ${source.id} -> ${target.id}`);
  };

  const createProjectAndVersion = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const project = await createBuilderProject({
        name: projectName,
        description: projectDescription,
      });
      setProjectId(project.id);
      addLog(`Created project ${project.name}`);

      const createdVersion = await createBuilderVersion(project.id, graph, "Initial draft from UI");
      setVersion(createdVersion);
      addLog(`Created version v${createdVersion.version_number}`);
    } finally {
      setBusy(false);
    }
  };

  const runValidation = async () => {
    if (!version) {
      addLog("Create a version first");
      return;
    }
    setBusy(true);
    try {
      const result = await validateBuilderVersion(version.id);
      addLog(
        result.valid
          ? `Validation passed (${result.warnings.length} warning(s))`
          : `Validation failed: ${result.errors.join(" | ")}`,
      );
    } finally {
      setBusy(false);
    }
  };

  const runSimulation = async () => {
    if (!version) {
      addLog("Create a version first");
      return;
    }
    setBusy(true);
    try {
      const result = await simulateBuilderVersion(version.id, simulateInput);
      addLog(`Simulation completed; nodes executed: ${result.output.nodes_executed}`);
    } finally {
      setBusy(false);
    }
  };

  const runGenerate = async () => {
    if (!version) {
      addLog("Create a version first");
      return;
    }
    setBusy(true);
    try {
      const result = await generateBuilderVersion(version.id);
      addLog(`Generated artifact ${result.artifact_hash} (${Object.keys(result.files).length} files)`);
    } finally {
      setBusy(false);
    }
  };

  const runImport = async () => {
    if (!version) {
      addLog("Create a version first");
      return;
    }
    setBusy(true);
    try {
      const result = await importBuilderVersion(version.id);
      addLog(`Imported as ${result.agent_slug}`);
    } finally {
      setBusy(false);
    }
  };

  const runPublish = async () => {
    if (!version) {
      addLog("Create a version first");
      return;
    }
    setBusy(true);
    try {
      const result = await publishBuilderVersion(version.id);
      addLog(`Published at ${result.published_at}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <main className="mx-auto flex min-h-[calc(100vh-56px)] w-full max-w-7xl flex-col gap-6 px-6 py-8">
      <header className="rounded-xl border border-border-dark bg-[#111520] p-5">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-muted">Agent Builder</p>
        <h1 className="mt-2 text-2xl font-bold text-primary">Visual agent builder for Tarpspace</h1>
        <p className="mt-2 text-sm text-muted">
          Create workflows with tools and guardrails, validate, simulate, generate files, import into runtime,
          and publish.
        </p>
      </header>

      <section className="grid gap-5 lg:grid-cols-[280px_1fr_320px]">
        <aside className="rounded-xl border border-border-dark bg-[#111520] p-4">
          <h2 className="text-sm font-semibold text-primary">Node Palette</h2>
          <div className="mt-3 grid grid-cols-1 gap-2">
            {NODE_TYPES.map((type) => (
              <button
                key={type}
                className="rounded-md border border-border-dark px-3 py-2 text-left text-xs text-muted hover:border-accent-blue hover:text-primary"
                onClick={() => addNode(type)}
                type="button"
              >
                + {type}
              </button>
            ))}
          </div>

          <div className="mt-4 border-t border-border-dark pt-4">
            <label className="block text-xs text-muted">Quick Connect (last node -> target)</label>
            <select
              className="mt-1 w-full rounded-md border border-border-dark bg-[#0d1018] px-2 py-2 text-xs text-primary"
              onChange={(e) => linkLastTo(e.target.value)}
              defaultValue=""
            >
              <option value="" disabled>
                Select target
              </option>
              {graph.nodes.map((node) => (
                <option key={node.id} value={node.id}>
                  {node.id}
                </option>
              ))}
            </select>
          </div>
        </aside>

        <section className="rounded-xl border border-border-dark bg-[#111520] p-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-primary">Workflow Graph</h2>
            <span className="font-mono text-xs text-muted">
              nodes: {nodeCount} · edges: {edgeCount}
            </span>
          </div>

          <div className="mt-4 grid gap-3">
            {graph.nodes.map((node) => (
              <article key={node.id} className="rounded-lg border border-border-dark bg-[#0c1018] p-3">
                <div className="flex items-center justify-between">
                  <p className="text-sm font-medium text-primary">{node.name}</p>
                  <span className="rounded bg-[#1d2230] px-2 py-0.5 font-mono text-[10px] text-muted">{node.type}</span>
                </div>
                <p className="mt-1 font-mono text-[11px] text-muted">{node.id}</p>
              </article>
            ))}
          </div>

          <p className="mt-4 text-xs text-muted">Current flow: {selectedSummary}</p>
        </section>

        <aside className="rounded-xl border border-border-dark bg-[#111520] p-4">
          <h2 className="text-sm font-semibold text-primary">Build & Publish</h2>
          <form className="mt-3 space-y-2" onSubmit={createProjectAndVersion}>
            <input
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              className="w-full rounded-md border border-border-dark bg-[#0d1018] px-3 py-2 text-sm text-primary"
              placeholder="Project name"
            />
            <textarea
              value={projectDescription}
              onChange={(e) => setProjectDescription(e.target.value)}
              className="h-20 w-full rounded-md border border-border-dark bg-[#0d1018] px-3 py-2 text-sm text-primary"
              placeholder="Description"
            />
            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-md border border-accent-blue px-3 py-2 text-sm text-accent-blue disabled:opacity-60"
            >
              {busy ? "Working..." : "Save Draft Version"}
            </button>
          </form>

          <div className="mt-4 grid grid-cols-2 gap-2">
            <button type="button" onClick={runValidation} className="rounded border border-border-dark px-2 py-2 text-xs text-muted">
              Validate
            </button>
            <button type="button" onClick={runSimulation} className="rounded border border-border-dark px-2 py-2 text-xs text-muted">
              Simulate
            </button>
            <button type="button" onClick={runGenerate} className="rounded border border-border-dark px-2 py-2 text-xs text-muted">
              Generate
            </button>
            <button type="button" onClick={runImport} className="rounded border border-border-dark px-2 py-2 text-xs text-muted">
              Import
            </button>
          </div>

          <button
            type="button"
            onClick={runPublish}
            className="mt-2 w-full rounded border border-emerald-500 px-2 py-2 text-xs text-emerald-400"
          >
            Publish
          </button>

          <div className="mt-4 border-t border-border-dark pt-3">
            <label className="text-xs text-muted">Simulation input</label>
            <textarea
              value={simulateInput}
              onChange={(e) => setSimulateInput(e.target.value)}
              className="mt-1 h-16 w-full rounded-md border border-border-dark bg-[#0d1018] px-2 py-2 text-xs text-primary"
            />
          </div>

          <div className="mt-4 border-t border-border-dark pt-3">
            <p className="text-xs text-muted">Project ID</p>
            <p className="font-mono text-[11px] text-primary">{projectId ?? "—"}</p>
            <p className="mt-2 text-xs text-muted">Version</p>
            <p className="font-mono text-[11px] text-primary">
              {version ? `v${version.version_number} (${version.status})` : "—"}
            </p>
          </div>
        </aside>
      </section>

      <section className="rounded-xl border border-border-dark bg-[#111520] p-4">
        <h2 className="text-sm font-semibold text-primary">Execution / Build Log</h2>
        <div className="mt-3 max-h-64 space-y-1 overflow-auto font-mono text-xs text-muted">
          {logs.length === 0 && <p>No actions yet.</p>}
          {logs.map((line) => (
            <p key={line}>{line}</p>
          ))}
        </div>
      </section>
    </main>
  );
}
