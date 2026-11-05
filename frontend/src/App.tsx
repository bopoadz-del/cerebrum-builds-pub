/**
 * Console source for the Harbourline contracts platform.
 *
 * The shipped artifact is app/static/index.html: it discovers capabilities from
 * GET /v1/capabilities, creates records through POST /v1/{capability}, lists
 * them through GET /v1/{capability}, and renders the authority label on every
 * answer. This component mirrors that behaviour for teams that rebuild it.
 */
import { useEffect, useMemo, useState } from "react";

type Authority = { layer: number; label: string; source: string; detail?: string };
type Capability = { id: string; title: string; description: string; blocks: string[] };
type RecordRow = { id: number; reference?: string; status?: string; [key: string]: unknown };

const TOKEN_KEY = "harbourline.token";

export default function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem(TOKEN_KEY) || "");
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [active, setActive] = useState<string>("");
  const [reference, setReference] = useState("IPC-001");
  const [status, setStatus] = useState("open");
  const [records, setRecords] = useState<RecordRow[]>([]);
  const [authority, setAuthority] = useState<Authority | null>(null);
  const [error, setError] = useState("");

  const headers = useMemo(() => {
    const value: Record<string, string> = { "Content-Type": "application/json" };
    if (token) value.Authorization = `Bearer ${token}`;
    return value;
  }, [token]);

  useEffect(() => {
    sessionStorage.setItem(TOKEN_KEY, token);
  }, [token]);

  useEffect(() => {
    fetch("/v1/capabilities", { headers })
      .then((response) => response.json())
      .then((body) => {
        const items: Capability[] = Array.isArray(body.items) ? body.items : [];
        setCapabilities(items);
        if (items.length && !active) setActive(items[0].id);
      })
      .catch((err) => setError(String(err)));
  }, [headers, active]);

  useEffect(() => {
    if (!active) return;
    fetch(`/v1/${active}`, { headers })
      .then((response) => response.json())
      .then((body) => {
        setRecords(Array.isArray(body.items) ? body.items : []);
        setAuthority(body.authority || null);
      })
      .catch((err) => setError(String(err)));
  }, [active, headers]);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    setError("");
    const response = await fetch(`/v1/${active}`, {
      method: "POST",
      headers,
      body: JSON.stringify({ reference, status }),
    });
    const body = await response.json();
    if (!response.ok || body.ok === false) {
      setError(body.error || body.detail?.error || `HTTP ${response.status}`);
      return;
    }
    setAuthority(body.authority || null);
    const listed = await fetch(`/v1/${active}`, { headers }).then((r) => r.json());
    setRecords(Array.isArray(listed.items) ? listed.items : []);
  }

  return (
    <main style={{ fontFamily: "system-ui, sans-serif", maxWidth: 1000, margin: "24px auto" }}>
      <h1>Harbourline Civil Works — Contracts Administration</h1>
      <section>
        <label>Bearer token <input type="password" value={token} onChange={(e) => setToken(e.target.value)} /></label>
      </section>
      <nav>
        {capabilities.map((cap) => (
          <button key={cap.id} onClick={() => setActive(cap.id)} disabled={active === cap.id}>
            {cap.title}
          </button>
        ))}
      </nav>
      <form onSubmit={create}>
        <label>Reference <input value={reference} onChange={(e) => setReference(e.target.value)} required /></label>
        <label>Status
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="open">open</option>
            <option value="in_progress">in_progress</option>
            <option value="closed">closed</option>
          </select>
        </label>
        <button type="submit">Create record</button>
      </form>
      {error && <p role="alert" style={{ color: "#a52121" }}>{error}</p>}
      {authority && (
        <p>
          <span className={`authority layer-${authority.layer}`}>
            authority: {authority.label} · {authority.detail || authority.source}
          </span>
        </p>
      )}
      <table>
        <thead><tr><th>id</th><th>reference</th><th>status</th></tr></thead>
        <tbody>
          {records.map((row) => (
            <tr key={String(row.id)}>
              <td>{row.id}</td>
              <td>{row.reference}</td>
              <td>{row.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
