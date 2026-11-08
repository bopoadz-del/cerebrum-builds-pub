/**
 * Operational chat: resolve a governing term against the uploaded contract
 * and BOQ through POST /v1/contract_and_boq_source_of_record. The operator
 * picks a clause or a BOQ item; the capability answers with the term, its
 * quantity and rate where applicable, its document citation and the authority
 * layer it resolved at. A term the documents do not contain is refused and
 * the refusal is shown verbatim rather than dressed as an answer.
 */
import { useEffect, useState } from "react";
import { request, type Answer, type Capability } from "./command_center";

export default function OperationalChat() {
  const [capability, setCapability] = useState<Capability | null>(null);
  const [documentType, setDocumentType] = useState("contract");
  const [term, setTerm] = useState("");
  const [answer, setAnswer] = useState<Answer>({});
  const [detail, setDetail] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    request("/v1/capabilities").then(({ body }) => {
      const items = (body.items || []) as unknown as Capability[];
      setCapability(items.find((item) => item.id === "contract_and_boq_source_of_record") || null);
    });
  }, []);

  const choices = capability?.fields.find((field) => field.name === (documentType === "boq" ? "boq_item" : "clause_ref"))?.allowed_values || [];

  async function resolve() {
    const payload: Record<string, unknown> = { reference: "console-" + Date.now(), document_type: documentType };
    if (term) payload[documentType === "boq" ? "boq_item" : "clause_ref"] = term;
    const { body } = await request("/v1/contract_and_boq_source_of_record", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setAnswer(body);
    setDetail((body as unknown as { result?: Record<string, unknown> }).result || null);
  }

  return (
    <section data-screen="operational_chat">
      <h2>Source of record</h2>
      <select value={documentType} onChange={(event) => { setDocumentType(event.target.value); setTerm(""); }}>
        <option value="contract">contract</option>
        <option value="boq">boq</option>
      </select>
      <select value={term} onChange={(event) => setTerm(event.target.value)}>
        <option value="">whole document</option>
        {choices.map((value) => <option key={value} value={value}>{value}</option>)}
      </select>
      <button onClick={resolve}>Resolve</button>
      <p>{detail ? String(detail.description || detail.citation || "Resolved") : "Choose a clause or BOQ item."}</p>
      <p>Authority: {answer.authority || "unlabelled"}</p>
      {answer.ok === false ? <p role="alert">Refused: {answer.error}</p> : null}
    </section>
  );
}
