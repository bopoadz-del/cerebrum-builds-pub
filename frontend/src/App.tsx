/**
 * Delivery Service Platform operator frontend.
 *
 * Three real surfaces over the platform's own routes:
 *   Command centre    — browse by suburb/slot and book a contractor
 *   Operational chat  — lifecycle transitions and customer messages
 *   Resident engineer — contractor onboarding, weekly availability, ranking
 *
 * The Factory-served console at app/static/index.html remains the live
 * deployment surface; this module tree is the same API driven from source.
 */
import { useEffect, useState } from "react";

import CommandCenterModule from "./modules/command_center";
import OperationalChatModule from "./modules/operational_chat";
import ResidentEngineerModule from "./modules/resident_engineer";

type Tab = "command_center" | "operational_chat" | "resident_engineer";

const TABS: { id: Tab; label: string }[] = [
  { id: "command_center", label: "Command centre" },
  { id: "operational_chat", label: "Operational chat" },
  { id: "resident_engineer", label: "Resident engineer" },
];

export default function App() {
  const [tab, setTab] = useState<Tab>("command_center");
  const [tenant, setTenant] = useState("");

  useEffect(() => {
    fetch("/v1/tenant", {
      headers: { Authorization: "Bearer " + ((window as any).PLATFORM_TOKEN || "") },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((body) => setTenant((body && body.tenant_id) || ""))
      .catch(() => setTenant(""));
  }, []);

  return (
    <main>
      <h1>Delivery Service Platform</h1>
      <p className="dim">
        Set <code>window.PLATFORM_TOKEN</code> to the deploy token before using a screen.
        {tenant ? " Bound tenant: " + tenant + "." : " Not bound to a tenant."}
      </p>
      <nav>
        {TABS.map((entry) => (
          <button key={entry.id} onClick={() => setTab(entry.id)} disabled={tab === entry.id}>
            {entry.label}
          </button>
        ))}
      </nav>
      {tab === "command_center" ? <CommandCenterModule /> : null}
      {tab === "operational_chat" ? <OperationalChatModule /> : null}
      {tab === "resident_engineer" ? <ResidentEngineerModule /> : null}
    </main>
  );
}
