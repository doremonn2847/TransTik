// Typed client for the FastAPI service. All calls go through Next's /api rewrite.

export type Platform = "tiktok" | "instagram" | "youtube";
export type ExportFormat = "txt" | "srt" | "vtt" | "json" | "csv" | "md";
export const FORMATS: ExportFormat[] = ["txt", "srt", "vtt", "md", "csv", "json"];

export interface Segment { start: number; end: number; text: string }

export interface Item {
  id: number; platform: Platform; url: string; title: string | null; author: string | null;
  duration_s: number | null; language: string | null; source: "platform_captions" | "asr";
  model: string | null; edited: boolean; chars: number; folder_id: number | null; folder: string | null;
  tags: string[]; thumbnail: string | null; stats: Record<string, number>;
  created_at: string; updated_at: string; snippet?: string | null;
}

export interface Transcript extends Item { description: string | null; segments: Segment[]; text: string }

export interface Job {
  id: number; batch_id: string | null; input_url: string;
  status: "queued" | "resolving" | "fetching" | "transcribing" | "done" | "failed";
  error_code: string | null; error_detail: string | null; hint: string | null;
  transcript_id: number | null; title: string | null; author: string | null; platform: Platform | null;
  created_at: string; finished_at: string | null;
}

export interface Folder { id: number; name: string; count: number }
export interface Tag { tag: string; count: number }

export interface Status {
  asr: { configured: boolean; base_url: string; model: string };
  ytdlp_version: string; ffmpeg: boolean; js_runtime: boolean; cookies: boolean;
  mcp: { local_url: string; tunnel_url: string | null };
  library_count: number; in_docker: boolean;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    ...init,
    headers: init?.body ? { "Content-Type": "application/json", ...init.headers } : init?.headers,
  });
  if (!res.ok) {
    const detail = await res.json().then((d) => d.detail).catch(() => null);
    throw new Error(typeof detail === "string" ? detail : `Request failed (${res.status})`);
  }
  return res.json();
}

const post = <T,>(path: string, body?: unknown) =>
  req<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  submit: (text: string) => post<{ batch_id: string | null; job_ids: number[]; notes: string[] }>("/jobs", { text }),
  jobs: () => req<Job[]>("/jobs?limit=100"),
  job: (id: number) => req<Job>(`/jobs/${id}`),
  retry: (id: number) => post<Job>(`/jobs/${id}/retry`),
  clearFinished: () => req<{ deleted: number }>("/jobs/finished", { method: "DELETE" }),

  library: (params: Record<string, string | number | undefined>) => {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== "") qs.set(k, String(v));
    return req<{ total: number; items: Item[] }>(`/library?${qs}`);
  },
  transcript: (id: number) => req<Transcript>(`/transcripts/${id}`),
  patch: (id: number, body: Record<string, unknown>) =>
    req<Transcript>(`/transcripts/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  remove: (ids: number[]) => post<{ deleted: number }>("/library/delete", { ids }),
  retranscribe: (id: number) => post<{ job_id: number }>(`/transcripts/${id}/retranscribe`),

  folders: () => req<Folder[]>("/folders"),
  createFolder: (name: string) => post<Folder>("/folders", { name }),
  tags: () => req<Tag[]>("/tags"),

  status: () => req<Status>("/settings/status"),
  asrTest: () => post<{ ok: boolean; message: string }>("/settings/asr-test"),
  ytdlpUpdate: () => post<{ ok: boolean; message: string }>("/settings/ytdlp-update"),

  exportUrl: (id: number, format: ExportFormat, timestamps = false) =>
    `/api/transcripts/${id}/export?format=${format}&timestamps=${timestamps}`,

  async downloadZip(ids: number[], format: ExportFormat) {
    const res = await fetch("/api/export/zip", {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids, format }),
    });
    if (!res.ok) throw new Error("Export failed");
    const url = URL.createObjectURL(await res.blob());
    const a = Object.assign(document.createElement("a"), { href: url, download: `transcripts-${ids.length}.zip` });
    a.click();
    URL.revokeObjectURL(url);
  },
};

export const ACTIVE = ["queued", "resolving", "fetching", "transcribing"];

export function clock(seconds: number): string {
  const t = Math.floor(seconds);
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = t % 60;
  const pad = (n: number) => String(n).padStart(2, "0");
  return h ? `${h}:${pad(m)}:${pad(s)}` : `${pad(m)}:${pad(s)}`;
}

export function compact(n: number | undefined | null): string {
  if (n === undefined || n === null) return "–";
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(n);
}

export function percent(n: number | undefined): string {
  return n === undefined ? "–" : `${(n * 100).toFixed(n < 0.01 ? 2 : 1)}%`;
}

export function day(iso: string): string {
  return new Date(iso.replace(" ", "T") + "Z").toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export function countLinks(text: string): number {
  return (text.match(/(?:https?:\/\/|www\.|\b(?:vm\.|vt\.|m\.)?(?:tiktok|instagram|youtube)\.com\/|youtu\.be\/)\S+/gi) ?? []).length;
}
