const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8080";

export interface HeartbeatResult {
  status: string;
  agent_id: string;
  latency_ms: number;
}

export interface TextResult {
  request_id: string;
  word_count: number;
  latency_ms: number;
}

export interface FileResult {
  file_id: string;
  word_count: number;
  filename: string;
  latency_ms: number;
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json();
}

export function sendHeartbeat(agentId: string) {
  return request<HeartbeatResult>("/api/heartbeat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent_id: agentId }),
  });
}

export function analyzeText(text: string) {
  return request<TextResult>("/api/analyze-text", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

export function uploadFile(file: File) {
  const form = new FormData();
  form.append("file", file);
  return request<FileResult>("/api/upload-file", {
    method: "POST",
    body: form,
  });
}

export async function healthCheck(): Promise<boolean> {
  try {
    await request<{ status: string }>("/api/health", { method: "GET" });
    return true;
  } catch {
    return false;
  }
}
