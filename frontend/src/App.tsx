/* Generated UI shell for Harbourline Civil Works Contracts Administration */
import CommandCenterModule from './modules/command_center';
import OperationalChatModule from './modules/operational_chat';
import ResidentEngineerModule from './modules/resident_engineer';
export default function App(){
  return (
    <main data-product="product">
      <h1>Harbourline Civil Works Contracts Administration</h1>
      <p>A contracts-administration platform for the Harbourline Civil Works project that treats the uploaded contract excerpt and BOQ as the source of record. It manages progress claims certified against BOQ line items, tracks delay damages under Clause 8.7, maintains QA/ITP records, and runs a controlled document register with revision history. It serves the project's contract administrator, quantity surveyor, QA engineer, and document controller, keeping every claim, deduction, and record traceable ba</p>
      <CommandCenterModule />
      <OperationalChatModule />
      <ResidentEngineerModule />
    </main>
  )
}
