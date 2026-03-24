"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  sendHeartbeat,
  analyzeText,
  uploadFile,
  healthCheck,
} from "@/lib/api";

interface LogEntry {
  id: number;
  ts: string;
  msg: string;
  kind: "info" | "success" | "error";
}

let logId = 0;

export default function Home() {
  const [connected, setConnected] = useState<boolean | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const logRef = useRef<HTMLDivElement>(null);

  const addLog = useCallback((msg: string, kind: LogEntry["kind"] = "info") => {
    setLogs((prev) => [
      ...prev.slice(-99),
      { id: ++logId, ts: new Date().toLocaleTimeString(), msg, kind },
    ]);
  }, []);

  useEffect(() => {
    healthCheck().then(setConnected);
    const interval = setInterval(() => healthCheck().then(setConnected), 10_000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight, behavior: "smooth" });
  }, [logs]);

  return (
    <div className="min-h-screen flex flex-col">
      <Header connected={connected} />
      <main className="flex-1 max-w-7xl w-full mx-auto px-6 py-8 grid gap-6 lg:grid-cols-3">
        <HeartbeatCard addLog={addLog} />
        <TextAnalysisCard addLog={addLog} />
        <FileUploadCard addLog={addLog} />
      </main>
      <ActivityLog logs={logs} logRef={logRef} />
    </div>
  );
}

/* ── Header ────────────────────────────────────────────────────────────── */

function Header({ connected }: { connected: boolean | null }) {
  return (
    <header className="border-b border-[var(--border)] px-6 py-4 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-8 h-8 rounded-lg bg-[var(--accent)] flex items-center justify-center font-bold text-white text-sm">
          ES
        </div>
        <h1 className="text-lg font-semibold tracking-tight">EdgeScale</h1>
        <span className="text-xs text-[var(--text-dim)] ml-2">Event Processor Dashboard</span>
      </div>
      <div className="flex items-center gap-2 text-sm">
        <span
          className={`w-2 h-2 rounded-full ${
            connected === null
              ? "bg-[var(--warning)]"
              : connected
              ? "bg-[var(--success)]"
              : "bg-[var(--error)]"
          }`}
        />
        <span className="text-[var(--text-dim)]">
          {connected === null ? "Checking..." : connected ? "Connected" : "Disconnected"}
        </span>
      </div>
    </header>
  );
}

/* ── Heartbeat ─────────────────────────────────────────────────────────── */

function HeartbeatCard({ addLog }: { addLog: (m: string, k?: LogEntry["kind"]) => void }) {
  const [agentId, setAgentId] = useState("agent-001");
  const [loading, setLoading] = useState(false);
  const [last, setLast] = useState<string | null>(null);

  const send = async () => {
    setLoading(true);
    try {
      const res = await sendHeartbeat(agentId);
      setLast(`${res.latency_ms}ms`);
      addLog(`Heartbeat from ${agentId} — ${res.latency_ms}ms`, "success");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      addLog(`Heartbeat failed: ${msg}`, "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="Heartbeat" subtitle="Fire-and-forget">
      <label className="block text-xs text-[var(--text-dim)] mb-1">Agent ID</label>
      <input
        className="w-full bg-[var(--bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-[var(--accent)] transition-colors"
        value={agentId}
        onChange={(e) => setAgentId(e.target.value)}
      />
      <button onClick={send} disabled={loading} className="btn mt-3 w-full">
        {loading ? "Sending..." : "Send Heartbeat"}
      </button>
      {last && <Stat label="Latency" value={last} />}
    </Card>
  );
}

/* ── Text Analysis ─────────────────────────────────────────────────────── */

function TextAnalysisCard({ addLog }: { addLog: (m: string, k?: LogEntry["kind"]) => void }) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ wc: number; ms: number } | null>(null);

  const analyze = async () => {
    if (!text.trim()) return;
    setLoading(true);
    try {
      const res = await analyzeText(text);
      setResult({ wc: res.word_count, ms: res.latency_ms });
      addLog(`Text analysis: ${res.word_count} words — ${res.latency_ms}ms`, "success");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      addLog(`Text analysis failed: ${msg}`, "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="Text Analysis" subtitle="Request-Response over Broker">
      <label className="block text-xs text-[var(--text-dim)] mb-1">Text</label>
      <textarea
        className="w-full bg-[var(--bg)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm h-24 resize-none focus:outline-none focus:border-[var(--accent)] transition-colors"
        placeholder="Paste or type text to analyze..."
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <button onClick={analyze} disabled={loading || !text.trim()} className="btn mt-3 w-full">
        {loading ? "Analyzing..." : "Analyze Text"}
      </button>
      {result && (
        <div className="flex gap-4 mt-3">
          <Stat label="Word Count" value={String(result.wc)} />
          <Stat label="Latency" value={`${result.ms}ms`} />
        </div>
      )}
    </Card>
  );
}

/* ── File Upload ───────────────────────────────────────────────────────── */

function FileUploadCard({ addLog }: { addLog: (m: string, k?: LogEntry["kind"]) => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ wc: number; ms: number; name: string } | null>(null);

  const upload = async () => {
    if (!file) return;
    setLoading(true);
    try {
      const res = await uploadFile(file);
      setResult({ wc: res.word_count, ms: res.latency_ms, name: res.filename });
      addLog(
        `File "${res.filename}": ${res.word_count} words — ${res.latency_ms}ms`,
        "success",
      );
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Unknown error";
      addLog(`File upload failed: ${msg}`, "error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="File Upload" subtitle="Streaming Analysis">
      <label className="block text-xs text-[var(--text-dim)] mb-1">File (1-10 MB text)</label>
      <div className="relative">
        <input
          type="file"
          accept=".txt,.csv,.log,.md,.json,.xml"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="w-full text-sm file:mr-3 file:py-2 file:px-4 file:rounded-lg file:border-0 file:bg-[var(--surface-hover)] file:text-[var(--text)] file:cursor-pointer file:text-sm hover:file:bg-[var(--border)] transition-colors"
        />
      </div>
      {file && (
        <p className="text-xs text-[var(--text-dim)] mt-1">
          {file.name} — {(file.size / 1024).toFixed(1)} KB
        </p>
      )}
      <button onClick={upload} disabled={loading || !file} className="btn mt-3 w-full">
        {loading ? "Uploading..." : "Upload & Analyze"}
      </button>
      {result && (
        <div className="flex gap-4 mt-3">
          <Stat label="Word Count" value={String(result.wc)} />
          <Stat label="Latency" value={`${result.ms}ms`} />
        </div>
      )}
    </Card>
  );
}

/* ── Activity Log ──────────────────────────────────────────────────────── */

function ActivityLog({
  logs,
  logRef,
}: {
  logs: LogEntry[];
  logRef: React.RefObject<HTMLDivElement>;
}) {
  const kindColor = { info: "text-[var(--text-dim)]", success: "text-[var(--success)]", error: "text-[var(--error)]" };

  return (
    <section className="border-t border-[var(--border)] bg-[var(--surface)]">
      <div className="max-w-7xl mx-auto px-6 py-3">
        <h2 className="text-xs font-semibold text-[var(--text-dim)] uppercase tracking-wider mb-2">
          Activity Log
        </h2>
        <div ref={logRef} className="h-32 overflow-y-auto font-mono text-xs space-y-0.5">
          {logs.length === 0 && (
            <p className="text-[var(--text-dim)] italic">No activity yet. Try sending a heartbeat.</p>
          )}
          {logs.map((l) => (
            <div key={l.id} className="flex gap-3">
              <span className="text-[var(--text-dim)] shrink-0">{l.ts}</span>
              <span className={kindColor[l.kind]}>{l.msg}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* ── Shared Components ─────────────────────────────────────────────────── */

function Card({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-xl p-5 flex flex-col">
      <h2 className="font-semibold text-base">{title}</h2>
      <p className="text-xs text-[var(--text-dim)] mb-4">{subtitle}</p>
      {children}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="mt-2 bg-[var(--bg)] rounded-lg px-3 py-2 flex-1">
      <p className="text-[10px] text-[var(--text-dim)] uppercase tracking-wider">{label}</p>
      <p className="text-lg font-semibold font-mono">{value}</p>
    </div>
  );
}
