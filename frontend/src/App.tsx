/**
 * Source for the Harbourline console.
 *
 * The deployed console is app/static/index.html (plain HTML/JS, served by
 * app.main at "/") so the runtime image needs no node toolchain. This file
 * is the same screen kept in the frontend source tree: it discovers the
 * capabilities from /v1/capabilities, posts a record to a real capability
 * route, asks the contract a grounded question, and lists the register.
 */
import { useEffect, useMemo, useState } from "react";

// Every answer names the precedence layer that produced it.
function withAuthority(status: number, body: any) {
  const layer = body?.result?.authority ?? body?.authority ?? "";
  return (layer ? `authority: ${layer}\n\n` : "") + JSON.stringify({ status, body }, null, 2);
}

type Capability = { id: string; title: string; summary: string; fields: string[] };

export default function App() {
  const [token, setToken] = useState(sessionStorage.getItem("token") ?? "");
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [capability, setCapability] = useState("");
  const [answer, setAnswer] = useState("");

  const headers = useMemo(
    () => ({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" }),
    [token],
  );

  useEffect(() => {
    if (!token) return;
    fetch("/v1/capabilities", { headers })
      .then((response) => response.json())
      .then((body) => {
        setCapabilities(body.items ?? []);
        setCapability((current) => current || body.items?.[0]?.id || "");
      })
      .catch(() => setAnswer("capabilities unavailable"));
  }, [token, headers]);

  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const payload: Record<string, string> = {};
    form.forEach((value, key) => {
      if (typeof value === "string" && value !== "") payload[key] = value;
    });
    const response = await fetch(`/v1/${capability}`, {
      method: "POST",
      headers,
      body: JSON.stringify(payload),
    });
    setAnswer(withAuthority(response.status, await response.json()));
  };

  const ask = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const question = String(new FormData(event.currentTarget).get("question") ?? "");
    const response = await fetch("/v1/contract_clause_grounding", {
      method: "POST",
      headers,
      body: JSON.stringify({ reference: `console-${Date.now()}`, status: "open", question }),
    });
    setAnswer(withAuthority(response.status, await response.json()));
  };

  return (
    <main>
      <section data-module="command_center">
      <h1>Harbourline Contracts Administration</h1>
      <input
        type="password"
        placeholder="PLATFORM_TOKEN"
        value={token}
        onChange={(event) => {
          setToken(event.target.value);
          sessionStorage.setItem("token", event.target.value);
        }}
      />
      <ul>
        {capabilities.map((item) => (
          <li key={item.id} onClick={() => setCapability(item.id)}>
            <strong>{item.title}</strong> — {item.summary}
          </li>
        ))}
      </ul>
      </section>
      <section data-module="resident_engineer">
      <form onSubmit={submit}>
        <select value={capability} onChange={(event) => setCapability(event.target.value)}>
          {capabilities.map((item) => (
            <option key={item.id} value={item.id}>{item.id}</option>
          ))}
        </select>
        {(capabilities.find((item) => item.id === capability)?.fields ?? []).map((name) => (
          <label key={name}>
            {name}
            <input name={name} />
          </label>
        ))}
        <button type="submit">Submit record</button>
      </form>
      </section>
      <section data-module="operational_chat">
      <form onSubmit={ask}>
        <input name="question" placeholder="What is the delay damages rate?" />
        <button type="submit">Ask</button>
      </form>
      </section>
      <pre>{answer}</pre>
    </main>
  );
}
