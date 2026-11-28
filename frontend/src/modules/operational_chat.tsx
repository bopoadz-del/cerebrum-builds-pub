/**
 * Operational chat: booking communication and lifecycle actions.
 *
 * Drives three real routes: POST /v1/booking_status_lifecycle for the
 * requested → accepted → in progress → completed/cancelled decision,
 * POST /v1/email for a customer message, and POST /v1/booking_notifications
 * for the booking alert (whose declared placeholder answers 503 and is shown
 * as such, never as a sent message).
 */
import { useEffect, useState } from "react";

type BookingRow = {
  id: number;
  reference: string;
  contractor_reference: string;
  status: string;
};

type Message = { role: "operator" | "platform"; text: string };

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

export default function OperationalChatModule() {
  const [bookings, setBookings] = useState<BookingRow[]>([]);
  const [reference, setReference] = useState("");
  const [state, setState] = useState("requested");
  const [target, setTarget] = useState("accepted");
  const [actor, setActor] = useState("contractor");
  const [recipient, setRecipient] = useState("guest@example.com");
  const [subject, setSubject] = useState("Booking update");
  const [message, setMessage] = useState("Your booking is confirmed.");
  const [channel, setChannel] = useState("email");
  const [messages, setMessages] = useState<Message[]>([]);

  async function loadBookings() {
    const { body } = await call("/v1/customer_booking_flow");
    if (body && Array.isArray(body.items)) {
      setBookings(body.items);
      if (!reference && body.items.length) setReference(body.items[0].reference);
    }
  }

  useEffect(() => {
    loadBookings();
  }, []);

  function say(role: Message["role"], text: string) {
    setMessages((current) => [...current, { role, text }]);
  }

  async function transition() {
    const payload = {
      reference: "transition-" + Date.now(),
      status: "open",
      notes: "operator transition",
      booking_reference: reference,
      current_state: state,
      target_state: target,
      actor,
      transition_id: "ui-" + Date.now(),
    };
    const { status, body } = await call("/v1/booking_status_lifecycle", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    const result = (body && body.result) || {};
    say(
      "platform",
      status === 200 && result.allowed
        ? "Transition allowed: " + state + " → " + target + ". " +
          (result.views && result.views.customer ? result.views.customer : "")
        : "Transition refused: " + ((result.decision) || (body && body.error) || status)
    );
    if (status === 200 && result.allowed) setState(target);
    await loadBookings();
  }

  async function sendEmail() {
    const { status, body } = await call("/v1/email", {
      method: "POST",
      body: JSON.stringify({
        reference: "email-" + Date.now(),
        status: "open",
        notes: "operator message",
        recipient_email: recipient,
        subject,
        body: message,
      }),
    });
    const result = (body && body.result) || {};
    say(
      "platform",
      status === 200
        ? "Email " + (result.delivery || "unknown") +
          (result.setting ? " — set " + result.setting : "")
        : "Email refused: " + ((body && body.error) || status)
    );
  }

  async function notify() {
    const { status, body } = await call("/v1/booking_notifications", {
      method: "POST",
      body: JSON.stringify({
        reference: "notice-" + Date.now(),
        status: "open",
        notes: "booking alert",
        booking_reference: reference,
        recipient_email: recipient,
        recipient_phone: "",
        channel,
        message,
        event_type: state,
      }),
    });
    const settings = (body && body.settings) || [];
    say(
      "platform",
      status === 200
        ? "Notification accepted: " + JSON.stringify((body && body.result) || {})
        : status + " " + ((body && body.error) || "refused") +
          (settings.length ? " — needs " + settings.join(", ") : "")
    );
  }

  return (
    <section data-module="operational_chat" data-product="product">
      <header>
        <h2>Operational chat</h2>
        <p>Move a booking through its lifecycle and message the parties.</p>
      </header>

      <div className="row">
        <label>
          Booking
          <select value={reference} onChange={(e) => setReference(e.target.value)}>
            {bookings.map((booking) => (
              <option key={booking.id} value={booking.reference}>
                {booking.reference} ({booking.status})
              </option>
            ))}
          </select>
        </label>
        <label>
          From
          <select value={state} onChange={(e) => setState(e.target.value)}>
            {["requested", "accepted", "in_progress", "completed", "cancelled"].map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          To
          <select value={target} onChange={(e) => setTarget(e.target.value)}>
            {["requested", "accepted", "in_progress", "completed", "cancelled"].map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <label>
          Actor
          <select value={actor} onChange={(e) => setActor(e.target.value)}>
            {["customer", "contractor", "operator", "system"].map((value) => (
              <option key={value} value={value}>{value}</option>
            ))}
          </select>
        </label>
        <button onClick={transition}>Apply transition</button>
      </div>

      <div className="row">
        <label>To <input value={recipient} onChange={(e) => setRecipient(e.target.value)} /></label>
        <label>Subject <input value={subject} onChange={(e) => setSubject(e.target.value)} /></label>
        <label>
          Channel
          <select value={channel} onChange={(e) => setChannel(e.target.value)}>
            <option value="email">email</option>
            <option value="webhook">webhook</option>
            <option value="sms">sms</option>
          </select>
        </label>
      </div>
      <textarea rows={4} cols={70} value={message} onChange={(e) => setMessage(e.target.value)} />
      <div className="row">
        <button onClick={sendEmail}>Send email</button>
        <button onClick={notify}>Send booking notification</button>
      </div>

      <h3>Conversation</h3>
      <ul>
        {messages.map((entry, index) => (
          <li key={index} className={entry.role === "platform" ? "dim" : ""}>
            <strong>{entry.role}:</strong> {entry.text}
          </li>
        ))}
      </ul>
    </section>
  );
}
