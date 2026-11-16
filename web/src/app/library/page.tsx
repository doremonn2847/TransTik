"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Empty, ErrorNote, PlatformMark } from "@/components/ui";
import { api, clock, compact, day, FORMATS, type ExportFormat, type Item } from "@/lib/api";

const PAGE = 50;

function useDebounced<T>(value: T, ms = 250): T {
  const [v, setV] = useState(value);
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return v;
}

export default function Library() {
  const qc = useQueryClient();
  const search = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  const [platform, setPlatform] = useState("");
  const [source, setSource] = useState("");
  const [folderId, setFolderId] = useState("");
  const [tag, setTag] = useState("");
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [format, setFormat] = useState<ExportFormat>("txt");
  const dq = useDebounced(q);

  useEffect(() => { setPage(0); setSelected(new Set()); }, [dq, platform, source, folderId, tag]);

  // "/" focuses search, as in most reading tools.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = document.activeElement;
      if (e.key === "/" && !(el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement || el instanceof HTMLSelectElement)) {
        e.preventDefault();
        search.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const lib = useQuery({
    queryKey: ["library", dq, platform, source, folderId, tag, page],
    queryFn: () => api.library({ q: dq, platform, source, folder_id: folderId, tag, limit: PAGE, offset: page * PAGE }),
    placeholderData: keepPreviousData,
  });
  const folders = useQuery({ queryKey: ["folders"], queryFn: api.folders });
  const tags = useQuery({ queryKey: ["tags"], queryFn: api.tags });

  const remove = useMutation({
    mutationFn: api.remove,
    onSuccess: () => { setSelected(new Set()); qc.invalidateQueries({ queryKey: ["library"] }); qc.invalidateQueries({ queryKey: ["folders"] }); },
  });
  const zip = useMutation({ mutationFn: ({ ids, fmt }: { ids: number[]; fmt: ExportFormat }) => api.downloadZip(ids, fmt) });

  const items = lib.data?.items ?? [];
  const total = lib.data?.total ?? 0;
  const allOnPage = items.length > 0 && items.every((i) => selected.has(i.id));
  const filtered = Boolean(dq || platform || source || folderId || tag);

  const toggle = (id: number) => setSelected((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });
  const toggleAll = () => setSelected((s) => {
    const n = new Set(s);
    if (allOnPage) items.forEach((i) => n.delete(i.id)); else items.forEach((i) => n.add(i.id));
    return n;
  });

  return (
    <div>
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-serif text-[30px] leading-tight tracking-tight">Library</h1>
          <p className="num mt-1 text-[12px] text-muted">{lib.isSuccess ? `${total} transcript${total === 1 ? "" : "s"}${filtered ? " match" : ""}` : " "}</p>
        </div>
        <div className="relative w-full sm:w-80">
          <label htmlFor="search" className="sr-only">Search transcripts</label>
          <input
            id="search" ref={search} value={q} onChange={(e) => setQ(e.target.value)} type="search"
            placeholder="Search words, titles, authors" className="field w-full pr-8"
          />
          {!q && <kbd className="pointer-events-none absolute top-1/2 right-2 -translate-y-1/2 rounded border border-line px-1 font-mono text-[10px] text-muted">/</kbd>}
        </div>
      </div>

      <div className="mt-5 flex flex-wrap items-center gap-2 border-y border-line py-2.5">
        <Select label="Platform" value={platform} onChange={setPlatform}
          options={[["", "All platforms"], ["tiktok", "TikTok"], ["instagram", "Instagram"], ["youtube", "YouTube"]]} />
        <Select label="Source" value={source} onChange={setSource}
          options={[["", "Any source"], ["platform_captions", "Platform captions"], ["asr", "Speech-to-text"]]} />
        <Select label="Folder" value={folderId} onChange={setFolderId}
          options={[["", "All folders"], ...(folders.data ?? []).map((f) => [String(f.id), `${f.name} (${f.count})`] as [string, string])]} />
        {(tags.data?.length ?? 0) > 0 && (
          <Select label="Tag" value={tag} onChange={setTag}
            options={[["", "Any tag"], ...(tags.data ?? []).map((t) => [t.tag, `#${t.tag} (${t.count})`] as [string, string])]} />
        )}
        {filtered && (
          <button className="btn btn-quiet" onClick={() => { setQ(""); setPlatform(""); setSource(""); setFolderId(""); setTag(""); }}>
            Reset
          </button>
        )}
      </div>

      {selected.size > 0 && (
        <div className="sticky top-0 z-10 flex flex-wrap items-center gap-2 border-b border-line bg-paper/95 py-2 backdrop-blur">
          <span className="num mr-auto text-[13px]">{selected.size} selected</span>
          <label className="sr-only" htmlFor="fmt">Export format</label>
          <select id="fmt" className="field" value={format} onChange={(e) => setFormat(e.target.value as ExportFormat)}>
            {FORMATS.map((f) => <option key={f} value={f}>.{f}</option>)}
          </select>
          <button className="btn" disabled={zip.isPending} onClick={() => zip.mutate({ ids: [...selected], fmt: format })}>
            {zip.isPending ? "Preparing…" : "Download ZIP"}
          </button>
          <button
            className="btn hover:!border-bad hover:!text-bad"
            onClick={() => { if (confirm(`Delete ${selected.size} transcript(s)? This cannot be undone.`)) remove.mutate([...selected]); }}
          >
            Delete
          </button>
          <button className="btn btn-quiet" onClick={() => setSelected(new Set())}>Clear</button>
        </div>
      )}

      <ErrorNote error={lib.error ?? zip.error ?? remove.error} />

      {lib.isSuccess && total === 0 && (
        <div className="mt-6">
          {filtered
            ? <Empty title="No matches">Try fewer words or reset the filters.</Empty>
            : <Empty title="Your library is empty">Transcripts you make on the <Link href="/" className="underline">Inbox</Link>, or through Claude and ChatGPT, appear here.</Empty>}
        </div>
      )}

      {items.length > 0 && (
        <table className="mt-1 w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-line">
              <th className="w-8 py-2"><input type="checkbox" aria-label="Select all on this page" checked={allOnPage} onChange={toggleAll} className="accent-[var(--accent)]" /></th>
              <th className="label py-2 font-normal">Video</th>
              <th className="label hidden py-2 text-right font-normal md:table-cell">Length</th>
              <th className="label hidden py-2 text-right font-normal sm:table-cell">Views</th>
              <th className="label hidden py-2 pl-4 text-right font-normal lg:table-cell">Added</th>
            </tr>
          </thead>
          <tbody className={lib.isPlaceholderData ? "opacity-60" : ""}>
            {items.map((item) => <Row key={item.id} item={item} checked={selected.has(item.id)} onToggle={() => toggle(item.id)} />)}
          </tbody>
        </table>
      )}

      {total > PAGE && (
        <div className="mt-4 flex items-center justify-between">
          <button className="btn" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</button>
          <span className="num text-[12px] text-muted">{page * PAGE + 1}–{Math.min(total, (page + 1) * PAGE)} of {total}</span>
          <button className="btn" disabled={(page + 1) * PAGE >= total} onClick={() => setPage((p) => p + 1)}>Next</button>
        </div>
      )}
    </div>
  );
}

function Select({ label, value, onChange, options }: { label: string; value: string; onChange: (v: string) => void; options: [string, string][] }) {
  return (
    <label className="inline-flex">
      <span className="sr-only">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} className={`field ${value ? "!border-ink" : ""}`}>
        {options.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
      </select>
    </label>
  );
}

function Snippet({ text }: { text: string }) {
  // The API marks matches with [ ].
  const parts = text.split(/(\[[^\]]*\])/g);
  return (
    <p className="mt-1 line-clamp-2 font-serif text-[14px] leading-snug text-muted">
      {parts.map((p, i) => p.startsWith("[") && p.endsWith("]")
        ? <mark key={i} className="bg-transparent font-medium text-ink underline decoration-accent decoration-2 underline-offset-2">{p.slice(1, -1)}</mark>
        : <span key={i}>{p}</span>)}
    </p>
  );
}

function Row({ item, checked, onToggle }: { item: Item; checked: boolean; onToggle: () => void }) {
  return (
    <tr className={`border-b border-line align-top ${checked ? "bg-surface" : "hover:bg-surface/60"}`}>
      <td className="py-3"><input type="checkbox" aria-label={`Select ${item.title ?? "transcript"}`} checked={checked} onChange={onToggle} className="accent-[var(--accent)]" /></td>
      <td className="py-3 pr-3">
        <div className="flex gap-3">
          <Link href={`/t/${item.id}`} tabIndex={-1} className="hidden h-[52px] w-[40px] shrink-0 overflow-hidden bg-sunk sm:block">
            {item.thumbnail && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={item.thumbnail} alt="" loading="lazy" className="h-full w-full object-cover" />
            )}
          </Link>
          <div className="min-w-0">
            <Link href={`/t/${item.id}`} className="line-clamp-1 font-medium hover:underline">{item.title || "Untitled video"}</Link>
            <div className="mt-0.5 flex flex-wrap items-center gap-x-3 gap-y-0.5 text-[12.5px] text-muted">
              <PlatformMark platform={item.platform} showLabel />
              {item.author && <span>@{item.author.replace(/^@/, "")}</span>}
              {item.source === "asr" && <span className="label !text-[10px]">Speech-to-text</span>}
              {item.edited && <span className="label !text-[10px]">Edited</span>}
              {item.folder && <span>▸ {item.folder}</span>}
              {item.tags.map((t) => <span key={t}>#{t}</span>)}
            </div>
            {item.snippet && <Snippet text={item.snippet} />}
          </div>
        </div>
      </td>
      <td className="num hidden py-3 text-right text-[12.5px] text-muted md:table-cell">{item.duration_s ? clock(item.duration_s) : "–"}</td>
      <td className="num hidden py-3 text-right text-[12.5px] text-muted sm:table-cell">{compact(item.stats.view_count)}</td>
      <td className="num hidden py-3 pl-4 text-right text-[12.5px] whitespace-nowrap text-muted lg:table-cell">{day(item.created_at)}</td>
    </tr>
  );
}
