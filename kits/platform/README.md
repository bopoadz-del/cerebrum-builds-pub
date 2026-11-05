# Platform kit

The platform blocks this product composes. They are vendored from the Store
and pinned by `blocks.lock.json`; nothing here is a copy of a block's logic.

| Block | Why the product binds it |
| --- | --- |
| analytics | gradebook events (weighted average per term) |
| approval_rules | capstone review decisions |
| audit | one audit row per faculty session and per admin action |
| auth | tenant key inventory at enrolment |
| config | declared in the blueprint; not bound (see app/actions/track_loader.py) |
| dashboard | the operator surface the console renders |
| database | table discovery for the persistence it owns |
| email | address validation for the week-1 reading email |
| evidence_chain | memo verdict provenance |
| formula_executor | rubric totals and weighted averages |
| governance_gate | session-level approval state |
| ingestion_provenance | memo provenance record |
| knowledge | tenant corpus search for a session |
| memory | session transcript pointer |
| notification | outbox for queued programme mail |
| orchestrator | declared in the blueprint; not bound (see app/actions/faculty_session.py) |
| pdf | transcript and defense-schedule extraction |
| transaction_state_machine | the defense lifecycle machine |
| validation | track document pipeline and memo evidence |
| vector_search | the week's readings and cases, indexed per week |
| version | published track content versions |
| version_diff | week-level diff between track versions |
| workbench | declared in the blueprint; not bound (needs an agent CLI the image does not ship) |
| workflow | the defense audit chain |
