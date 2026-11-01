/**
 * Coffee-compost factory operations console -- React/TypeScript source.
 *
 * This is the readable source of the console the platform serves at "/"
 * (rendered into app/static/index.html by frontend/build.py). It makes
 * exactly the calls the served page makes, against this platform's own HTTP
 * surface:
 *
 *   GET  /v1/capabilities   the roster, each capability's fields and rules
 *   POST /v1/<capability>   record a collection, batch, order, invoice, staff
 *                           member or dashboard reading
 *   GET  /v1/<capability>   read the tenant's records back
 *   GET  /health            fail-closed readiness
 *
 * Three rules the shell keeps:
 *
 *  1. No field contract is written here. Forms are drawn from the fields and
 *     constraints GET /v1/capabilities answers with, so the console cannot
 *     drift from the platform's declaration.
 *  2. Every answer is labelled with the authority object the platform sent,
 *     never with a label invented here.
 *  3. A refusal is rendered as a refusal.
 *
 * The operator's PLATFORM_TOKEN is typed into the field and kept in this
 * browser's storage; it is never bundled here. Every fetch is same-origin.
 */

import { useCallback, useEffect, useMemo, useState } from "react";

import { CommandCenter } from "./modules/command_center";
import { OperationalChat } from "./modules/operational_chat";
import { ResidentEngineer } from "./modules/resident_engineer";

export type FieldRule = {
  allowed_values?: Array<string | number>;
  required?: boolean;
  min?: number;
  max?: number;
  format?: string;
  approval?: boolean;
};

export type Capability = {
  capability_id: string;
  block_ids: string[];
  fields: string[];
  field_types?: Record<string, string>;
  constraints?: Record<string, FieldRule>;
  authority?: Authority;
};

export type Authority = {
  layer?: number;
  name?: string;
  source?: string;
  schema?: string;
};

type Tab = "command_center" | "operational_chat" | "resident_engineer";

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "command_center", label: "Command centre" },
  { id: "operational_chat", label: "Operational chat" },
  { id: "resident_engineer", label: "Resident engineer" },
];

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem("platform_token") || "");
  const [tab, setTab] = useState<Tab>("command_center");
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [rosterAuthority, setRosterAuthority] = useState<Authority | null>(null);
  const [error, setError] = useState("");

  const headers = useMemo(
    () => ({ "Content-Type": "application/json", Authorization: `Bearer ${token}` }),
    [token],
  );

  const call = useCallback(
    async (path: string, init?: RequestInit) => {
      const resp = await fetch(path, { ...(init || {}), headers });
      const body = await resp.json().catch(() => ({ ok: false, error: `HTTP ${resp.status}` }));
      if (resp.status === 401) throw new Error("401: enter a valid PLATFORM_TOKEN");
      return body;
    },
    [headers],
  );

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    call("/v1/capabilities")
      .then((body) => {
        if (cancelled) return;
        setCapabilities(Array.isArray(body.items) ? body.items : []);
        setRosterAuthority(body.authority || null);
        setError("");
      })
      .catch((err: Error) => !cancelled && setError(err.message));
    return () => {
      cancelled = true;
    };
  }, [call, token]);

  function connect(value: string) {
    localStorage.setItem("platform_token", value);
    setToken(value.trim());
  }

  return (
    <main className="console">
      <header>
        <h1>Coffee-compost factory operations</h1>
        <label>
          Platform bearer token
          <input
            id="token"
            type="password"
            defaultValue={token}
            onBlur={(event) => connect(event.target.value)}
            placeholder="PLATFORM_TOKEN"
          />
        </label>
      </header>

      {error && <p className="error">{error}</p>}

      <nav>
        {TABS.map((item) => (
          <button
            key={item.id}
            className={tab === item.id ? "active" : ""}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </nav>

      {rosterAuthority && (
        <p className="authority">
          Roster authority: layer {rosterAuthority.layer} &middot; {rosterAuthority.name}
        </p>
      )}

      {tab === "command_center" && (
        <CommandCenter capabilities={capabilities} call={call} />
      )}
      {tab === "operational_chat" && (
        <OperationalChat capabilities={capabilities} call={call} />
      )}
      {tab === "resident_engineer" && <ResidentEngineer call={call} />}
    </main>
  );
}
