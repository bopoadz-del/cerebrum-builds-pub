/* Generated UI shell for Harbourline Civil Works contracts administration */
import CommandCenterModule from './modules/command_center';
import OperationalChatModule from './modules/operational_chat';
import ResidentEngineerModule from './modules/resident_engineer';
export default function App(){
  return (
    <main data-product="product">
      <h1>Harbourline Civil Works contracts administration</h1>
      <p>A contracts-administration platform built for the Harbourline Civil Works project, serving the project's contract administrator and commercial team. It treats the uploaded contract excerpt and BOQ as the source of record, and administers progress claims and interim payment certificates under Clause 14.3 (5% retention, released 50/50), tracks delay damages under Clause 8.7 (0.1% of the Accepted Contract Amount per day, capped at 10%), records QA/ITP inspection and test records, and maintains a co</p>
      <CommandCenterModule />
      <OperationalChatModule />
      <ResidentEngineerModule />
    </main>
  )
}
