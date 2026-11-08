/**
 * Command center: discover the platform's capabilities from the live roster,
 * create one record against the selected capability's real POST route, and
 * list the caller's records through GET /v1/{capability}. The authority label
 * returned by the route is shown beside every answer, and no record is shown
 * from a response that refused.
 */
import { useCallback, useEffect, useState } from "react";

export type FieldSpec = {
  name: string;
  type: string;
  required: boolean;
  allowed_values?: string[];
};

export type Capability = {
  id: string;
  title: string;
  fields: FieldSpec[];
  authority: string;
};

export type Answer = { ok?: boolean; authority?: string; items?: Record<string, unknown>[]; error?: string };

export async function request(path: string, init?: RequestInit): Promise<{ status: number; body: Answer }> {
  const token = typeof sessionStorage === "undefined" ? "" : sessionStorage.getItem("platformToken") || "";
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers.Authorization = "Bearer " + token;
  const response = await fetch(path, {
    credentials: "same-origin",
    headers,
    ...init,
  });
  return { status: response.status, body: (await response.json()) as Answer };
}

export default function CommandCenter() {
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [current, setCurrent] = useState<Capability | null>(null);
  const [records, setRecords] = useState<Record<string, unknown>[]>([]);
  const [answer, setAnswer] = useState<Answer>({});
  const [values, setValues] = useState<Record<string, string>>({});

  useEffect(() => {
    request("/v1/capabilities").then(({ body }) => {
      const items = (body.items || []) as unknown as Capability[];
      setCapabilities(items);
      setCurrent(items[0] || null);
    });
  }, []);

  const refresh = useCallback(async () => {
    if (!current) return;
    const { body } = await request("/v1/" + encodeURIComponent(current.id));
    setRecords(body.items || []);
    setAnswer(body);
  }, [current]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  async function createRecord() {
    if (!current) return;
    const payload: Record<string, unknown> = {};
    for (const field of current.fields) {
      const raw = values[field.name];
      if (raw === undefined || raw === "") continue;
      payload[field.name] = field.type === "int" || field.type === "float" ? Number(raw) : raw;
    }
    const { body } = await request("/v1/" + encodeURIComponent(current.id), {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setAnswer(body);
    await refresh();
  }

  return (
    <section data-screen="command_center">
      <h2>Command center</h2>
      <select value={current?.id || ""} onChange={(event) => setCurrent(capabilities.find((c) => c.id === event.target.value) || null)}>
        {capabilities.map((capability) => <option key={capability.id} value={capability.id}>{capability.title}</option>)}
      </select>
      {current?.fields.map((field) => (
        <label key={field.name}>
          {field.name}{field.required ? " *" : ""}
          <input value={values[field.name] || ""} onChange={(event) => setValues({ ...values, [field.name]: event.target.value })} />
        </label>
      ))}
      <button onClick={createRecord}>Create record</button>
      <table><tbody>
        {records.map((record, index) => (
          <tr key={index}><td>{String(record.id ?? "")}</td><td>{String(record.reference ?? "")}</td><td>{String(record.status ?? "")}</td></tr>
        ))}
      </tbody></table>
      <p>Authority: {answer.authority || "unlabelled"}</p>
    </section>
  );
}
