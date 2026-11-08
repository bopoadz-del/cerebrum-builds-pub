/**
 * The console source for the Harbourline contracts-administration platform.
 *
 * The deployed console is app/static/index.html (served at GET / by the
 * FastAPI app), which calls the same live routes this component does. This
 * file is the typed source of that screen for teams that build the frontend
 * with their own toolchain; it is not required at runtime.
 */
import React, { useEffect, useState } from "react";

const CAPABILITY_ROUTE = "/v1/capabilities";
const CLAIM_ROUTE = "/v1/progress_claim_management";
const DELAY_ROUTE = "/v1/delay_damages_tracking";
const DASHBOARD_ROUTE = "/v1/commercial_dashboard";

type Capability = { id: string; title: string; blocks: string[]; authority: string };

function headers(token: string): Record<string, string> {
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

export default function App(): React.ReactElement {
  const [token, setToken] = useState("");
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [claims, setClaims] = useState<Record<string, unknown>[]>([]);
  const [delays, setDelays] = useState<Record<string, unknown>[]>([]);
  const [authority, setAuthority] = useState("layer 3 formulas");

  async function refresh(): Promise<void> {
    const [caps, claimList, delayList] = await Promise.all([
      fetch(CAPABILITY_ROUTE, { headers: headers(token) }).then((r) => r.json()),
      fetch(CLAIM_ROUTE, { headers: headers(token) }).then((r) => r.json()),
      fetch(DELAY_ROUTE, { headers: headers(token) }).then((r) => r.json()),
    ]);
    setCapabilities(caps.items || []);
    setClaims(claimList.items || []);
    setDelays(delayList.items || []);
    setAuthority(claimList.authority || delayList.authority || "layer 3 formulas");
  }

  async function createClaim(): Promise<void> {
    const response = await fetch(CLAIM_ROUTE, {
      method: "POST",
      headers: headers(token),
      body: JSON.stringify({ reference: "CLAIM-001", boq_item: "P1", claimed_quantity: 100, retention_pct: 5, status: "open" }),
    });
    const body = await response.json();
    setAuthority(body.authority || authority);
    await refresh();
  }

  async function createDelay(): Promise<void> {
    const response = await fetch(DELAY_ROUTE, {
      method: "POST",
      headers: headers(token),
      body: JSON.stringify({ reference: "DELAY-001", delay_days: 10, status: "open" }),
    });
    const body = await response.json();
    setAuthority(body.authority || authority);
    await refresh();
  }

  async function buildDashboard(): Promise<void> {
    const response = await fetch(DASHBOARD_ROUTE, {
      method: "POST",
      headers: headers(token),
      body: JSON.stringify({ reference: "SNAPSHOT-001", period: "2026-11", status: "open" }),
    });
    const body = await response.json();
    setAuthority(body.authority || authority);
    await refresh();
  }

  useEffect(() => {
    if (token) void refresh();
  }, [token]);

  return (
    <main>
      <h1>Harbourline Civil Works Contracts Administration</h1>
      <label>
        Bearer token
        <input type="password" value={token} onChange={(event) => setToken(event.target.value)} />
      </label>
      <p>authority: {authority}</p>
      <section>
        <h2>Capabilities</h2>
        <ul>
          {capabilities.map((capability) => (
            <li key={capability.id}>
              {capability.title} ({capability.id}) - {capability.authority}
            </li>
          ))}
        </ul>
      </section>
      <section>
        <button onClick={createClaim}>Create progress claim</button>
        <button onClick={createDelay}>Assess delay exposure</button>
        <button onClick={buildDashboard}>Build commercial snapshot</button>
      </section>
      <section>
        <h2>Stored records</h2>
        <p>{claims.length} claim(s), {delays.length} delay assessment(s)</p>
      </section>
    </main>
  );
}
