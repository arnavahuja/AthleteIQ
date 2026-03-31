const BASE_URL = import.meta.env.VITE_API_URL || "/api";

export async function sendQuery(query, conversationHistory = null) {
  const body = { query };
  if (conversationHistory && conversationHistory.length > 0) {
    body.conversation_history = conversationHistory;
  }
  const response = await fetch(`${BASE_URL}/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`Query failed: ${response.statusText}`);
  }
  return response.json();
}

export async function sendVoice(audioBlob) {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");
  const response = await fetch(`${BASE_URL}/voice`, {
    method: "POST",
    body: formData,
  });
  if (!response.ok) {
    throw new Error(`Voice query failed: ${response.statusText}`);
  }
  return response.json();
}

export async function getHealth() {
  const response = await fetch(`${BASE_URL}/health`);
  return response.json();
}

export async function getSchema() {
  const response = await fetch(`${BASE_URL}/schema`);
  return response.json();
}
