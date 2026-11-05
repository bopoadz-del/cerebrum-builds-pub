import { useEffect, useMemo, useState } from "react";

/**
 * Harbourline Civil Works — contracts administration console.
 *
 * One API: every action calls the live /v1 routes. The token is held in
 * sessionStorage and sent as a Bearer header; nothing is mocked.
 */

type Field = {
  name: string;
  type: string;
  required?: boolean;
  allowed_values?: string[];
  min?: number;
  max?: number;
  format?: string;
};

type Capability = {
  id: string;
  title: string;
  summary: string;
  entity: string;
  blocks: string[];
  fields: Field[];
};

type RecordRow = Record<string, unknown> & { id?: number; reference?: string; status?: string };

const TOKEN_KEY = "harbourline.platformToken";

function authHeaders(token: string): Record<string, string> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

function defaultFor(field: Field): string {
  if (field.allowed_values?.length) return field.allowed_values[0];
  if (field.type === "date") return new Date().toISOString().slice(0, 10);
  if (field.type === "int" || field.type === "float") return field.min !== undefined ? String(field.min) : "0";
  return "";
}

export default function App() {
  const [token, setToken] = useState<string>(() => sessionStorage.getItem(TOKEN_KEY) ?? "");
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [rows, setRows] = useState<RecordRow[]>([]);
  const [response, setResponse] = useState<string>("{}");
  const [authority, setAuthority] = useState<string>("layer 1 certified");
  const [busy, setBusy] = useState(false);

  const capability = useMemo(
    () => capabilities.find((item) => item.id === selected),
    [capabilities, selected],
  );

  async function api(path: string, init?: RequestInit) {
    setBusy(true);
    try {
      const resp = await fetch(path, { ...init, headers: authHeaders(token) });
      const body = await resp.json().catch(() => ({ ok: false, error: "non-JSON response" }));
      setResponse(JSON.stringify({ status: resp.status, body }, null, 2));
      // Every answer is labelled with the precedence layer that produced it;
      // an unlabelled answer is shown as such rather than silently trusted.
      setAuthority(typeof body?.authority === "string" && body.authority ? body.authority : "unlabelled");
      return { status: resp.status, body };
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!token) return;
    api("/v1/capabilities").then(({ body }) => {
      const items: Capability[] = body.items ?? [];
      setCapabilities(items);
      setSelected((current) => current || items[0]?.id || "");
    });
  }, [token]);

  useEffect(() => {
    if (!capability) return;
    const next: Record<string, string> = {};
    for (const field of capability.fields) next[field.name] = defaultFor(field);
    setValues(next);
  }, [capability?.id]);

  async function refresh() {
    if (!capability) return;
    const { body } = await api(`/v1/${encodeURIComponent(capability.id)}`);
    setRows((body.items ?? []) as RecordRow[]);
  }

  useEffect(() => {
    refresh();
  }, [capability?.id]);

  async function submit() {
    if (!capability) return;
    const payload: Record<string, unknown> = {};
    for (const field of capability.fields) {
      const raw = values[field.name];
      if (raw === undefined || raw === "") continue;
      payload[field.name] = field.type === "int" || field.type === "float" ? Number(raw) : raw;
    }
    await api(`/v1/${encodeURIComponent(capability.id)}`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
    await refresh();
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="bg-slate-900 px-6 py-4 text-white">
        <h1 className="text-xl font-semibold">Harbourline Civil Works — contracts administration</h1>
        <p className="text-sm text-slate-300">
          Interim payment certificates · delay damages · QA/ITP · controlled documents.
        </p>
      </header>

      <main className="mx-auto grid max-w-6xl gap-4 px-6 py-6 lg:grid-cols-[22rem_1fr]">
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Platform token</h2>
          <input
            type="password"
            value={token}
            placeholder="PLATFORM_TOKEN"
            className="w-full rounded border border-slate-300 px-3 py-2"
            onChange={(event) => {
              sessionStorage.setItem(TOKEN_KEY, event.target.value);
              setToken(event.target.value);
            }}
          />

          <h2 className="mb-2 mt-6 text-xs font-semibold uppercase tracking-wide text-slate-500">New record</h2>
          <select
            value={selected}
            className="w-full rounded border border-slate-300 px-3 py-2"
            onChange={(event) => setSelected(event.target.value)}
          >
            {capabilities.map((item) => (
              <option key={item.id} value={item.id}>
                {item.title}
              </option>
            ))}
          </select>

          {capability?.fields.map((field) => (
            <label key={field.name} className="mt-3 block text-xs text-slate-500">
              {field.name}
              {field.required ? " *" : ""}
              {field.allowed_values?.length ? (
                <select
                  value={values[field.name] ?? ""}
                  className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm text-slate-900"
                  onChange={(event) => setValues({ ...values, [field.name]: event.target.value })}
                >
                  {field.allowed_values.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              ) : (
                <input
                  type={field.type === "date" ? "date" : field.type === "int" || field.type === "float" ? "number" : "text"}
                  value={values[field.name] ?? ""}
                  className="mt-1 w-full rounded border border-slate-300 px-3 py-2 text-sm text-slate-900"
                  onChange={(event) => setValues({ ...values, [field.name]: event.target.value })}
                />
              )}
            </label>
          ))}

          <button
            type="button"
            disabled={busy || !capability}
            className="mt-4 w-full rounded bg-sky-800 px-4 py-2 text-white disabled:opacity-50"
            onClick={submit}
          >
            POST /v1/{capability?.id ?? "capability"}
          </button>
          {capability?.summary ? <p className="mt-3 text-xs text-slate-500">{capability.summary}</p> : null}
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">
              Register ({rows.length})
            </h2>
            <button type="button" className="rounded bg-slate-200 px-3 py-1 text-sm" onClick={refresh}>
              Refresh
            </button>
          </div>
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-500">
              <tr>
                <th className="border-b border-slate-200 py-2">id</th>
                <th className="border-b border-slate-200 py-2">reference</th>
                <th className="border-b border-slate-200 py-2">status</th>
                <th className="border-b border-slate-200 py-2">authority</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={String(row.id)}>
                  <td className="border-b border-slate-100 py-2">{String(row.id ?? "")}</td>
                  <td className="border-b border-slate-100 py-2">{String(row.reference ?? "")}</td>
                  <td className="border-b border-slate-100 py-2">{String(row.status ?? "")}</td>
                  <td className="border-b border-slate-100 py-2">{String(row.authority ?? authority)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="mb-2 mt-6 flex items-center justify-between">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-slate-500">Last response</h2>
            <span className="rounded-full bg-slate-200 px-2 py-0.5 text-xs text-slate-700" data-testid="authority">
              {authority}
            </span>
          </div>
          <pre className="max-h-72 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">{response}</pre>
        </section>
      </main>
    </div>
  );
}
