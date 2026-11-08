/**
 * Harbourline Civil Works -- operator console (authored source).
 *
 * Three screens, one platform and one API:
 *   command_center    -- capability discovery, create and list on the real routes
 *   operational_chat  -- resolve a governing term against the source of record
 *   resident_engineer -- record position across every capability, with authority
 *
 * The deployed console is the dependency-free build in `frontend/index.html`,
 * emitted to `app/static/index.html` by `npm run build` and served at `/`.
 * Every path these screens call exists in app/routes.py; every answer carries
 * the authority label the route returned.
 */
import CommandCenter from "./modules/command_center";
import OperationalChat from "./modules/operational_chat";
import ResidentEngineer from "./modules/resident_engineer";

export default function App() {
  return (
    <main>
      <header>
        <h1>Harbourline Civil Works -- contracts administration</h1>
        <p>Progress claims, delay damages, QA/ITP records and the document register, grounded in the uploaded contract and BOQ.</p>
      </header>
      <nav>
        <a href="#/command_center">Command center</a>
        <a href="#/operational_chat">Operational chat</a>
        <a href="#/resident_engineer">Resident engineer</a>
      </nav>
      <CommandCenter />
      <OperationalChat />
      <ResidentEngineer />
    </main>
  );
}
