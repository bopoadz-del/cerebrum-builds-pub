/**
 * Resident engineer -- read-only diagnostics for whoever runs the platform.
 *
 * It asks the platform's own instruments rather than describing them:
 * GET /health (fail-closed readiness), GET /v1/capabilities (the roster and
 * its block bindings), GET /v1/authority (the precedence.v1 ladder) and
 * GET /v1/provenance (what was cloned at which commit). Nothing here writes a
 * record, so an operator can inspect a live factory without touching its data.
 */

import { useState } from "react";

type Answer = { ok?: boolean; status?: string; error?: string; [key: string]: unknown };
type Call = (path: string, init?: RequestInit) => Promise<Answer>;

const CHECKS: Array<{ path: string; label: string }> = [
  { path: "/health", label: "Health (process, disk, database, migrations)" },
  { path: "/v1/capabilities", label: "Capability roster and block bindings" },
  { path: "/v1/authority", label: "Authority ladder (precedence.v1)" },
  { path: "/v1/provenance", label: "Build provenance and clone register" },
];

export function ResidentEngineer({ call }: { call: Call }) {
  const [answers, setAnswers] = useState<Record<string, Answer>>({});
  const [busy, setBusy] = useState("");

  async function probe(path: string, label: string) {
    setBusy(label);
    try {
      const body = await call(path);
      setAnswers((current) => ({ ...current, [path]: body }));
    } catch (error) {
      setAnswers((current) => ({
        ...current,
        [path]: { ok: false, error: (error as Error).message },
      }));
    } finally {
      setBusy("");
    }
  }

  async function probeAll() {
    for (const check of CHECKS) {
      await probe(check.path, check.label);
    }
  }

  return (
    <section className="resident-engineer">
      <h2>Resident engineer</h2>
      <p className="hint">
        Read-only diagnostics. The platform is offline and runs its blocks in-process;
        these are the same surfaces an operator or a monitoring probe uses.
      </p>
      <button onClick={() => void probeAll()} disabled={Boolean(busy)}>
        {busy ? `Checking ${busy}…` : "Run every check"}
      </button>
      <div className="checks">
        {CHECKS.map((check) => {
          const answer = answers[check.path];
          const healthy = answer ? answer.ok !== false && answer.status !== "not_ready" : null;
          return (
            <article key={check.path} className={healthy === false ? "check failed" : "check"}>
              <header>
                <strong>{check.label}</strong>
                <code>{check.path}</code>
                <button onClick={() => void probe(check.path, check.label)} disabled={Boolean(busy)}>
                  Check
                </button>
              </header>
              {answer ? (
                <pre>{JSON.stringify(answer, null, 2)}</pre>
              ) : (
                <p className="hint">Not checked in this session.</p>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
