"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { CopyButton, ErrorNote } from "@/components/ui";
import { api, type AsrStatus } from "@/lib/api";

export default function Settings() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["status"], queryFn: api.status, refetchInterval: 10000 });
  const update = useMutation({
    mutationFn: api.ytdlpUpdate,
    onSuccess: () => setTimeout(() => qc.invalidateQueries({ queryKey: ["status"] }), 6000),
  });
  const s = status.data;
  const mcpUrl = s?.mcp.local_url ?? "http://localhost:8765/mcp";

  const claudeCode = `claude mcp add --transport http transtik ${mcpUrl}`;
  const desktopJson = JSON.stringify(
    { mcpServers: { transtik: { command: "npx", args: ["-y", "mcp-remote", mcpUrl] } } }, null, 2);

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="font-serif text-[30px] leading-tight tracking-tight">Settings</h1>
      <ErrorNote error={status.error} />

      <Section title="Speech-to-text">
        <p className="text-[13px] leading-relaxed text-muted">
          Most TikToks and Reels have no captions, so TransTik listens to the audio instead. That needs an API key
          from OpenAI or Groq. It costs well under a cent per short video; videos with captions cost nothing.
        </p>
        {s ? <AsrForm asr={s.asr} /> : <p className="mt-3 text-muted">Loading…</p>}
      </Section>

      <Section title="Health">
        <Check ok={true} label="yt-dlp (link fetching)" detail={s ? `Version ${s.ytdlp_version}. Update when a platform stops working.` : "…"}>
          <button className="btn" disabled={update.isPending} onClick={() => update.mutate()}>
            {update.isPending ? "Updating…" : "Update now"}
          </button>
        </Check>
        {update.data && <p className={`-mt-1 mb-2 pl-6 text-[12.5px] ${update.data.ok ? "text-ok" : "text-bad"}`}>{update.data.message}</p>}
        <Check ok={s?.ffmpeg} label="ffmpeg (audio)" detail={s?.ffmpeg ? "Installed." : "Missing. Needed for speech-to-text. It is included in the Docker image."} />
        <Check ok={s?.js_runtime} label="JavaScript runtime (YouTube)" detail={s?.js_runtime ? "Installed." : "Missing. YouTube may fail without it. It is included in the Docker image."} />
        <Check ok={s?.cookies ? true : undefined} label="Cookies file (optional)"
          detail={s?.cookies ? "data/cookies.txt is in use." : "Not used. Add data/cookies.txt only if Instagram keeps asking for a login."} />
      </Section>

      <Section title="Connect Claude or ChatGPT">
        <p className="text-[13px] leading-relaxed text-muted">
          The MCP server lets an assistant transcribe links, search your library and write from your transcripts.
        </p>

        <Step
          title="Claude Desktop"
          body={<>Needs <a className="underline" href="https://nodejs.org" target="_blank" rel="noreferrer">Node.js</a>. In Claude: Settings → Developer → Edit Config, paste this into <code className="font-mono">claude_desktop_config.json</code> (merge with anything already there), save, then quit and reopen Claude.</>}
          code={desktopJson}
        />
        <Step title="Claude Code" body="Run once in a terminal:" code={claudeCode} />
        <div className="mt-6">
          <h3 className="text-[14px] font-medium">ChatGPT and claude.ai on the web</h3>
          <p className="mt-1 text-[13px] leading-relaxed text-muted">
            These run in the cloud and cannot see your computer. Start the tunnel with{" "}
            <code className="font-mono text-ink">docker compose --profile tunnel up -d</code>, then add the address below as a custom connector.
            It changes each time the tunnel restarts, and only works while this computer is on.
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

function AsrForm({ asr }: { asr: AsrStatus }) {
  const qc = useQueryClient();
  const [provider, setProvider] = useState<string>(asr.provider === "custom" && asr.source === "none" ? "openai" : asr.provider);
  const [key, setKey] = useState("");
  const [baseUrl, setBaseUrl] = useState(asr.provider === "custom" ? asr.base_url : "");
  const [model, setModel] = useState(asr.provider === "custom" ? asr.model : "");
  const [editing, setEditing] = useState(!asr.configured);

  const refresh = () => qc.invalidateQueries({ queryKey: ["status"] });
  const save = useMutation({
    mutationFn: () => api.saveAsr({ provider, api_key: key, ...(provider === "custom" ? { base_url: baseUrl, model } : {}) }),
    onSuccess: (res) => { setKey(""); if (res.test.ok) setEditing(false); refresh(); },
  });
  const test = useMutation({ mutationFn: api.asrTest });
  const clear = useMutation({ mutationFn: api.clearAsr, onSuccess: () => { setEditing(true); save.reset(); test.reset(); refresh(); } });

  const result = save.data?.test ?? test.data;
  const providerName = asr.providers[asr.provider]?.label ?? "Custom provider";

  if (!editing) {
    return (
      <div className="mt-3">
        <Check ok={true} label={`${providerName} · ${asr.model}`}
          detail={`Key ${asr.key_hint ?? ""}${asr.source === "env" ? " (from the .env file)" : ""}`}>
          <button className="btn" disabled={test.isPending} onClick={() => test.mutate()}>{test.isPending ? "Testing…" : "Test key"}</button>
          <button className="btn" onClick={() => { setEditing(true); test.reset(); }}>Change</button>
        </Check>
        {result && <p className={`mt-1 text-[12.5px] ${result.ok ? "text-ok" : "text-bad"}`}>{result.message}</p>}
      </div>
    );
  }

  const keyHelp = provider === "groq"
    ? <>Get one at <a className="underline" href="https://console.groq.com/keys" target="_blank" rel="noreferrer">console.groq.com/keys</a>.</>
    : provider === "openai"
      ? <>Get one at <a className="underline" href="https://platform.openai.com/api-keys" target="_blank" rel="noreferrer">platform.openai.com/api-keys</a>. It starts with <code className="font-mono">sk-</code>.</>
      : "Any OpenAI-compatible transcription service.";

  return (
    <form className="mt-4 space-y-3 border border-line bg-surface p-4" onSubmit={(e) => { e.preventDefault(); save.mutate(); }}>
      <div>
        <label htmlFor="provider" className="block text-[12px] text-muted">Provider</label>
        <select id="provider" className="field mt-1 w-full sm:w-64" value={provider} onChange={(e) => setProvider(e.target.value)}>
          <option value="openai">OpenAI (whisper-1)</option>
          <option value="groq">Groq (whisper-large-v3-turbo, cheaper)</option>
          <option value="custom">Other OpenAI-compatible service</option>
        </select>
      </div>
      {provider === "custom" && (
        <div className="grid gap-3 sm:grid-cols-2">
          <div>
            <label htmlFor="base" className="block text-[12px] text-muted">API address</label>
            <input id="base" className="field mt-1 w-full font-mono" placeholder="https://…/v1" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />
          </div>
          <div>
            <label htmlFor="model" className="block text-[12px] text-muted">Model</label>
            <input id="model" className="field mt-1 w-full font-mono" placeholder="whisper-1" value={model} onChange={(e) => setModel(e.target.value)} />
          </div>
        </div>
      )}
      <div>
        <label htmlFor="key" className="block text-[12px] text-muted">API key</label>
        <input
          id="key" type="password" autoComplete="off" spellCheck={false} className="field mt-1 w-full font-mono"
          placeholder={asr.key_hint ? `Current: ${asr.key_hint}` : "Paste your key here"} value={key} onChange={(e) => setKey(e.target.value)}
        />
        <p className="mt-1 text-[12px] text-muted">{keyHelp} Saved only on this computer, in <code className="font-mono">data/settings.json</code>.</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button type="submit" className="btn btn-primary" disabled={!key.trim() || save.isPending}>
          {save.isPending ? "Saving and testing…" : "Save and test"}
        </button>
        {asr.configured && <button type="button" className="btn btn-quiet" onClick={() => { setEditing(false); setKey(""); save.reset(); }}>Cancel</button>}
        {asr.source === "settings" && (
          <button type="button" className="btn btn-quiet ml-auto hover:!text-bad" onClick={() => confirm("Remove the saved API key?") && clear.mutate()}>
            Remove saved key
          </button>
        )}
      </div>
      <ErrorNote error={save.error ?? clear.error} />
      {result && <p className={`text-[12.5px] ${result.ok ? "text-ok" : "text-bad"}`}>{result.message}</p>}
    </form>
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
    <div className="flex flex-wrap items-center gap-3 border-b border-line py-2.5">
      <span aria-hidden className={`num w-3 text-center ${color}`}>{mark}</span>
      <div className="min-w-0 flex-1">
        <p className="font-medium">{label}</p>
        <p className="text-[12.5px] text-muted">{detail}</p>
      </div>
      {children && <div className="flex gap-2">{children}</div>}
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
