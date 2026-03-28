import axios from "axios";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const DEV_USER_ID =
  process.env.NEXT_PUBLIC_DEV_USER_ID ?? "00000000-0000-0000-0000-000000000001";

export const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    "Content-Type": "application/json",
    "X-Dev-User-Id": DEV_USER_ID,
  },
});

// ---------------------------------------------------------------------------
// Shared
// ---------------------------------------------------------------------------

export type AgentMessage = {
  id: string;
  role: string;
  content: string;
  completeness_after: number;
  created_at: string;
};

// ---------------------------------------------------------------------------
// Personal Agent
// ---------------------------------------------------------------------------

export type Persona = {
  name?: string;
  home_city?: string;
  communication_style?: string;
  general_interests?: string[];
  deal_sensitivity?: string;
  [key: string]: unknown;
};

export type PersonalAgentSession = {
  conversation: { id: string; status: string; created_at: string };
  agent_message: AgentMessage;
  persona: Persona;
};

export type PersonalAgentTurnResponse = {
  conversation: { id: string; status: string };
  user_message: AgentMessage;
  agent_message: AgentMessage;
  persona_delta: Persona;
  persona: Persona;
  completeness_score: number;
  gaps_remaining: string[];
  next_gap: string | null;
  elicitation_complete: boolean;
};

export async function createPersonalAgentSession(): Promise<PersonalAgentSession> {
  const { data } = await apiClient.post<PersonalAgentSession>(
    "/api/v1/personal-agent/sessions",
  );
  return data;
}

export async function sendPersonalAgentMessage(
  conversationId: string,
  content: string,
): Promise<PersonalAgentTurnResponse> {
  const { data } = await apiClient.post<PersonalAgentTurnResponse>(
    `/api/v1/personal-agent/sessions/${conversationId}/messages`,
    { content },
  );
  return data;
}

export async function listPersonalMemories() {
  const { data } = await apiClient.get("/api/v1/personal-agent/memories");
  return data;
}

// ---------------------------------------------------------------------------
// Mandate Agent
// ---------------------------------------------------------------------------

/** Flat mandate state returned from derive_mandate_state on the backend. */
export type FlatMandateState = {
  intent_type?: string;
  vertical?: string;
  category?: string;
  budget?: { min?: number; max?: number };
  location?: string;
  condition?: string;
  timing?: string;
  style_preferences?: string[];
  dealbreakers?: string[];
  autonomy_level?: string;
};

/** Full ORM mandate returned from session create / GET mandate endpoints. */
export type MandateState = {
  id: string;
  owner_id: string;
  intent_type: string | null;
  vertical: string | null;
  category: string | null;
  hard_constraints: Array<{ field: string; value: string }>;
  negotiation_range: Array<{ dimension: string; min?: number; max?: number }>;
  soft_preferences: Array<{ field: string; value: string }>;
  dealbreakers: string[];
  autonomy_level: string;
  completeness_score: number;
  is_active: boolean;
  mandate_state: FlatMandateState;
};

export type MandateAgentSession = {
  conversation: { id: string; status: string; mandate_id: string | null };
  mandate: MandateState;
  agent_message: AgentMessage;
};

export type MandateAgentTurnResponse = {
  conversation: { id: string; status: string };
  user_message: AgentMessage;
  agent_message: AgentMessage;
  mandate_delta: Partial<FlatMandateState> & Record<string, unknown>;
  mandate_state: FlatMandateState;
  completeness_score: number;
  gaps_remaining: string[];
  next_gap: string | null;
  mandate_complete: boolean;
};

export async function createMandateAgentSession(): Promise<MandateAgentSession> {
  const { data } = await apiClient.post<MandateAgentSession>(
    "/api/v1/mandate-agent/sessions",
  );
  return data;
}

export async function sendMandateAgentMessage(
  conversationId: string,
  content: string,
): Promise<MandateAgentTurnResponse> {
  const { data } = await apiClient.post<MandateAgentTurnResponse>(
    `/api/v1/mandate-agent/sessions/${conversationId}/messages`,
    { content },
  );
  return data;
}

export async function getMandateAgentMandate(
  conversationId: string,
): Promise<MandateState> {
  const { data } = await apiClient.get<MandateState>(
    `/api/v1/mandate-agent/sessions/${conversationId}/mandate`,
  );
  return data;
}

// ---------------------------------------------------------------------------
// Agent Builder
// ---------------------------------------------------------------------------

export type BuilderNodeType =
  | "start"
  | "end"
  | "agent"
  | "classify"
  | "if_else"
  | "tool"
  | "guardrail"
  | "transform"
  | "set_state"
  | "user_approval"
  | "loop";

export type BuilderNode = {
  id: string;
  type: BuilderNodeType;
  name: string;
  config: Record<string, unknown>;
};

export type BuilderEdge = {
  source: string;
  target: string;
  label?: string;
  condition?: string;
};

export type BuilderGraph = {
  nodes: BuilderNode[];
  edges: BuilderEdge[];
};

export type BuilderProject = {
  id: string;
  name: string;
  description?: string | null;
  status: string;
  owner_id: string;
  created_at: string;
  updated_at: string;
};

export type BuilderVersion = {
  id: string;
  project_id: string;
  version_number: number;
  status: string;
  notes?: string | null;
  schema_version: string;
  created_at: string;
  graph: BuilderGraph;
};

export async function createBuilderProject(payload: {
  name: string;
  description?: string;
}): Promise<BuilderProject> {
  const { data } = await apiClient.post<BuilderProject>(
    "/api/v1/agent-builder/projects",
    payload,
  );
  return data;
}

export async function listBuilderProjects(): Promise<BuilderProject[]> {
  const { data } = await apiClient.get<BuilderProject[]>(
    "/api/v1/agent-builder/projects",
  );
  return data;
}

export async function createBuilderVersion(
  projectId: string,
  graph: BuilderGraph,
  notes?: string,
): Promise<BuilderVersion> {
  const { data } = await apiClient.post<BuilderVersion>(
    `/api/v1/agent-builder/projects/${projectId}/versions`,
    { graph, notes },
  );
  return data;
}

export async function validateBuilderVersion(versionId: string) {
  const { data } = await apiClient.post(
    `/api/v1/agent-builder/versions/${versionId}/validate`,
  );
  return data;
}

export async function simulateBuilderVersion(versionId: string, inputText: string) {
  const { data } = await apiClient.post(
    `/api/v1/agent-builder/versions/${versionId}/simulate`,
    { input_text: inputText },
  );
  return data;
}

export async function generateBuilderVersion(versionId: string) {
  const { data } = await apiClient.post(
    `/api/v1/agent-builder/versions/${versionId}/generate`,
  );
  return data;
}

export async function importBuilderVersion(versionId: string) {
  const { data } = await apiClient.post(
    `/api/v1/agent-builder/versions/${versionId}/import`,
  );
  return data;
}

export async function publishBuilderVersion(versionId: string) {
  const { data } = await apiClient.post(
    `/api/v1/agent-builder/versions/${versionId}/publish`,
  );
  return data;
}
