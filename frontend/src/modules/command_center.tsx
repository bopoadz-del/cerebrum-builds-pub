/**
 * Command centre -- the working surface.
 *
 * Discovers the roster from GET /v1/capabilities, draws a form from each
 * capability's declared FIELDS + CONSTRAINTS, POSTs the record to that
 * capability's route, lists it back, and runs the operations dashboard. It
 * never writes a field contract of its own: a vocabulary or bound shown here
 * is the one the spec declared, and the answer's authority label is the one
 * the platform sent.
 */

import { useEffect, useMemo, useState } from "react";

type Rule = {
  allowed_values?: Array<string | number>;
  required?: boolean;
  min?: number;
  max?: number;
  format?: string;
};

type Capability = {
  capability_id: string;
  block_ids: string[];
  fields: string[];
  field_types?: Record<string, string>;
  constraints?: Record<string, Rule>;
};

type Authority = { layer?: number; name?: string; source?: string };

type Answer = {
  ok?: boolean;
  id?: number | null;
  error?: string;
  authority?: Authority;
  result?: Record<string, unknown>;
  items?: Array<Record<string, unknown>>;
};

type Call = (path: string, init?: RequestInit) => Promise<Answer>;

function initialValue(name: string, rule: Rule, kind: string): unknown {
  if (rule.allowed_values && rule.allowed_values.length) return rule.allowed_values[0];
  if (rule.format === "date") return new Date().toISOString().slice(0, 10);
  if (rule.format === "datetime") return new Date().toISOString().slice(0, 19);
  if (rule.format === "email") return "guest@example.com";
  if (kind === "bool") return false;
  if (kind === "int" || kind === "float") return rule.min ?? 0;
  return "";
}

export function CommandCenter({ capabilities, call }: { capabilities: Capability[]; call: Call }) {
  const [active, setActive] = useState<Capability | null>(null);
  const [values, setValues] = useState<Record<string, unknown>>({});
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [records, setRecords] = useState<Array<Record<string, unknown>>>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    if (!active && capabilities.length) select(capabilities[0]);
  }, [capabilities, active]);

  function select(capability: Capability) {
    const next: Record<string, unknown> = {};
    capability.fields.forEach((name) => {
      next[name] = initialValue(
        name,
        (capability.constraints || {})[name] || {},
        (capability.field_types || {})[name] || "str",
      );
    });
    setActive(capability);
    setValues(next);
    setRecords([]);
    setAnswer(null);
    setMessage("");
  }

  const authority = useMemo(() => answer?.authority || null, [answer]);

  async function save() {
    if (!active) return;
    setBusy(true);
    setMessage("Saving…");
    try {
      const body = await call(`/v1/${active.capability_id}`, {
        method: "POST",
        body: JSON.stringify(values),
      });
      setAnswer(body);
      if (body.ok === false) {
        setMessage(body.error || "Refused.");
      } else {
        setMessage(`Stored record ${body.id == null ? "" : "#" + body.id}.`);
        await load();
      }
    } finally {
      setBusy(false);
    }
  }

  async function load() {
    if (!active) return;
    const body = await call(`/v1/${active.capability_id}?limit=50`);
    setAnswer(body);
    setRecords(Array.isArray(body.items) ? body.items : []);
    setMessage(body.ok === false ? body.error || "Refused." : "");
  }

  async function runDashboard() {
    setBusy(true);
    try {
      const body = await call("/v1/operational_dashboard", {
        method: "POST",
        body: JSON.stringify({ reference: "console", status: "open" }),
      });
      setAnswer(body);
      setMessage(body.ok === false ? body.error || "Refused." : "Dashboard rendered.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="command-center">
      <aside>
        <h2>Capabilities</h2>
        <ul>
          {capabilities.map((capability) => (
            <li
              key={capability.capability_id}
              className={active?.capability_id === capability.capability_id ? "active" : ""}
              onClick={() => select(capability)}
            >
              <strong>{capability.capability_id}</strong>
              <small>{capability.block_ids.join(", ") || "no blocks"}</small>
            </li>
          ))}
        </ul>
      </aside>

      <article>
        <h2>{active?.capability_id || "Connect to load the roster"}</h2>
        {authority && (
          <p className="authority">
            Authority: layer {authority.layer} &middot; {authority.name} &mdash; {authority.source}
          </p>
        )}
        {active && (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void save();
            }}
          >
            {active.fields.map((name) => {
              const rule = (active.constraints || {})[name] || {};
              const kind = (active.field_types || {})[name] || "str";
              const value = values[name];
              return (
                <label key={name}>
                  {name}
                  {(rule.required && " *") || ""}
                  {rule.allowed_values && rule.allowed_values.length ? (
                    <select
                      value={String(value ?? "")}
                      onChange={(event) =>
                        setValues({ ...values, [name]: event.target.value })
                      }
                    >
                      {rule.allowed_values.map((option) => (
                        <option key={String(option)} value={String(option)}>
                          {String(option)}
                        </option>
                      ))}
                    </select>
                  ) : kind === "bool" ? (
                    <input
                      type="checkbox"
                      checked={Boolean(value)}
                      onChange={(event) =>
                        setValues({ ...values, [name]: event.target.checked })
                      }
                    />
                  ) : (
                    <input
                      type={kind === "int" || kind === "float" ? "number" : "text"}
                      min={rule.min}
                      max={rule.max}
                      value={String(value ?? "")}
                      onChange={(event) =>
                        setValues({
                          ...values,
                          [name]:
                            kind === "int" || kind === "float"
                              ? Number(event.target.value)
                              : event.target.value,
                        })
                      }
                    />
                  )}
                </label>
              );
            })}
            <div className="row">
              <button type="submit" disabled={busy}>
                Save record
              </button>
              <button type="button" disabled={busy} onClick={() => void load()}>
                Load records
              </button>
              <button type="button" disabled={busy} onClick={() => void runDashboard()}>
                Run operations dashboard
              </button>
            </div>
          </form>
        )}
        <p className={answer?.ok === false ? "status error" : "status"}>{message}</p>
        {records.length > 0 && (
          <table>
            <thead>
              <tr>
                {Object.keys(records[0]).slice(0, 7).map((key) => (
                  <th key={key}>{key}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {records.map((row, index) => (
                <tr key={String(row.id ?? index)}>
                  {Object.keys(records[0]).slice(0, 7).map((key) => (
                    <td key={key}>{String(row[key] ?? "")}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
        {answer && <pre>{JSON.stringify(answer, null, 2)}</pre>}
      </article>
    </section>
  );
}
