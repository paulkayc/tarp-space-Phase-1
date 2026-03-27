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

export type PersonalAgentSession = {
  conversation: { id: string; status: string };
  agent_message: { content: string };
};

export async function createPersonalAgentSession() {
  const { data } = await apiClient.post<PersonalAgentSession>(
    "/api/v1/personal-agent/sessions",
  );
  return data;
}

export async function sendPersonalAgentMessage(
  conversationId: string,
  content: string,
) {
  const { data } = await apiClient.post(
    `/api/v1/personal-agent/sessions/${conversationId}/messages`,
    { content },
  );
  return data;
}

export async function listPersonalMemories() {
  const { data } = await apiClient.get("/api/v1/personal-agent/memories");
  return data;
}
