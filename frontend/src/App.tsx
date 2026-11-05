/**
 * Cerebrum Executive Programs - operator console (React source).
 *
 * The platform serves ONE UI: `app/static/index.html` is the shipped, built
 * console and this component is the same screen in React form. Both drive the
 * live routes (`/v1/capabilities`, `/v1/tracks`, `/v1/formulas`,
 * `/v1/faculty_session`, `/v1/memo_grading`, `/v1/gradebook_and_transcript`,
 * `/v1/reading_and_case_library`, `/v1/rag/ingest`, `/v1/rag/query`) and both
 * show the authority label the API returns.
 */
import { useEffect, useState } from "react";

type Authority = { layer: number; label: string; source?: string };
type Capability = { id: string; entity: string; fields: string[] };

const BASE = "";

function useToken(): [string, (value: string) => void] {
  const [token, setToken] = useState<string>(() => sessionStorage.getItem("platformToken") || "");
  useEffect(() => {
    sessionStorage.setItem("platformToken", token);
  }, [token]);
  return [token, setToken];
}

async function api(token: string, path: string, options: RequestInit = {}) {
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  if (options.body) headers["Content-Type"] = "application/json";
  const resp = await fetch(BASE + path, { ...options, headers });
  const body = await resp.json().catch(() => null);
  return { status: resp.status, body };
}

function AuthorityLine({ body }: { body: any }) {
  const label: Authority | undefined = body?.authority || body?.record?.authority;
  if (!label) return null;
  return (
    <div className="authority">
      authority: layer {label.layer} - {label.label}
      {label.source ? ` (${label.source})` : ""}
    </div>
  );
}

export default function App() {
  const [token, setToken] = useToken();
  const [caps, setCaps] = useState<Capability[]>([]);
  const [tracks, setTracks] = useState<any>(null);
  const [formulas, setFormulas] = useState<any>(null);
  const [session, setSession] = useState<any>(null);
  const [grade, setGrade] = useState<any>(null);
  const [gradebook, setGradebook] = useState<any>(null);
  const [library, setLibrary] = useState<any>(null);

  const [mode, setMode] = useState("lecture");
  const [week, setWeek] = useState(1);
  const [submission, setSubmission] = useState("");
  const [scores, setScores] = useState({ memos: 86, defenses: 82, capstone: 90 });

  useEffect(() => {
    if (!token) return;
    api(token, "/v1/capabilities").then(({ body }) => setCaps(body?.items || []));
    api(token, "/v1/tracks").then(({ body }) => setTracks(body));
    api(token, "/v1/formulas").then(({ body }) => setFormulas(body));
  }, [token]);

  async function openSession() {
    const { body } = await api(token, "/v1/faculty_session", {
      method: "POST",
      body: JSON.stringify({
        reference: `session-${Date.now()}`,
        status: "open",
        mode,
        week,
        learner_email: "learner@example.com",
        message: "Pressure-test my reading of this week's framework.",
      }),
    });
    setSession(body);
  }

  async function gradeMemo() {
    const { body } = await api(token, "/v1/memo_grading", {
      method: "POST",
      body: JSON.stringify({
        reference: `memo-${Date.now()}`,
        status: "open",
        week,
        learner_email: "learner@example.com",
        submission,
      }),
    });
    setGrade(body);
  }

  async function computeGradebook() {
    const { body } = await api(token, "/v1/gradebook_and_transcript", {
      method: "POST",
      body: JSON.stringify({
        reference: `gradebook-${Date.now()}`,
        status: "open",
        term: 1,
        learner_email: "learner@example.com",
        memos_score: scores.memos,
        defenses_score: scores.defenses,
        capstone_score: scores.capstone,
      }),
    });
    setGradebook(body);
  }

  async function readWeek() {
    const { body } = await api(token, "/v1/reading_and_case_library", {
      method: "POST",
      body: JSON.stringify({
        reference: `library-${Date.now()}`,
        status: "open",
        week,
        session_offset: 0,
        learner_email: "learner@example.com",
      }),
    });
    setLibrary(body);
  }

  return (
    <main>
      <header>
        <h1>Cerebrum Executive Programs</h1>
        <input value={token} onChange={(e) => setToken(e.target.value)} placeholder="Bearer token" />
      </header>

      <section>
        <h2>Capabilities</h2>
        <ul>
          {caps.map((cap) => (
            <li key={cap.id}>
              <b>{cap.id}</b> — {cap.entity}
            </li>
          ))}
        </ul>
        <pre>{JSON.stringify(tracks, null, 2)}</pre>
        <pre>{JSON.stringify(formulas, null, 2)}</pre>
      </section>

      <section>
        <h2>Faculty session</h2>
        <select value={mode} onChange={(e) => setMode(e.target.value)}>
          {["lecture", "brief", "socratic", "sparring", "oral_quiz", "examiner"].map((m) => (
            <option key={m}>{m}</option>
          ))}
        </select>
        <input type="number" min={1} value={week} onChange={(e) => setWeek(Number(e.target.value))} />
        <button onClick={openSession}>Open session</button>
        <AuthorityLine body={session} />
        <pre>{(session?.record?.turns || []).join("\n")}</pre>

        <h2>Memo grading</h2>
        <textarea rows={6} value={submission} onChange={(e) => setSubmission(e.target.value)} />
        <button onClick={gradeMemo}>Grade memo</button>
        <AuthorityLine body={grade} />
        <pre>{(grade?.verdict_lines || []).join("\n")}</pre>

        <h2>Gradebook</h2>
        <input type="number" value={scores.memos} onChange={(e) => setScores({ ...scores, memos: Number(e.target.value) })} />
        <input type="number" value={scores.defenses} onChange={(e) => setScores({ ...scores, defenses: Number(e.target.value) })} />
        <input type="number" value={scores.capstone} onChange={(e) => setScores({ ...scores, capstone: Number(e.target.value) })} />
        <button onClick={computeGradebook}>Compute gradebook</button>
        <AuthorityLine body={gradebook} />
        <pre>{(gradebook?.gradebook || []).join("\n")}</pre>

        <h2>Reading and case library</h2>
        <button onClick={readWeek}>Read the week</button>
        <AuthorityLine body={library} />
        <pre>{JSON.stringify(library?.record?.cases || [], null, 2)}</pre>
      </section>
    </main>
  );
}
