/**
 * Manager console source.
 *
 * The deployed console is app/static/index.html (served by app/main.py), so
 * the pilot image needs no node build. This module is the same screen as a
 * React component for teams that embed the console in a larger frontend: it
 * discovers capabilities from the API and drives the live POST/GET routes.
 */
import { useEffect, useMemo, useState } from "react";

type Capability = { id: string; name: string; entity: string; blocks: string[] };

const API = "";

export default function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem("manager_token") || "");
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Record<string, unknown> | null>(null);
  const [dashboard, setDashboard] = useState<Record<string, unknown> | null>(null);

  const headers = useMemo(
    () => ({ "Content-Type": "application/json", Authorization: `Bearer ${token}` }),
    [token]
  );

  useEffect(() => {
    if (!token) return;
    sessionStorage.setItem("manager_token", token);
    fetch(`${API}/v1/capabilities`, { headers })
      .then((response) => response.json())
      .then((body) => setCapabilities(body.items || []))
      .catch(() => setCapabilities([]));
  }, [token, headers]);

  async function ask() {
    const response = await fetch(`${API}/v1/document_grounded_qa`, {
      method: "POST",
      headers,
      body: JSON.stringify({ question: question || "summarize the uploaded documents", top_k: 5 }),
    });
    setAnswer(await response.json());
  }

  async function loadDashboard() {
    const response = await fetch(`${API}/v1/manager_dashboard`, {
      method: "POST",
      headers,
      body: JSON.stringify({ plant: "all", include_alerts: true }),
    });
    setDashboard(await response.json());
  }

  const authority = (answer?.authority || (answer?.result as Record<string, unknown>)?.authority) as
    | { layer?: number; label?: string }
    | undefined;

  return (
    <div className="console">
      <header>
        <h1>Plant Manager Console</h1>
        <input
          type="password"
          value={token}
          placeholder="manager token"
          onChange={(event) => setToken(event.target.value.trim())}
        />
      </header>

      <section>
        <h2>Ask the documents</h2>
        <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
        <button onClick={ask}>Ask</button>
        {authority ? (
          <p className="authority">
            Authority: layer {authority.layer} · {authority.label}
          </p>
        ) : null}
        {answer ? <pre>{JSON.stringify(answer, null, 2)}</pre> : null}
      </section>

      <section>
        <h2>Dashboard</h2>
        <button onClick={loadDashboard}>Load dashboard</button>
        {dashboard ? <pre>{JSON.stringify(dashboard, null, 2)}</pre> : null}
      </section>

      <section>
        <h2>Capabilities</h2>
        <ul>
          {capabilities.map((item) => (
            <li key={item.id}>
              <strong>{item.name}</strong> — {item.blocks.join(", ")}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
