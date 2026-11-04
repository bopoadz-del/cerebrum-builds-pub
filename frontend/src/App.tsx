/**
 * The operator console, as source.
 *
 * The platform serves the compiled console from app/static/index.html; this is
 * the component it is built from. It discovers the capabilities from the API,
 * builds a form from each capability's declared FIELDS, posts to the real
 * /v1/<capability> route, shows the answer with its authority label and lists
 * the records the caller's tenant can see. Nothing is hardcoded per capability:
 * the roster and the fields come from the server.
 */
import { useCallback, useEffect, useMemo, useState } from 'react';

type FieldSpec = {
  name: string;
  type: string;
  required?: boolean;
  allowed_values?: unknown[];
  min?: number;
  max?: number;
};

type Capability = {
  id: string;
  title: string;
  fields: FieldSpec[];
  servable: boolean;
  placeholder_connectors?: string[];
  stages?: string[];
};

const API = '';

function useToken() {
  const [token, setToken] = useState('');
  return { token, setToken };
}

async function call(path: string, token: string, init: RequestInit = {}) {
  const resp = await fetch(API + path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  });
  let body: any = null;
  try {
    body = await resp.json();
  } catch {
    body = { ok: false, error: 'non-JSON answer' };
  }
  return { status: resp.status, body };
}

export default function App() {
  const { token, setToken } = useToken();
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [current, setCurrent] = useState<Capability | null>(null);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [answer, setAnswer] = useState<any>(null);
  const [records, setRecords] = useState<any[]>([]);

  const load = useCallback(async () => {
    const resp = await call('/v1/capabilities', token);
    if (resp.status === 200) setCapabilities(resp.body.items || []);
  }, [token]);

  useEffect(() => {
    if (token) load();
  }, [token, load]);

  const authority = useMemo(() => {
    const label = answer?.authority ?? answer?.result?.authority;
    return label ? String(label) : '';
  }, [answer]);

  function select(cap: Capability) {
    setCurrent(cap);
    setValues(Object.fromEntries(cap.fields.map((f) => [f.name, f.allowed_values?.[0] ?? ''])));
  }

  async function run() {
    if (!current) return;
    const payload = { ...values, reference: values.reference || `console-${Date.now()}` };
    const resp = await call(`/v1/${current.id}`, token, { method: 'POST', body: JSON.stringify(payload) });
    setAnswer({ status: resp.status, ...resp.body });
    const listed = await call(`/v1/${current.id}`, token);
    if (listed.status === 200) setRecords(listed.body.items || []);
  }

  return (
    <main>
      <h1>Cerebrum Executive Programs</h1>
      <input
        type="password"
        placeholder="platform token"
        value={token}
        onChange={(event) => setToken(event.target.value.trim())}
      />
      <nav>
        {capabilities.map((cap) => (
          <button key={cap.id} onClick={() => select(cap)}>
            {cap.title}
            {cap.servable ? '' : ' (placeholder)'}
          </button>
        ))}
      </nav>
      {current && (
        <section>
          <h2>{current.title}</h2>
          {current.fields.map((field) => (
            <label key={field.name}>
              {field.name}
              {field.required ? ' *' : ''}
              <input
                value={String(values[field.name] ?? '')}
                onChange={(event) =>
                  setValues({ ...values, [field.name]: event.target.value })
                }
              />
            </label>
          ))}
          <button onClick={run}>Run</button>
        </section>
      )}
      {answer && (
        <section>
          {authority && <p className="authority">authority: {authority}</p>}
          <pre>{JSON.stringify(answer, null, 2)}</pre>
        </section>
      )}
      <section>
        <h2>Records</h2>
        <pre>{JSON.stringify(records, null, 2)}</pre>
      </section>
    </main>
  );
}
