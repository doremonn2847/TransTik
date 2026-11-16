"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { CopyButton, ErrorNote } from "@/components/ui";
import { api } from "@/lib/api";

export default function Settings() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["status"], queryFn: api.status, refetchInterval: 10000 });
  const asrTest = useMutation({ mutationFn: api.asrTest });
  const update = useMutation({
    mutationFn: api.ytdlpUpdate,
    onSuccess: () => setTimeout(() => qc.invalidateQueries({ queryKey: ["status"] }), 6000),
  });
  const s = status.data;
  const mcpUrl = s?.mcp.local_url ?? "http://localhost:8765/mcp";

  const claudeCode = `claude mcp add --transport http transcript-desk ${mcpUrl}`;
  const desktopJson = JSON.stringify(
    { mcpServers: { "transcript-desk": { command: "npx", args: ["-y", "mcp-remote", mcpUrl] } } }, null, 2);

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="font-serif text-[30px] leading-tight tracking-tight">Settings</h1>
      <p className="mt-1.5 text-[13px] text-muted">Values come from the <code className="font-mono">.env</code> file. Change them there and restart.</p>
      <ErrorNote error={status.error} />

      <Section title="Health">
        <Check ok={s?.asr.configured} label="Speech-to-text key"
          detail={s ? (s.asr.configured ? `${s.asr.model} via ${new URL(s.asr.base_url).host}` : "Not set. Videos without captions will fail. Set ASR_API_KEY in .env.") : "…"}>
          <button className="btn" disabled={!s?.asr.configured || asrTest.isPending} onClick={() => asrTest.mutate()}>
            {asrTest.isPending ? "Testing…" : "Test key"}
          </button>
        </Check>
        {asrTest.data && <p className={`-mt-1 mb-2 pl-6 text-[12.5px] ${asrTest.data.ok ? "text-ok" : "text-bad"}`}>{asrTest.data.message}</p>}
        <Check ok={true} label="yt-dlp (link fetching)" detail={s ? `Version ${s.ytdlp_version}. Update when a platform stops working.` : "…"}>
          <button className="btn" disabled={update.isPending} onClick={() => update.mutate()}>
            {update.isPending ? "Updating…" : "Update now"}
          </button>
        </Check>
        {update.data && <p className={`-mt-1 mb-2 pl-6 text-[12.5px] ${update.data.ok ? "text-ok" : "text-bad"}`}>{update.data.message}</p>}
        <Check ok={s?.ffmpeg} label="ffmpeg" detail={s?.ffmpeg ? "Installed." : "Missing. Needed for speech-to-text. It is included in the Docker image."} />
        <Check ok={s?.js_runtime} label="JavaScript runtime (deno)" detail={s?.js_runtime ? "Installed." : "Missing. YouTube may fail without it. It is included in the Docker image."} />
        <Check ok={s?.cookies ? true : undefined} label="Cookies file (optional)"
          detail={s?.cookies ? "data/cookies.txt is in use." : "Not used. Add data/cookies.txt only if Instagram keeps asking for a login."} />
      </Section>

      <Section title="Connect Claude or ChatGPT">
        <p className="text-[13px] leading-relaxed text-muted">
          The MCP server lets an assistant transcribe links, search your library and write from your transcripts.
        </p>

        <Step title="Claude Code" body="Run once in a terminal:" code={claudeCode} />
        <Step
          title="Claude Desktop"
          body={<>Settings → Developer → Edit config, add this to <code className="font-mono">claude_desktop_config.json</code>, then restart Claude. Needs Node.js installed.</>}
          code={desktopJson}
        />
        <div className="mt-6">
          <h3 className="text-[14px] font-medium">ChatGPT and claude.ai on the web</h3>
          <p className="mt-1 text-[13px] leading-relaxed text-muted">
            These run in the cloud and cannot see your laptop. Start the tunnel with{" "}
            <code className="font-mono text-ink">docker compose --profile tunnel up -d</code>, then add the address below as a custom connector.
            It changes each time the tunnel restarts, and only works while this laptop is on.
          </p>
          {s?.mcp.tunnel_url ? (
            <div className="mt-2 flex gap-1.5">
              <code className="min-w-0 flex-1 truncate border border-line bg-sunk px-2 py-1.5 font-mono text-[12px]">{s.mcp.tunnel_url}</code>
              <CopyButton text={s.mcp.tunnel_url} />
            </div>
          ) : (
            <p className="mt-2 border border-dashed border-line px-3 py-2 text-[12.5px] text-muted">Tunnel not running.</p>
          )}
          <p className="mt-2 text-[12px] text-muted">The address contains a secret. Anyone who has it can use your library, so do not share it.</p>
        </div>
      </Section>

      <Section title="Library">
        <p className="text-[13px] text-muted">
          <span className="num text-ink">{s?.library_count ?? "–"}</span> transcript{s?.library_count === 1 ? "" : "s"}, stored in <code className="font-mono">data/app.db</code>.
          Back up or move the library by copying the <code className="font-mono">data</code> folder.
        </p>
      </Section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="mt-9">
      <h2 className="label border-b border-ink pb-2 !text-ink">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Check({ ok, label, detail, children }: { ok: boolean | undefined; label: string; detail: string; children?: ReactNode }) {
  const mark = ok === undefined ? "–" : ok ? "✓" : "!";
  const color = ok === undefined ? "text-muted" : ok ? "text-ok" : "text-bad";
  return (
    <div className="flex items-center gap-3 border-b border-line py-2.5">
      <span aria-hidden className={`num w-3 text-center ${color}`}>{mark}</span>
      <div className="min-w-0 flex-1">
        <p className="font-medium">{label}</p>
        <p className="text-[12.5px] text-muted">{detail}</p>
      </div>
      {children}
    </div>
  );
}

function Step({ title, body, code }: { title: string; body: ReactNode; code: string }) {
  return (
    <div className="mt-5">
      <h3 className="text-[14px] font-medium">{title}</h3>
      <p className="mt-1 text-[13px] text-muted">{body}</p>
      <div className="relative mt-2">
        <pre className="overflow-x-auto border border-line bg-sunk px-3 py-2.5 pr-20 font-mono text-[12px] leading-relaxed">{code}</pre>
        <div className="absolute top-1.5 right-1.5"><CopyButton text={code} className="btn !h-7" /></div>
      </div>
    </div>
  );
}
