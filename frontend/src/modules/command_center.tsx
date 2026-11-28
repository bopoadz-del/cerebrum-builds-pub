/**
 * Command centre: the customer booking surface.
 *
 * It drives the live routes only -- GET /v1/customer_booking_flow/available
 * to browse contractors by suburb and slot, POST /v1/customer_booking_flow
 * to create the booking, and GET /v1/customer_booking_flow to read back what
 * the platform stored. A conflict is shown as the platform's own answer.
 */
import { useEffect, useState } from "react";

type Contractor = {
  contractor_reference: string;
  contractor_name?: string;
  service_suburbs: string[];
  capacity: number;
  booked_in_slot: number;
  availability: { weekday: string; start_time: string; end_time: string }[];
};

type BookingRow = {
  id: number;
  reference: string;
  contractor_reference: string;
  suburb: string;
  booking_date: string;
  start_time: string;
  end_time: string;
  status: string;
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

export default function CommandCenterModule() {
  const [suburb, setSuburb] = useState("Newtown");
  const [bookingDate, setBookingDate] = useState("2026-09-03");
  const [startTime, setStartTime] = useState("09:00:00");
  const [endTime, setEndTime] = useState("10:00:00");
  const [contractors, setContractors] = useState<Contractor[]>([]);
  const [selected, setSelected] = useState("");
  const [customerName, setCustomerName] = useState("");
  const [customerEmail, setCustomerEmail] = useState("guest@example.com");
  const [quoted, setQuoted] = useState("25");
  const [cost, setCost] = useState("15");
  const [bookings, setBookings] = useState<BookingRow[]>([]);
  const [answer, setAnswer] = useState<unknown>(null);
  const [error, setError] = useState("");

  async function browse() {
    setError("");
    const query = new URLSearchParams({
      suburb,
      booking_date: bookingDate,
      start_time: startTime,
      end_time: endTime,
    });
    const { status, body } = await call(
      "/v1/customer_booking_flow/available?" + query.toString()
    );
    if (status !== 200 || !body || body.ok === false) {
      setError((body && body.error) || "browse failed (" + status + ")");
      setContractors([]);
      return;
    }
    setContractors(body.items || []);
    setSelected(body.items && body.items[0] ? body.items[0].contractor_reference : "");
  }

  async function loadBookings() {
    const { body } = await call("/v1/customer_booking_flow");
    if (body && Array.isArray(body.items)) setBookings(body.items);
  }

  async function book() {
    setError("");
    const payload = {
      reference: "booking-" + Date.now(),
      status: "open",
      notes: "created from the command centre",
      customer_name: customerName || "customer",
      customer_email: customerEmail,
      contractor_reference: selected,
      suburb,
      booking_date: bookingDate,
      start_time: startTime,
      end_time: endTime,
      service_type: "delivery",
      quoted_amount: Number(quoted),
      cost_amount: Number(cost),
    };
    const { status, body } = await call("/v1/customer_booking_flow", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    setAnswer({ status, body });
    if (status === 409) {
      setError("That contractor already has a confirmed booking in this slot.");
    }
    await loadBookings();
  }

  useEffect(() => {
    browse();
    loadBookings();
  }, []);

  return (
    <section data-module="command_center" data-product="product">
      <header>
        <h2>Command centre</h2>
        <p>Browse contractors by suburb and slot, then book one.</p>
      </header>

      <div className="row">
        <label>Suburb <input value={suburb} onChange={(e) => setSuburb(e.target.value)} /></label>
        <label>Date <input type="date" value={bookingDate} onChange={(e) => setBookingDate(e.target.value)} /></label>
        <label>Start <input value={startTime} onChange={(e) => setStartTime(e.target.value)} /></label>
        <label>End <input value={endTime} onChange={(e) => setEndTime(e.target.value)} /></label>
        <button onClick={browse}>Find contractors</button>
      </div>

      {error ? <p className="err">{error}</p> : null}

      <h3>Available contractors ({contractors.length})</h3>
      <ul>
        {contractors.map((contractor) => (
          <li key={contractor.contractor_reference}>
            <label>
              <input
                type="radio"
                name="contractor"
                checked={selected === contractor.contractor_reference}
                onChange={() => setSelected(contractor.contractor_reference)}
              />
              {contractor.contractor_name || contractor.contractor_reference} — {contractor.service_suburbs.join(", ")}
            </label>
            <span className="dim">
              {" "}capacity {contractor.capacity}, booked in slot {contractor.booked_in_slot}
            </span>
            <ul>
              {contractor.availability.map((window, index) => (
                <li key={index}>{window.weekday} {window.start_time}–{window.end_time}</li>
              ))}
            </ul>
          </li>
        ))}
      </ul>

      <h3>Book the selected contractor</h3>
      <div className="row">
        <label>Customer <input value={customerName} onChange={(e) => setCustomerName(e.target.value)} /></label>
        <label>Email <input value={customerEmail} onChange={(e) => setCustomerEmail(e.target.value)} /></label>
        <label>Quoted <input value={quoted} onChange={(e) => setQuoted(e.target.value)} /></label>
        <label>Cost <input value={cost} onChange={(e) => setCost(e.target.value)} /></label>
        <button disabled={!selected} onClick={book}>Create booking</button>
      </div>
      <pre>{JSON.stringify(answer, null, 2)}</pre>

      <h3>Stored bookings ({bookings.length})</h3>
      <table>
        <thead>
          <tr><th>Reference</th><th>Contractor</th><th>Suburb</th><th>Date</th><th>Slot</th><th>Status</th></tr>
        </thead>
        <tbody>
          {bookings.map((booking) => (
            <tr key={booking.id}>
              <td>{booking.reference}</td>
              <td>{booking.contractor_reference}</td>
              <td>{booking.suburb}</td>
              <td>{booking.booking_date}</td>
              <td>{booking.start_time}–{booking.end_time}</td>
              <td>{booking.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
