/**
 * Resident engineer: contractor fleet maintenance.
 *
 * Drives POST /v1/contractor_onboarding_and_service_areas to register a
 * contractor with its active suburbs, POST /v1/contractor_availability_schedule
 * for the weekly calendar, and POST /v1/location_based_matching to see which
 * active-suburb contractor the platform ranks for a booking slot.
 */
import { useEffect, useState } from "react";

type ContractorRow = {
  id: number;
  reference: string;
  contractor_name: string;
  service_suburbs: string;
  capacity: number;
  active: boolean;
};

const token = () => (window as any).PLATFORM_TOKEN || "";
const headers = () => ({
  Authorization: "Bearer " + token(),
  "Content-Type": "application/json",
});

async function call(path: string, init?: RequestInit) {
  const res = await fetch(path, { ...(init || {}), headers: headers() });
  const body = await res.json().catch(() => null);
  return { status: res.status, body };
}

export default function ResidentEngineerModule() {
  const [contractors, setContractors] = useState<ContractorRow[]>([]);
  const [reference, setReference] = useState("");
  const [name, setName] = useState("");
  const [suburbs, setSuburbs] = useState("Newtown, Erskineville");
  const [email, setEmail] = useState("contractor@example.com");
  const [vehicle, setVehicle] = useState("van");
  const [capacity, setCapacity] = useState("1");
  const [active, setActive] = useState(true);

  const [weekday, setWeekday] = useState("thursday");
  const [start, setStart] = useState("08:00:00");
  const [end, setEnd] = useState("17:00:00");

  const [matchSuburb, setMatchSuburb] = useState("Newtown");
  const [matchDate, setMatchDate] = useState("2026-09-03");
  const [matchStart, setMatchStart] = useState("09:00:00");
  const [requiredSkills, setRequiredSkills] = useState("van");
  const [answer, setAnswer] = useState<unknown>(null);
  const [error, setError] = useState("");
  const [catalogue, setCatalogue] = useState<{ suburb: string; region?: string; active: boolean }[]>([]);
  const [newSuburb, setNewSuburb] = useState("");
  const [newRegion, setNewRegion] = useState("");

  async function loadContractors() {
    const { body } = await call("/v1/contractor_onboarding_and_service_areas");
    if (body && Array.isArray(body.items)) setContractors(body.items);
  }

  async function loadCatalogue() {
    const { body } = await call("/v1/ops_back_office/suburbs");
    if (body && Array.isArray(body.items)) setCatalogue(body.items);
  }

  async function addSuburb(active: boolean) {
    setError("");
    if (!newSuburb.trim()) {
      setError("Name the suburb to add or retire.");
      return;
    }
    const { status, body } = await call("/v1/ops_back_office/suburbs", {
      method: "POST",
      body: JSON.stringify({ suburb: newSuburb, region: newRegion, active }),
    });
    setAnswer({ status, body });
    if (status !== 200 || (body && body.ok === false)) {
      setError((body && body.error) || "catalogue update refused (" + status + ")");
    } else {
      setNewSuburb("");
      setNewRegion("");
    }
    await loadCatalogue();
  }

  useEffect(() => {
    loadContractors();
    loadCatalogue();
  }, []);

  async function onboard() {
    setError("");
    const ref = reference || "contractor-" + Date.now();
    const { status, body } = await call("/v1/contractor_onboarding_and_service_areas", {
      method: "POST",
      body: JSON.stringify({
        reference: ref,
        status: "open",
        notes: "registered from the resident engineer screen",
        contractor_name: name || ref,
        contact_email: email,
        phone: "",
        service_suburbs: suburbs,
        vehicle_type: vehicle,
        capacity: Number(capacity) || 1,
        active,
      }),
    });
    setAnswer({ status, body });
    if (status !== 200 || (body && body.ok === false)) {
      setError((body && body.error) || "onboarding refused (" + status + ")");
    } else {
      setReference(ref);
    }
    await loadContractors();
  }

  async function publishSchedule() {
    setError("");
    const target = reference || (contractors[0] && contractors[0].reference) || "";
    if (!target) {
      setError("Register or select a contractor first.");
      return;
    }
    const { status, body } = await call("/v1/contractor_availability_schedule", {
      method: "POST",
      body: JSON.stringify({
        reference: "availability-" + Date.now(),
        status: "open",
        notes: "weekly window",
        contractor_reference: target,
        weekday,
        start_time: start,
        end_time: end,
        capacity: Number(capacity) || 1,
        active: true,
      }),
    });
    setAnswer({ status, body });
    if (status !== 200 || (body && body.ok === false)) {
      setError((body && body.error) || "schedule refused (" + status + ")");
    }
  }

  async function match() {
    setError("");
    const { status, body } = await call("/v1/location_based_matching", {
      method: "POST",
      body: JSON.stringify({
        reference: "match-" + Date.now(),
        status: "open",
        notes: "ranking request",
        booking_reference: "booking-" + Date.now(),
        suburb: matchSuburb,
        contractor_reference: reference,
        booking_date: matchDate,
        start_time: matchStart,
        distance_km: 2.5,
        required_skills: requiredSkills,
      }),
    });
    setAnswer({ status, body });
    if (status !== 200 || (body && body.ok === false)) {
      setError((body && body.error) || "matching refused (" + status + ")");
    }
  }

  return (
    <section data-module="resident_engineer" data-product="product">
      <header>
        <h2>Resident engineer</h2>
        <p>Onboard contractors, publish their week, and verify the ranking.</p>
      </header>

      {error ? <p className="err">{error}</p> : null}

      <h3>Suburb catalogue (ops)</h3>
      <p className="dim">
        Contractor onboarding only activates suburbs in this list; a suburb a
        contractor proposes but ops has not added stays pending.
      </p>
      <div className="row">
        <label>Suburb <input value={newSuburb} onChange={(e) => setNewSuburb(e.target.value)} /></label>
        <label>Region <input value={newRegion} onChange={(e) => setNewRegion(e.target.value)} /></label>
        <button onClick={() => addSuburb(true)}>Add / activate</button>
        <button onClick={() => addSuburb(false)}>Retire</button>
      </div>
      <ul data-catalogue>
        {catalogue.map((row) => (
          <li key={row.suburb}>
            {row.suburb}{row.region ? " (" + row.region + ")" : ""} — {row.active ? "active" : "retired"}
          </li>
        ))}
      </ul>

      <h3>Contractor profile</h3>
      <div className="row">
        <label>Name <input value={name} onChange={(e) => setName(e.target.value)} /></label>
        <label>Email <input value={email} onChange={(e) => setEmail(e.target.value)} /></label>
        <label>Vehicle <input value={vehicle} onChange={(e) => setVehicle(e.target.value)} /></label>
        <label>Capacity <input value={capacity} onChange={(e) => setCapacity(e.target.value)} /></label>
        <label>
          Active
          <input type="checkbox" checked={active} onChange={(e) => setActive(e.target.checked)} />
        </label>
      </div>
      <div className="row">
        <label>Active suburbs <input size={40} value={suburbs} onChange={(e) => setSuburbs(e.target.value)} /></label>
        <button onClick={onboard}>Register contractor</button>
      </div>

      <h3>Weekly availability</h3>
      <div className="row">
        <label>
          Contractor
          <select value={reference} onChange={(e) => setReference(e.target.value)}>
            <option value="">—</option>
            {contractors.map((contractor) => (
              <option key={contractor.id} value={contractor.reference}>
                {contractor.contractor_name || contractor.reference}
              </option>
            ))}
          </select>
        </label>
        <label>
          Weekday
          <select value={weekday} onChange={(e) => setWeekday(e.target.value)}>
            {["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"].map((day) => (
              <option key={day} value={day}>{day}</option>
            ))}
          </select>
        </label>
        <label>Start <input value={start} onChange={(e) => setStart(e.target.value)} /></label>
        <label>End <input value={end} onChange={(e) => setEnd(e.target.value)} /></label>
        <button onClick={publishSchedule}>Publish window</button>
      </div>

      <h3>Match a booking</h3>
      <div className="row">
        <label>Suburb <input value={matchSuburb} onChange={(e) => setMatchSuburb(e.target.value)} /></label>
        <label>Date <input type="date" value={matchDate} onChange={(e) => setMatchDate(e.target.value)} /></label>
        <label>Start <input value={matchStart} onChange={(e) => setMatchStart(e.target.value)} /></label>
        <label>Skills <input value={requiredSkills} onChange={(e) => setRequiredSkills(e.target.value)} /></label>
        <button onClick={match}>Rank contractors</button>
      </div>

      <pre>{JSON.stringify(answer, null, 2)}</pre>

      <h3>Contractors ({contractors.length})</h3>
      <ul>
        {contractors.map((contractor) => (
          <li key={contractor.id}>
            <strong>{contractor.contractor_name || contractor.reference}</strong> — {contractor.service_suburbs}
            <span className="dim"> capacity {contractor.capacity}, {contractor.active ? "active" : "pending approval"}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
