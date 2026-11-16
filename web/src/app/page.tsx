"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Empty, ErrorNote, PlatformMark, StatusPill } from "@/components/ui";
import { ACTIVE, api, countLinks, type Job } from "@/lib/api";

export default function Inbox() {
  const qc = useQueryClient();
  const box = useRef<HTMLTextAreaElement>(null);
  const [text, setText] = useState("");
  const [notes, setNotes] = useState<string[]>([]);

  const jobs = useQuery({
    queryKey: ["jobs"],
    queryFn: api.jobs,
    // Poll quickly only while something is running.
    refetchInterval: (q) => (q.state.data?.some((j) => ACTIVE.includes(j.status)) ? 1500 : 15000),
  });

  const submit = useMutation({
    mutationFn: api.submit,
    onSuccess: (res) => {
      setNotes(res.job_ids.length ? res.notes : res.notes.length ? res.notes : ["No video links found."]);
      if (res.job_ids.length) setText("");
      qc.invalidateQueries({ queryKey: ["jobs"] });
    },
  });
  const retry = useMutation({ mutationFn: api.retry, onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }) });
  const clear = useMutation({ mutationFn: api.clearFinished, onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }) });

  // Pasting anywhere on the page lands in the box.
  useEffect(() => {
    const onPaste = (e: ClipboardEvent) => {
      const el = document.activeElement;
      if (el instanceof HTMLInputElement || el instanceof HTMLTextAreaElement) return;
      const pasted = e.clipboardData?.getData("text");
      if (!pasted) return;
      e.preventDefault();
      setText((t) => (t ? `${t.trimEnd()}\n${pasted}` : pasted));
      box.current?.focus();
    };
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, []);

  const links = countLinks(text);
  const list = jobs.data ?? [];
  const running = list.filter((j) => ACTIVE.includes(j.status)).length;
  const finished = list.length - running;
  const go = () => text.trim() && !submit.isPending && submit.mutate(text);

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="font-serif text-[30px] leading-tight tracking-tight">Paste links, get transcripts.</h1>
      <p className="mt-1.5 text-[13px] text-muted">
        TikTok, Instagram Reels and YouTube. One link or many; a profile or playlist link brings in its videos.
      </p>

      <form
        className="mt-6 border border-line bg-surface focus-within:border-muted"
        onSubmit={(e) => { e.preventDefault(); go(); }}
      >
        <label htmlFor="links" className="sr-only">Video links</label>
        <textarea
          id="links"
          ref={box}
          autoFocus
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); go(); } }}
          rows={5}
          spellCheck={false}
          placeholder={"https://www.tiktok.com/@creator/video/…\nhttps://www.instagram.com/reel/…\nhttps://youtube.com/shorts/…"}
          className="block w-full resize-y bg-transparent px-4 py-3.5 font-mono text-[13px] leading-relaxed outline-none placeholder:text-muted/70"
        />
        <div className="flex items-center justify-between gap-3 border-t border-line px-3 py-2">
          <span className="num text-[12px] text-muted">
            {links ? `${links} link${links === 1 ? "" : "s"} detected` : "Ctrl/⌘ + Enter to start"}
          </span>
          <button type="submit" className="btn btn-primary" disabled={!text.trim() || submit.isPending}>
            {submit.isPending ? "Adding…" : links > 1 ? `Transcribe ${links}` : "Transcribe"}
          </button>
        </div>
      </form>

      <div className="mt-3 space-y-2">
        <ErrorNote error={submit.error} />
        {notes.map((n) => <p key={n} className="text-[13px] text-muted">{n}</p>)}
      </div>

      <section className="mt-10" aria-labelledby="queue">
        <div className="flex items-baseline justify-between border-b border-ink pb-2">
          <h2 id="queue" className="label !text-ink">
            Queue {running > 0 && <span className="num ml-1 text-accent">{running} running</span>}
          </h2>
          {finished > 0 && (
            <button className="btn btn-quiet !h-6 !px-1.5 text-[12px]" onClick={() => clear.mutate()}>Clear finished</button>
          )}
        </div>
        <ErrorNote error={jobs.error} />
        {jobs.isSuccess && list.length === 0 && (
          <div className="mt-4">
            <Empty title="Nothing in the queue">
              Paste a link above. Finished transcripts stay in the <Link className="underline" href="/library">Library</Link>,
              and Claude or ChatGPT can add to it through the MCP server (see Settings).
            </Empty>
          </div>
        )}
        <ul>
          {list.map((job) => <JobRow key={job.id} job={job} onRetry={() => retry.mutate(job.id)} />)}
        </ul>
      </section>
    </div>
  );
}

function JobRow({ job, onRetry }: { job: Job; onRetry: () => void }) {
  const title = job.title ?? job.input_url.replace(/^https?:\/\/(www\.)?/, "");
  const guess = job.platform ?? (["tiktok", "instagram", "youtube"] as const).find((p) => job.input_url.includes(p.slice(0, 5))) ?? null;
  return (
    <li className="grid grid-cols-[auto_minmax(0,1fr)_auto] items-start gap-x-3 border-b border-line py-2.5">
      <span className="pt-1.5"><PlatformMark platform={guess} /></span>
      <div className="min-w-0">
        {job.transcript_id ? (
          <Link href={`/t/${job.transcript_id}`} className="block truncate font-medium hover:underline">{title}</Link>
        ) : (
          <span className={`block truncate ${job.title ? "font-medium" : "font-mono text-[12.5px] text-muted"}`}>{title}</span>
        )}
        {job.author && job.status === "done" && <p className="text-[12.5px] text-muted">@{job.author.replace(/^@/, "")}</p>}
      </div>
      <div className="flex items-center gap-2 pt-0.5">
        <StatusPill job={job} />
        {job.status === "failed" && <button className="btn !h-6 !px-2 text-[12px]" onClick={onRetry}>Retry</button>}
      </div>
      {/* Hint spans the text and status columns so it is not squeezed on phones. */}
      {job.status === "failed" && job.hint && (
        <p className="col-span-2 col-start-2 mt-0.5 text-[12.5px] text-muted">{job.hint}</p>
      )}
    </li>
  );
}
