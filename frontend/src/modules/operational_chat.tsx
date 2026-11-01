/**
 * Operational chat -- a deterministic desk for the factory's own records.
 *
 * There is no language model in this platform (offline posture). The chat is
 * an intent router over the customer's declared vocabulary: the operator types
 * a subject ("collections", "batches", "orders", "invoices", "staff",
 * "dashboard") and the desk calls the matching GET route, then shows the
 * records and the authority layer that answered. A subject it does not know
 * is refused by name, never answered from a guess.
 */

import { useMemo, useState } from "react";

type Authority = { layer?: number; name?: string; source?: string };

type Answer = {
  ok?: boolean;
  error?: string;
  authority?: Authority;
  items?: Array<Record<string, unknown>>;
};

type Call = (path: string, init?: RequestInit) => Promise<Answer>;

const SUBJECTS: Record<string, string> = {
  collections: "collection_planning_tracking",
  pickups: "collection_planning_tracking",
  batches: "batch_production_tracking",
  compost: "batch_production_tracking",
  orders: "catalog_pricing_orders",
  catalog: "catalog_pricing_orders",
  invoices: "invoicing_tunisian_vat",
  vat: "invoicing_tunisian_vat",
  staff: "internal_staff_access",
  access: "internal_staff_access",
  dashboard: "operational_dashboard",
};

export function OperationalChat({ capabilities, call }: { capabilities: any[]; call: Call }) {
  const known = useMemo(
    () => new Set(capabilities.map((item: { capability_id: string }) => item.capability_id)),
    [capabilities],
  );
  const [text, setText] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [note, setNote] = useState("");

  async function ask() {
    const words = text.toLowerCase().match(/[a-z_]+/g) || [];
    const subject = words.find((word: string) => SUBJECTS[word]);
    if (!subject) {
      setNote(
        "I can answer for: " +
          Object.keys(SUBJECTS).sort().join(", ") +
          ". No model is configured, so an unknown subject is refused.",
      );
      setAnswer(null);
      return;
    }
    const capability = SUBJECTS[subject];
    if (known.size && !known.has(capability)) {
      setNote(`${capability} is not in this deployment's roster.`);
      return;
    }
    const body = await call(`/v1/${capability}?limit=50`);
    setAnswer(body);
    setNote(
      body.ok === false
        ? body.error || "Refused."
        : `${capability}: ${body.items?.length ?? 0} record(s) for this tenant.`,
    );
  }

  return (
    <section className="operational-chat">
      <h2>Operational chat</h2>
      <p className="hint">
        Deterministic lookup, not a language model: the desk maps your subject to the
        capability route that owns it and shows the answer with its authority layer.
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void ask();
        }}
      >
        <input
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="collections, batches, orders, invoices, staff, dashboard"
        />
        <button type="submit">Ask the desk</button>
      </form>
      <p className={answer?.ok === false ? "status error" : "status"}>{note}</p>
      {answer?.authority && (
        <p className="authority">
          Answered by layer {answer.authority.layer} &middot; {answer.authority.name} &mdash;{" "}
          {answer.authority.source}
        </p>
      )}
      {answer?.items && answer.items.length > 0 && (
        <table>
          <thead>
            <tr>
              {Object.keys(answer.items[0]).slice(0, 6).map((key) => (
                <th key={key}>{key}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {answer.items.map((row, index) => (
              <tr key={String(row.id ?? index)}>
                {Object.keys(answer.items?.[0] || {}).slice(0, 6).map((key) => (
                  <td key={key}>{String(row[key] ?? "")}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
