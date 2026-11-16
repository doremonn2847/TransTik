"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { CopyButton, ErrorNote, PlatformMark } from "@/components/ui";
import { api, clock, compact, day, FORMATS, percent, type Segment, type Transcript } from "@/lib/api";

export default function TranscriptPage() {
  const { id } = useParams<{ id: string }>();
  const tid = Number(id);
  const router = useRouter();
  const qc = useQueryClient();
  const [timestamps, setTimestamps] = useState(true);
  const [editing, setEditing] = useState<number | null>(null);
  const [flash, setFlash] = useState<number | null>(null);

  const query = useQuery({ queryKey: ["transcript", tid], queryFn: () => api.transcript(tid) });
  const t = query.data;

  const refresh = (data: Transcript) => {
    qc.setQueryData(["transcript", tid], data);
    qc.invalidateQueries({ queryKey: ["library"] });
  };
  const patch = useMutation({ mutationFn: (body: Record<string, unknown>) => api.patch(tid, body), onSuccess: refresh });
  const remove = useMutation({
    mutationFn: () => api.remove([tid]),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["library"] }); router.push("/library"); },
  });
  const redo = useMutation({ mutationFn: () => api.retranscribe(tid), onSuccess: () => router.push("/") });

  const plain = t ? (timestamps ? t.segments.map((s) => `[${clock(s.start)}] ${s.text}`).join("\n") : t.text) : "";

  // "c" copies the transcript when not typing.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = document.activeElement;
      if (e.key === "c" && !e.metaKey && !e.ctrlKey && plain &&
          !(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement)) {
        navigator.clipboard.writeText(plain);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [plain]);

  if (query.isPending) return <p className="text-muted">Loading…</p>;
  if (query.isError || !t) {
    return (
      <div className="space-y-3">
        <ErrorNote error={query.error} />
        <Link href="/library" className="btn">Back to library</Link>
      </div>
    );
  }

  const saveSegment = (index: number, text: string) => {
    setEditing(null);
    if (text.trim() === t.segments[index].text) return;
    const segments: Segment[] = t.segments.map((s, i) => (i === index ? { ...s, text: text.trim() } : s)).filter((s) => s.text);
    qc.setQueryData(["transcript", tid], { ...t, segments, edited: true }); // show it now; the server reply replaces it
    patch.mutate({ segments }, {
      onSuccess: () => { setFlash(index); setTimeout(() => setFlash(null), 900); },
      onError: () => qc.setQueryData(["transcript", tid], t),
    });
  };

  const words = t.text.split(/\s+/).filter(Boolean).length;
  const wpm = t.duration_s ? Math.round(words / (t.duration_s / 60)) : null;
  const askPrompt = `Use TransTik: read transcript ${t.id} ("${t.title ?? "untitled"}") and `;

  return (
    <div className="grid grid-cols-[minmax(0,1fr)] gap-10 lg:grid-cols-[minmax(0,1fr)_300px]">
      <article className="min-w-0">
        <Link href="/library" className="label hover:!text-ink">← Library</Link>
        <h1 className="mt-3 font-serif text-[30px] leading-[1.15] tracking-tight text-balance">{t.title || "Untitled video"}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[13px] text-muted">
          <PlatformMark platform={t.platform} showLabel />
          {t.author && <span>@{t.author.replace(/^@/, "")}</span>}
          {t.language && <span className="num uppercase">{t.language}</span>}
          <span>{t.source === "asr" ? "Speech-to-text" : "Platform captions"}</span>
          <span className="num">{words} words</span>
        </div>

        <div className="mt-6 flex flex-wrap items-center gap-2 border-y border-line py-2">
          <CopyButton text={plain} label="Copy text" className="btn btn-primary" />
          <label className="ml-1 inline-flex cursor-pointer items-center gap-1.5 text-[13px] text-muted">
            <input type="checkbox" checked={timestamps} onChange={(e) => setTimestamps(e.target.checked)} className="accent-[var(--accent)]" />
            Timestamps
          </label>
          <span className="ml-auto text-[12px] text-muted">
            {t.edited ? (
              <button className="underline hover:text-ink" onClick={() => confirm("Discard your edits and restore the original transcript?") && patch.mutate({ restore_original: true })}>
                Edited · restore original
              </button>
            ) : "Click a line to correct it"}
          </span>
        </div>

        <ErrorNote error={patch.error} />

        <div className="mt-5 max-w-[68ch]">
          {t.segments.map((seg, i) => (
            <div key={`${i}-${seg.start}`} className={`group grid grid-cols-[52px_minmax(0,1fr)] gap-3 rounded-[3px] ${flash === i ? "saved" : ""}`}>
              <a
                href={jumpUrl(t, seg.start)} target="_blank" rel="noreferrer"
                title="Open the video at this moment"
                className={`num pt-[5px] text-right text-[11.5px] text-muted hover:text-accent ${timestamps ? "" : "invisible"}`}
              >
                {clock(seg.start)}
              </a>
              {editing === i ? (
                <EditLine initial={seg.text} onSave={(v) => saveSegment(i, v)} onCancel={() => setEditing(null)} />
              ) : (
                <p
                  role="button" tabIndex={0}
                  onClick={() => setEditing(i)}
                  onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); setEditing(i); } }}
                  className="cursor-text rounded-[3px] px-1.5 py-[3px] font-serif text-[17.5px] leading-[1.6] hover:bg-surface"
                >
                  {seg.text}
                </p>
              )}
            </div>
          ))}
        </div>
      </article>

      <aside className="min-w-0 space-y-7 lg:sticky lg:top-6 lg:self-start">
        {t.thumbnail && (
          <a href={t.url} target="_blank" rel="noreferrer" className="block overflow-hidden border border-line bg-sunk">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={t.thumbnail} alt="Video thumbnail" className="max-h-72 w-full object-cover" />
          </a>
        )}
        <a href={t.url} target="_blank" rel="noreferrer" className="btn w-full">Open original ↗</a>

        <section>
          <h2 className="label border-b border-line pb-1.5">Numbers</h2>
          <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-2.5">
            <Stat label="Views" value={compact(t.stats.view_count)} />
            <Stat label="Likes" value={compact(t.stats.like_count)} />
            <Stat label="Comments" value={compact(t.stats.comment_count)} />
            <Stat label="Shares" value={compact(t.stats.repost_count)} />
            <Stat label="Likes / view" value={percent(t.stats.likes_per_view)} />
            <Stat label="Length" value={t.duration_s ? clock(t.duration_s) : "–"} />
            <Stat label="Words / min" value={wpm ? String(wpm) : "–"} />
            <Stat label="Added" value={day(t.created_at)} />
          </dl>
          <p className="mt-2 text-[11.5px] text-muted">As of when it was transcribed.</p>
        </section>

        <section>
          <h2 className="label border-b border-line pb-1.5">Export</h2>
          <div className="mt-2 grid grid-cols-3 gap-1.5">
            {FORMATS.map((f) => (
              <a key={f} href={api.exportUrl(t.id, f, timestamps)} className="btn !px-0 font-mono" download>.{f}</a>
            ))}
          </div>
        </section>

        <Organize t={t} onSave={(body) => patch.mutate(body)} />

        <section>
          <h2 className="label border-b border-line pb-1.5">Use in Claude or ChatGPT</h2>
          <p className="mt-2 text-[12.5px] leading-relaxed text-muted">
            With the MCP server connected, start a chat with this and add what you want: hooks, a remix on your topic, or why it worked.
          </p>
          <div className="mt-2 flex gap-1.5">
            <code className="min-w-0 flex-1 truncate border border-line bg-sunk px-2 py-1.5 font-mono text-[11.5px]" title={askPrompt}>{askPrompt}</code>
            <CopyButton text={askPrompt} />
          </div>
        </section>

        <section className="space-y-2 border-t border-line pt-4">
          {t.source === "platform_captions" && (
            <button className="btn w-full" disabled={redo.isPending} onClick={() => confirm("Transcribe the audio with speech-to-text? This replaces the current transcript and any edits.") && redo.mutate()}>
              Re-transcribe from audio
            </button>
          )}
          <button className="btn btn-quiet w-full hover:!text-bad" onClick={() => confirm("Delete this transcript? This cannot be undone.") && remove.mutate()}>
            Delete transcript
          </button>
          <ErrorNote error={redo.error ?? remove.error} />
        </section>
      </aside>
    </div>
  );
}

function jumpUrl(t: Transcript, seconds: number): string {
  const s = Math.floor(seconds);
  return t.platform === "youtube" ? `${t.url}&t=${s}s` : t.url;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-[11.5px] text-muted">{label}</dt>
      <dd className="num text-[15px]">{value}</dd>
    </div>
  );
}

function EditLine({ initial, onSave, onCancel }: { initial: string; onSave: (v: string) => void; onCancel: () => void }) {
  const [value, setValue] = useState(initial);
  return (
    <textarea
      autoFocus
      value={value}
      onChange={(e) => setValue(e.target.value)}
      onBlur={() => onSave(value)}
      onKeyDown={(e) => {
        if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSave(value); }
        if (e.key === "Escape") onCancel();
      }}
      onFocus={(e) => e.currentTarget.setSelectionRange(value.length, value.length)}
      rows={Math.max(1, Math.ceil(value.length / 70))}
      aria-label="Edit line"
      className="w-full resize-none rounded-[3px] border border-accent bg-surface px-1.5 py-[2px] font-serif text-[17.5px] leading-[1.6] outline-none"
    />
  );
}

function Organize({ t, onSave }: { t: Transcript; onSave: (body: Record<string, unknown>) => void }) {
  const qc = useQueryClient();
  const folders = useQuery({ queryKey: ["folders"], queryFn: api.folders });
  const [tags, setTags] = useState(t.tags.map((x) => `#${x}`).join(" "));
  useEffect(() => setTags(t.tags.map((x) => `#${x}`).join(" ")), [t.tags]);

  const chooseFolder = async (value: string) => {
    if (value === "__new") {
      const name = prompt("New folder name")?.trim();
      if (!name) return;
      const f = await api.createFolder(name);
      qc.invalidateQueries({ queryKey: ["folders"] });
      onSave({ folder_id: f.id });
    } else if (value === "") {
      onSave({ clear_folder: true });
    } else {
      onSave({ folder_id: Number(value) });
    }
    qc.invalidateQueries({ queryKey: ["folders"] });
  };

  const saveTags = () => {
    const list = tags.split(/[\s,]+/).map((x) => x.replace(/^#/, "").trim().toLowerCase()).filter(Boolean);
    if (list.join(" ") !== t.tags.join(" ")) onSave({ tags: list });
  };

  return (
    <section>
      <h2 className="label border-b border-line pb-1.5">Organize</h2>
      <label className="mt-2 block text-[11.5px] text-muted" htmlFor="folder">Folder</label>
      <select id="folder" className="field mt-1 w-full" value={t.folder_id ?? ""} onChange={(e) => chooseFolder(e.target.value)}>
        <option value="">No folder</option>
        {(folders.data ?? []).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        <option value="__new">+ New folder…</option>
      </select>
      <label className="mt-3 block text-[11.5px] text-muted" htmlFor="tags">Tags</label>
      <input
        id="tags" className="field mt-1 w-full font-mono" value={tags} placeholder="#hooks #fitness"
        onChange={(e) => setTags(e.target.value)} onBlur={saveTags}
        onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); saveTags(); } }}
      />
    </section>
  );
}
