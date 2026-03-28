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
