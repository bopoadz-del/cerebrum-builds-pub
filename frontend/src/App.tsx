/* Generated UI shell for Harbourline Civil Works */
import CommandCenterModule from './modules/command_center';
import OperationalChatModule from './modules/operational_chat';
import ResidentEngineerModule from './modules/resident_engineer';
export default function App(){
  return (
    <main data-product="product">
      <h1>Harbourline Civil Works</h1>
      <p>A contracts-administration platform for the Harbourline Civil Works project that governs progress claims, delay-damages exposure, QA/ITP records and the project document register against the uploaded contract and BOQ as the single source of record. It serves the project's contract administrator, commercial manager, QA lead and document controller, anchoring every claim, notification and test record to the executed contract clauses (Time for Completion, Delay Damages, Retention, Performance Secur</p>
      <CommandCenterModule />
      <OperationalChatModule />
      <ResidentEngineerModule />
    </main>
  )
}
