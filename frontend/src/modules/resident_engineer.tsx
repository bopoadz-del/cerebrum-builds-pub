/**
 * Resident engineer: the position across every declared capability. For each
 * capability the console asks the real list route GET /v1/{capability} for the
 * caller's records and shows the count together with the authority layer the
 * route answers at. It never invents a count: a refused or failed list is
 * shown as unavailable rather than as zero.
 */
import { useEffect, useState } from "react";
import { request, type Capability } from "./command_center";

type Row = { id: string; title: string; count: number | null; authority: string };

export default function ResidentEngineer() {
  const [rows, setRows] = useState<Row[]>([]);
  const [status, setStatus] = useState("Loading the capability roster ...");

  useEffect(() => {
    request("/v1/capabilities").then(async ({ body }) => {
      const items = (body.items || []) as unknown as Capability[];
      const measured: Row[] = [];
      for (const capability of items) {
        const listed = await request("/v1/" + encodeURIComponent(capability.id));
        const available = listed.status === 200 && listed.body.ok !== false;
        measured.push({
          id: capability.id,
          title: capability.title,
          count: available ? (listed.body.items || []).length : null,
          authority: listed.body.authority || capability.authority || "unlabelled",
        });
      }
      setRows(measured);
      setStatus("Position across " + measured.length + " declared capabilities.");
    });
  }, []);

  return (
    <section data-screen="resident_engineer">
      <h2>Resident engineer</h2>
      <table><thead><tr><th>Capability</th><th>Records</th><th>Authority</th></tr></thead><tbody>
        {rows.map((row) => (
          <tr key={row.id}>
            <td>{row.title}</td>
            <td>{row.count === null ? "unavailable" : row.count}</td>
            <td>{row.authority}</td>
          </tr>
        ))}
      </tbody></table>
      <p>{status}</p>
    </section>
  );
}
