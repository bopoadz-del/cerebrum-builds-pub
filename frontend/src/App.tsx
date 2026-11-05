/**
 * Harbourline Civil Works — contracts administration console.
 *
 * Source copy of app/static/index.html for teams that build the console
 * themselves. Nothing in this repository imports it; it carries no build
 * step, no external asset and no network call other than same-origin /v1
 * routes. The platform token is held in sessionStorage only and is never
 * written into this file.
 *
 * Targets the automatic JSX runtime (React 17+).
 */

import { useEffect, useState } from "react";
import type { FormEvent, ReactNode } from "react";

const TOKEN_KEY = "harbourline.console.token";

/** The three capabilities this console drives end to end are pinned first. */
const PREFERRED_CAPABILITIES = [
  "progress_claims",
  "delay_damages_tracking",
  "retention_defects_release",
];

type Json = Record<string, any>;

type FieldDef = {
  name: string;
  type: string;
  required: boolean;
  allowed_values?: Array<string | number> | null;
  min?: number | null;
  max?: number | null;
};

type Capability = {
  id: string;
  entity?: string;
  title: string;
  summary: string;
  blocks: string[];
  fields: FieldDef[];
};

type ApiResult = { status: number; ok: boolean; body: Json };
type ReadAnswer = { id: string; result: ApiResult };

/* ------------------------------------------------------------------ */
/* transport                                                          */
/* ------------------------------------------------------------------ */

async function callApi(
  token: string,
  path: string,
  init: { method?: string; body?: unknown } = {}
): Promise<ApiResult> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (init.body !== undefined) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;
  try {
    const response = await fetch(path, {
      method: init.method ?? "GET",
      headers,
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    });
    const text = await response.text();
    let body: Json;
    try {
      body = text ? (JSON.parse(text) as Json) : { ok: false, error: "empty response body" };
    } catch {
      body = { ok: false, error: `non-JSON response: ${text.slice(0, 200)}` };
    }
    return { status: response.status, ok: response.ok, body };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    return { status: 0, ok: false, body: { ok: false, error: `network error: ${message}` } };
  }
}

/* ------------------------------------------------------------------ */
/* pure helpers                                                       */
/* ------------------------------------------------------------------ */

function isOk(result: ApiResult): boolean {
  const body = result.body ?? {};
  if (body.ok === false) return false;
  if (body.ok === true) return true;
  return result.status >= 200 && result.status < 300;
}

function authorityLabel(body: Json | null | undefined): string | null {
  const label = body?.result?.authority?.label ?? body?.authority?.label;
  return typeof label === "string" && label ? label : null;
}

function rangeText(field: FieldDef): string {
  const min = field.min === undefined || field.min === null ? null : field.min;
  const max = field.max === undefined || field.max === null ? null : field.max;
  if (min === null && max === null) return "";
  if (min !== null && max !== null) return `min ${min}, max ${max}`;
  return min !== null ? `min ${min}` : `max ${max}`;
}

function metaText(field: FieldDef): string {
  const parts: string[] = [field.type || "str", field.required ? "required" : "optional"];
  const range = rangeText(field);
  if (range) parts.push(range);
  const allowed = field.allowed_values ?? [];
  if (allowed.length) parts.push(`one of ${allowed.join("|")}`);
  return parts.join(" · ");
}

function columnsOf(rows: Json[]): string[] {
  const seen = new Set<string>();
  const columns: string[] = [];
  for (const row of rows) {
    for (const key of Object.keys(row ?? {})) {
      if (!seen.has(key)) {
        seen.add(key);
        columns.push(key);
      }
    }
  }
  return columns;
}

function formatCell(value: unknown): string {
  if (value === null || value === undefined) return "—";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function buildBody(
  fields: FieldDef[],
  valueOf: (field: FieldDef) => string | boolean
): Json {
  const body: Json = {};
  for (const field of fields) {
    const value = valueOf(field);
    if (field.type === "bool") {
      body[field.name] = Boolean(value);
      continue;
    }
    const text = String(value ?? "").trim();
    if (text === "") {
      body[field.name] = null;
      continue;
    }
    if (field.type === "int") body[field.name] = Number.parseInt(text, 10);
    else if (field.type === "float") body[field.name] = Number(text);
    else body[field.name] = text;
  }
  return body;
}

/* ------------------------------------------------------------------ */
/* shared display pieces                                              */
/* ------------------------------------------------------------------ */

function Badges({
  result,
  authorityFallback,
}: {
  result: ApiResult;
  authorityFallback?: string;
}) {
  const body = result.body ?? {};
  const good = isOk(result);
  const label = authorityLabel(body) ?? authorityFallback ?? "not stated by this route";
  return (
    <div className="chips">
      <span className={`badge ${good ? "good" : "bad"}`}>HTTP {result.status}</span>
      <span className={`badge ${good ? "good" : "bad"}`}>ok:{good ? "true" : "false"}</span>
      <span className="badge mono">authority: {label}</span>
      {body.id !== undefined && body.id !== null ? (
        <span className="badge mono">record id {String(body.id)}</span>
      ) : null}
    </div>
  );
}

function ErrorBlock({ result }: { result: ApiResult }) {
  if (isOk(result)) return null;
  const body = result.body ?? {};
  const message = body.error ?? body.detail ?? `HTTP ${result.status}`;
  const allowed: Array<string | number> = Array.isArray(body.allowed_values) ? body.allowed_values : [];
  return (
    <div>
      <p className="error">ok:false · {String(message)}</p>
      {body.rejected_field ? (
        <p className="hint">
          rejected field <span className="mono">{String(body.rejected_field)}</span>
          {allowed.length ? (
            <>
              {" "}
              · allowed: <span className="mono">{allowed.join(", ")}</span>
            </>
          ) : null}
        </p>
      ) : null}
      {result.status === 401 ? (
        <p className="hint warn">set the platform token in the header, then press Use token.</p>
      ) : null}
    </div>
  );
}

function JsonBlock({ title, value, open = false }: { title: string; value: unknown; open?: boolean }) {
  return (
    <details open={open}>
      <summary>{title}</summary>
      <pre className="scroll">{JSON.stringify(value ?? null, null, 2)}</pre>
    </details>
  );
}

function FieldsTable({ fields }: { fields: FieldDef[] }) {
  if (!fields.length) return <p className="hint">No fields declared.</p>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>field</th>
            <th>type</th>
            <th>required</th>
            <th>allowed values</th>
            <th>range</th>
          </tr>
        </thead>
        <tbody>
          {fields.map((field) => (
            <tr key={field.name}>
              <td className="mono">{field.name}</td>
              <td>{field.type || "str"}</td>
              <td>{field.required ? "yes" : "no"}</td>
              <td className="mono">{(field.allowed_values ?? []).join(", ") || "—"}</td>
              <td>{rangeText(field) || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function CapabilityForm({
  cap,
  token,
  onPosted,
}: {
  cap: Capability;
  token: string;
  onPosted: (result: ApiResult, request: Json) => void;
}) {
  const [values, setValues] = useState<Record<string, string | boolean>>({});
  const [busy, setBusy] = useState(false);

  const valueOf = (field: FieldDef): string | boolean => {
    const current: string | boolean | undefined = values[field.name];
    if (current !== undefined) return current;
    return field.type === "bool" ? false : "";
  };

  const setValue = (name: string, value: string | boolean) => {
    setValues((previous) => ({ ...previous, [name]: value }));
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const request = buildBody(cap.fields ?? [], valueOf);
    setBusy(true);
    const result = await callApi(token, `/v1/${encodeURIComponent(cap.id)}`, {
      method: "POST",
      body: request,
    });
    setBusy(false);
    onPosted(result, request);
  };

  return (
    <section className="card">
      <h3>New record</h3>
      <p className="hint">
        POST <span className="mono">/v1/{cap.id}</span> · the body is built from the declared fields.
      </p>
      <form onSubmit={(event) => void submit(event)}>
        <div className="fields">
          {(cap.fields ?? []).map((field) => {
            const inputId = `field-${cap.id}-${field.name}`;
            const allowed = field.allowed_values ?? [];
            return (
              <div className="field" key={field.name}>
                <label htmlFor={inputId}>
                  <span className="mono">{field.name}</span>
                  <span className="ftype">{metaText(field)}</span>
                </label>
                {allowed.length ? (
                  <select
                    id={inputId}
                    name={field.name}
                    required={field.required}
                    value={String(valueOf(field) ?? "")}
                    onChange={(event) => setValue(field.name, event.target.value)}
                  >
                    <option value="">(unset)</option>
                    {allowed.map((option) => (
                      <option key={String(option)} value={String(option)}>
                        {String(option)}
                      </option>
                    ))}
                  </select>
                ) : field.type === "bool" ? (
                  <input
                    id={inputId}
                    name={field.name}
                    type="checkbox"
                    checked={Boolean(valueOf(field))}
                    onChange={(event) => setValue(field.name, event.target.checked)}
                  />
                ) : (
                  <input
                    id={inputId}
                    name={field.name}
                    type={
                      field.type === "date"
                        ? "date"
                        : field.type === "int" || field.type === "float"
                          ? "number"
                          : "text"
                    }
                    step={field.type === "int" ? 1 : field.type === "float" ? "any" : undefined}
                    min={field.min ?? undefined}
                    max={field.max ?? undefined}
                    required={field.required}
                    value={String(valueOf(field) ?? "")}
                    onChange={(event) => setValue(field.name, event.target.value)}
                  />
                )}
              </div>
            );
          })}
        </div>
        <div className="actions">
          <button type="submit" disabled={busy}>
            Submit record
          </button>
          <button type="reset" className="ghost" onClick={() => setValues({})}>
            Reset
          </button>
        </div>
      </form>
    </section>
  );
}

function CapabilityPanel({
  cap,
  token,
  hidden,
}: {
  cap: Capability;
  token: string;
  hidden: boolean;
}) {
  const [answer, setAnswer] = useState<ApiResult | null>(null);
  const [request, setRequest] = useState<Json | null>(null);
  const [list, setList] = useState<ApiResult | null>(null);
  const [read, setRead] = useState<ReadAnswer | null>(null);
  const [readId, setReadId] = useState("");
  const [busy, setBusy] = useState<"" | "list" | "read">("");

  const loadList = async () => {
    setBusy("list");
    const result = await callApi(token, `/v1/${encodeURIComponent(cap.id)}`);
    setList(result);
    setBusy("");
  };

  const readOne = async (raw: string) => {
    const id = raw.trim();
    if (!id) {
      setRead({
        id: "(none)",
        result: { status: 0, ok: false, body: { ok: false, error: "a record id is required" } },
      });
      return;
    }
    setBusy("read");
    const result = await callApi(
      token,
      `/v1/${encodeURIComponent(cap.id)}/${encodeURIComponent(id)}`
    );
    setRead({ id, result });
    setBusy("");
  };

  useEffect(() => {
    // One fetch when the panel is first revealed, and again after the
    // operator applies a different token. Later reloads are explicit.
    if (!hidden) void loadList();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hidden, token]);

  const rows: Json[] = list && Array.isArray(list.body.items) ? (list.body.items as Json[]) : [];
  const columns = columnsOf(rows);
  const readInputId = `read-${cap.id}`;

  return (
    <div hidden={hidden}>
      <div className="cap-head">
        <div>
          <h2>{cap.title}</h2>
          <p className="mono small">
            {cap.id} · entity {cap.entity ?? cap.id}
          </p>
          <p className="summary">{cap.summary}</p>
        </div>
        <div className="chips">
          {(cap.blocks ?? []).map((block) => (
            <span className="chip mono" key={block}>
              {block}
            </span>
          ))}
        </div>
      </div>

      <div className="grid2">
        <section className="card">
          <h3>Declared fields</h3>
          <FieldsTable fields={cap.fields ?? []} />
        </section>
        <CapabilityForm
          cap={cap}
          token={token}
          onPosted={(result, posted) => {
            setAnswer(result);
            setRequest(posted);
            if (isOk(result)) void loadList();
          }}
        />
      </div>

      <section className="card">
        <h3>
          Answer <span className="hint mono">POST /v1/{cap.id}</span>
        </h3>
        {answer ? (
          <>
            <Badges result={answer} />
            <ErrorBlock result={answer} />
            {isOk(answer) ? (
              <p className="hint">
                entity <span className="mono">{String(answer.body.entity ?? cap.id)}</span> · created
                record <span className="mono">#{String(answer.body.id)}</span>
              </p>
            ) : null}
            {request ? <JsonBlock title="Request body" value={request} /> : null}
            {answer.body.result !== undefined && answer.body.result !== null ? (
              <JsonBlock title="Computed result" value={answer.body.result} open />
            ) : null}
            {answer.body.record !== undefined && answer.body.record !== null ? (
              <JsonBlock title="Stored record" value={answer.body.record} />
            ) : null}
            {!isOk(answer) ? <JsonBlock title="Refusal as data" value={answer.body} open /> : null}
          </>
        ) : (
          <p className="hint">No submission yet. Fill the form and submit the record.</p>
        )}
      </section>

      <section className="card">
        <h3>
          Records <span className="hint mono">GET /v1/{cap.id}</span>{" "}
          <button type="button" className="ghost" onClick={() => void loadList()} disabled={busy === "list"}>
            Refresh
          </button>
        </h3>
        {busy === "list" ? <p className="hint">Loading records…</p> : null}
        {list ? (
          <>
            <Badges result={list} authorityFallback="record store" />
            <ErrorBlock result={list} />
            {rows.length ? (
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      {columns.map((column) => (
                        <th key={column}>{column}</th>
                      ))}
                      <th>read</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((row) => (
                      <tr key={String(row.id)}>
                        {columns.map((column) => (
                          <td key={column} className={column === "id" ? "mono" : undefined}>
                            {formatCell(row[column])}
                          </td>
                        ))}
                        <td>
                          <button
                            type="button"
                            className="ghost mono"
                            onClick={() => {
                              const id = String(row.id);
                              setReadId(id);
                              void readOne(id);
                            }}
                          >
                            GET {String(row.id)}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : list.body.ok ? (
              <p className="hint">No records yet for this tenant.</p>
            ) : null}
            <p className="hint">
              total <span className="mono">{String(list.body.total ?? rows.length)}</span> · showing{" "}
              {rows.length}
            </p>
          </>
        ) : null}
      </section>

      <section className="card">
        <h3>
          Read one{" "}
          <span className="hint mono">{`GET /v1/${cap.id}/{record_id}`}</span>
        </h3>
        <form
          className="inline"
          onSubmit={(event) => {
            event.preventDefault();
            void readOne(readId);
          }}
        >
          <div>
            <label className="hint" htmlFor={readInputId}>
              record id
            </label>
            <input
              id={readInputId}
              name="record_id"
              type="number"
              min={1}
              step={1}
              placeholder="1"
              required
              value={readId}
              onChange={(event) => setReadId(event.target.value)}
            />
          </div>
          <button type="submit" disabled={busy === "read"}>
            GET record
          </button>
        </form>
        {busy === "read" ? <p className="hint">Reading…</p> : null}
        {read ? (
          <>
            <Badges result={read.result} authorityFallback="record store" />
            <ErrorBlock result={read.result} />
            <JsonBlock title={`Answer for id ${read.id}`} value={read.result.body} open />
          </>
        ) : busy !== "read" ? (
          <p className="hint">No read yet.</p>
        ) : null}
      </section>
    </div>
  );
}

function KernelSection({
  title,
  route,
  result,
  busy,
  children,
}: {
  title: string;
  route: string;
  result: ApiResult | null;
  busy: boolean;
  children?: ReactNode;
}) {
  return (
    <div className="kernel-block">
      <h3>
        {title} <span className="hint mono">{route}</span>
      </h3>
      {result ? (
        <>
          <Badges result={result} authorityFallback="kernel route" />
          <ErrorBlock result={result} />
          {children}
          <JsonBlock title="Raw answer" value={result.body} open={route === "GET /v1/gates"} />
        </>
      ) : (
        <p className="hint">{busy ? "Loading…" : "Not loaded yet."}</p>
      )}
    </div>
  );
}

function KernelPanel({ token, hidden }: { token: string; hidden: boolean }) {
  const [answers, setAnswers] = useState<{
    jobs: ApiResult | null;
    provenance: ApiResult | null;
    gates: ApiResult | null;
  }>({ jobs: null, provenance: null, gates: null });
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setBusy(true);
    const [jobs, provenance, gates] = await Promise.all([
      callApi(token, "/v1/jobs"),
      callApi(token, "/v1/provenance"),
      callApi(token, "/v1/gates"),
    ]);
    setAnswers({ jobs, provenance, gates });
    setBusy(false);
  };

  useEffect(() => {
    if (!hidden) void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hidden, token]);

  const jobs: Json[] =
    answers.jobs && Array.isArray(answers.jobs.body.jobs)
      ? (answers.jobs.body.jobs as Json[])
      : [];

  return (
    <div hidden={hidden}>
      <section className="card">
        <h2>Kernel</h2>
        <p className="hint">
          GET <span className="mono">/v1/jobs</span>, <span className="mono">/v1/provenance</span>,{" "}
          <span className="mono">/v1/gates</span>{" "}
          <button type="button" className="ghost" onClick={() => void load()} disabled={busy}>
            Reload kernel
          </button>
        </p>
        <KernelSection title="Jobs" route="GET /v1/jobs" result={answers.jobs} busy={busy}>
          {jobs.length ? (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>kernel</th>
                    <th>title</th>
                    <th>mandate</th>
                    <th>http routes</th>
                    <th>agent</th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((job) => (
                    <tr key={String(job.kernel)}>
                      <td className="mono">{String(job.kernel ?? "")}</td>
                      <td>{String(job.title ?? "")}</td>
                      <td>{String(job.mandate ?? "")}</td>
                      <td className="mono">{Array.isArray(job.http_routes) ? job.http_routes.join(", ") : ""}</td>
                      <td className="mono">{String(job.agent ?? "")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </KernelSection>
        <KernelSection
          title="Provenance"
          route="GET /v1/provenance"
          result={answers.provenance}
          busy={busy}
        />
        <KernelSection title="Gates" route="GET /v1/gates" result={answers.gates} busy={busy} />
      </section>
    </div>
  );
}

function CapabilitiesOverview({
  result,
  loading,
  onReload,
}: {
  result: ApiResult | null;
  loading: boolean;
  onReload: () => void;
}) {
  const items: Capability[] = result && Array.isArray(result.body.items) ? result.body.items : [];
  return (
    <section className="card">
      <h2>Capabilities</h2>
      <p className="hint">
        GET <span className="mono">/v1/capabilities</span>{" "}
        <button type="button" className="ghost" onClick={onReload} disabled={loading}>
          Reload
        </button>
      </p>
      {result ? (
        <>
          <Badges result={result} authorityFallback="platform declaration" />
          <ErrorBlock result={result} />
          {items.map((cap) => (
            <div className="kernel-block" key={cap.id}>
              <h3>{cap.title}</h3>
              <p className="mono small">
                {cap.id}
                {cap.entity ? ` · entity ${cap.entity}` : ""}
              </p>
              <p className="summary">{cap.summary}</p>
              <div className="chips">
                {(cap.blocks ?? []).map((block) => (
                  <span className="chip mono" key={block}>
                    {block}
                  </span>
                ))}
              </div>
              <FieldsTable fields={cap.fields ?? []} />
            </div>
          ))}
          <p className="hint">{items.length} capability(ies) declared by the platform.</p>
        </>
      ) : (
        <p className="hint">Loading capabilities…</p>
      )}
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* console shell                                                      */
/* ------------------------------------------------------------------ */

export default function App() {
  const [token, setToken] = useState<string>(() => {
    try {
      return sessionStorage.getItem(TOKEN_KEY) ?? "";
    } catch {
      return "";
    }
  });
  const [draft, setDraft] = useState<string>(() => {
    try {
      return sessionStorage.getItem(TOKEN_KEY) ?? "";
    } catch {
      return "";
    }
  });
  const [capsResult, setCapsResult] = useState<ApiResult | null>(null);
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [loadingCaps, setLoadingCaps] = useState(false);
  const [active, setActive] = useState("capabilities");

  const applyToken = (value: string) => {
    const trimmed = value.trim();
    try {
      if (trimmed) sessionStorage.setItem(TOKEN_KEY, trimmed);
      else sessionStorage.removeItem(TOKEN_KEY);
    } catch {
      // sessionStorage can be unavailable; the token then lives for this page only.
    }
    setToken(trimmed);
    setCapsResult(null);
    setCapabilities([]);
    setLoadingCaps(true);
    void callApi(trimmed, "/v1/capabilities").then((result) => {
      setCapsResult(result);
      if (result.body.ok && Array.isArray(result.body.items)) {
        setCapabilities(result.body.items as Capability[]);
      }
      setLoadingCaps(false);
    });
  };

  useEffect(() => {
    void callApi(token, "/v1/capabilities").then((result) => {
      setCapsResult(result);
      if (result.body.ok && Array.isArray(result.body.items)) {
        setCapabilities(result.body.items as Capability[]);
      }
    });
    // Mount only: the initial token comes from sessionStorage.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ordered = capabilities.slice().sort((a, b) => {
    const rankA = PREFERRED_CAPABILITIES.indexOf(a.id);
    const rankB = PREFERRED_CAPABILITIES.indexOf(b.id);
    return (rankA === -1 ? PREFERRED_CAPABILITIES.length : rankA) -
      (rankB === -1 ? PREFERRED_CAPABILITIES.length : rankB);
  });

  const tabs = [{ id: "capabilities", title: "Capabilities" }, ...ordered.map((cap) => ({
    id: cap.id,
    title: cap.title,
  })), { id: "kernel", title: "Kernel" }];

  return (
    <div className="app">
      <style>{CSS}</style>
      <header className="bar">
        <div className="brand">
          <div className="mark">HCW</div>
          <div className="brand-text">
            <h1>Harbourline Civil Works</h1>
            <p>Contracts administration console</p>
          </div>
        </div>
        <form
          className="token"
          onSubmit={(event) => {
            event.preventDefault();
            applyToken(draft);
          }}
        >
          <div>
            <label htmlFor="token">Platform token</label>
            <input
              id="token"
              name="token"
              type="password"
              autoComplete="off"
              spellCheck={false}
              placeholder="paste platform token"
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
            />
          </div>
          <button type="submit">Use token</button>
          <button
            type="button"
            className="ghost"
            onClick={() => {
              setDraft("");
              applyToken("");
            }}
          >
            Clear
          </button>
        </form>
      </header>

      {token ? (
        <div className="notice">Platform token applied for this browser session (sessionStorage only).</div>
      ) : (
        <div className="notice warn">
          No platform token set. Set the platform token in the header; every /v1 call is refused with 401
          until you do.
        </div>
      )}

      <nav className="tabs" aria-label="Console sections">
        {tabs.map((tab) => (
          <button
            type="button"
            key={tab.id}
            className={`tab${active === tab.id ? " on" : ""}`}
            onClick={() => setActive(tab.id)}
          >
            {tab.title}
          </button>
        ))}
      </nav>

      <main>
        {active === "capabilities" ? (
          <CapabilitiesOverview
            result={capsResult}
            loading={loadingCaps}
            onReload={() => applyToken(token)}
          />
        ) : null}
        {ordered.map((cap) => (
          <CapabilityPanel key={cap.id} cap={cap} token={token} hidden={active !== cap.id} />
        ))}
        <KernelPanel token={token} hidden={active !== "kernel"} />
      </main>

      <footer className="foot">
        Every answer is shown with the authority label the platform returned. The token is held in this
        browser session only and is sent as a bearer principal on each <span className="mono">/v1</span> call.
      </footer>
    </div>
  );
}

const CSS = `
:root{--ink:#0d1b26;--ink2:#3c5266;--line:#d9e1e9;--bg:#f3f5f8;--card:#ffffff;--navy:#0f2738;--navy2:#17405b;--gold:#b7791f;--good:#1f6b46;--bad:#a52a2a;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
h1,h2,h3{margin:0;font-weight:600}
h1{font-size:17px;letter-spacing:.2px}
h2{font-size:18px;margin-bottom:4px}
h3{font-size:15px;margin-bottom:8px}
p{margin:0 0 8px}
.bar{display:flex;flex-wrap:wrap;gap:16px;align-items:center;justify-content:space-between;background:var(--navy);color:#eef3f7;padding:14px 22px;border-bottom:3px solid var(--gold)}
.brand{display:flex;align-items:center;gap:12px}
.mark{font-family:var(--mono);font-weight:700;font-size:13px;letter-spacing:1px;border:1px solid rgba(255,255,255,.45);padding:8px 10px;border-radius:3px}
.brand-text p{margin:2px 0 0;color:#a9c1d2;font-size:12px;letter-spacing:.4px;text-transform:uppercase}
.token{display:flex;align-items:flex-end;gap:8px;flex-wrap:wrap}
.token label{display:block;font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:#a9c1d2}
input,select,button,textarea{font:inherit;color:var(--ink)}
input,select{padding:6px 8px;border:1px solid var(--line);border-radius:3px;background:#fff;min-width:150px}
input[type=checkbox]{min-width:0;width:16px;height:16px;margin-top:6px}
button{padding:6px 12px;border:1px solid var(--navy2);background:var(--navy2);color:#fff;border-radius:3px;cursor:pointer;font-size:13px}
button:hover{background:#1d5174}
button.ghost{background:transparent;color:var(--navy2);border-color:#bfd0dd}
button.ghost:hover{background:#e8eef4}
.token input{background:#10324a;border-color:#2a5675;color:#eef3f7;min-width:220px}
.token button.ghost{color:#cfe0ec;border-color:#3c6683}
.notice{margin:14px 22px 0;padding:10px 14px;border:1px solid #cfe0ec;border-left:4px solid var(--navy2);background:#eaf1f7;border-radius:3px}
.notice.warn{border-left-color:var(--gold);background:#fbf3e4}
.tabs{display:flex;flex-wrap:wrap;gap:2px;margin:16px 22px 0;border-bottom:1px solid var(--line)}
.tab{background:transparent;border:1px solid transparent;border-bottom:none;color:var(--ink2);border-radius:3px 3px 0 0;padding:8px 14px}
.tab:hover{background:#e7edf3;color:var(--ink)}
.tab.on{background:var(--card);border-color:var(--line);color:var(--navy);font-weight:600;margin-bottom:-1px}
main{display:block;padding:16px 22px 32px;max-width:1280px}
.card{background:var(--card);border:1px solid var(--line);border-radius:4px;padding:16px;margin-bottom:16px;box-shadow:0 1px 2px rgba(15,39,56,.06)}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:16px}
.cap-head{display:flex;flex-wrap:wrap;justify-content:space-between;gap:16px;margin-bottom:14px}
.summary{color:var(--ink2);max-width:70ch;margin:6px 0 0}
.chips{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0}
.chip{font-size:12px;padding:2px 7px;border:1px solid var(--line);border-radius:10px;background:#eef2f6;color:var(--ink2)}
.badge{display:inline-block;font-size:12px;padding:2px 8px;border:1px solid var(--line);border-radius:10px;background:#eef2f6;color:var(--ink2)}
.badge.good{background:#e6f2ea;border-color:#bcdcc8;color:var(--good)}
.badge.bad{background:#f8e8e8;border-color:#e2bcbc;color:var(--bad)}
.mono{font-family:var(--mono)}
.small{font-size:12px}
.hint{color:var(--ink2);font-size:12px;margin:4px 0}
.hint.warn{color:#8a5a12;font-weight:600}
.error{color:var(--bad);font-weight:600;margin:6px 0}
.fields{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px 14px;margin:8px 0 14px}
.field label{display:flex;flex-direction:column;gap:1px;margin-bottom:4px}
.field .ftype{font-size:11px;color:#5d7387}
.field input,.field select{width:100%}
.actions{display:flex;gap:8px}
.inline{display:flex;align-items:flex-end;gap:8px;flex-wrap:wrap;margin:6px 0 10px}
table{border-collapse:collapse;width:100%;font-size:13px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{background:#eef2f6;font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:var(--ink2);white-space:nowrap}
.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:3px}
pre{background:#0f2738;color:#e6eef5;padding:12px;border-radius:3px;font-size:12px;line-height:1.45;overflow:auto;margin:6px 0 0}
pre.scroll{max-height:360px}
details{margin-top:8px}
summary{cursor:pointer;font-size:13px;color:var(--navy2);font-weight:600;margin-bottom:4px}
.kernel-block{border-top:1px solid var(--line);padding-top:12px;margin-top:12px}
.kernel-block:first-of-type{border-top:none;margin-top:8px;padding-top:0}
.foot{padding:14px 22px 28px;color:#5d7387;font-size:12px;max-width:1280px}
`;
