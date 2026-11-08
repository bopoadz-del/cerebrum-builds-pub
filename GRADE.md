# GRADE -- product

**Certified:** NO (Layer 1 decides; Layer 2 can only block)

## Layer 1 (deterministic): RED
- Functions graded: 6 (min 4)
  - `progress_claim_management`: PASS; mutants killed constant_return, drop_rule; survived none
  - `delay_damages_tracking`: PASS; mutants killed constant_return, drop_rule; survived none
  - `qa_itp_records`: PASS; mutants killed constant_return, drop_rule; survived none
  - `document_register`: PASS; mutants killed constant_return, drop_rule; survived none
  - `contract_terms_governance`: PASS; mutants killed constant_return, drop_rule; survived none
  - `commercial_dashboard`: PASS; mutants killed constant_return, drop_rule; survived none
- UI steps passed: 0/0
  - FAIL: UI run did not happen: no playwright report

## Layer 2 (separate grader context): ran
- PASS: Does the product deliver capability 'progress_claim_management' as the brief asked? -- evidence: "progress_claim_management.py: "A claim is measured against one uploaded BOQ line, retention is withheld at the contract's own percentage (Clause 14.3)... the retention rule is submitted to the approval register". BLOCK_IDS = ["boq_processor", "finance_reconciliation_workflow", "approval_rules", "audit"]. Rates and quantities are read from the BOQ via contract_data.boq_item. Layer 1 passed with both mutants killed."
- PASS: Does the product deliver capability 'delay_damages_tracking' as the brief asked? -- evidence: "delay_damages_tracking.py: elapsed time is measured against "contract_data.TIME_FOR_COMPLETION_DAYS + extension_days". DAMAGES_CODE is "uncapped = rate * delay_days ... cap = accepted_contract_amount * (cap_pct / 100.0) ... result = min(uncapped, cap)". ALERT_THRESHOLD = 0.8 and a notification block raise alerts when the cap is approached. Layer 1 passed."
- PASS: Does the product deliver capability 'qa_itp_records' as the brief asked? -- evidence: "qa_itp_records.py holds inspection_lot, hold_point, witness_point, test_result and signoff_by. It refuses a pass without sign-off ("a passing inspection lot must name the person who signed it off"). BLOCK_IDS = ["document_engine", "task_listing", "evidence_chain", "audit_chain"] supply the evidence and audit trail. Layer 1 passed."
- PASS: Does the product deliver capability 'document_register' as the brief asked? -- evidence: "document_register.py keeps revision, checksum, revision_date and status per entry, with _revision_history and a refusal to rewind the revision chain. DISTRIBUTION_BY_TYPE and REVIEW_STATE_BY_STATUS cover distribution and review status. The contract and BOQ are filed from the uploaded source-of-record text (contract_source_text and boq_source_text). Layer 1 passed."
- PASS: Does the product deliver capability 'contract_terms_governance' as the brief asked? -- evidence: "contract_terms_governance.py defines TERM_UNITS with time_for_completion, delay_damages, defects_notification, retention and performance_security. Each is cited to a clause (sources.clause), and a caller value is compared with the contract and reported as a divergence naming the contract's value. Layer 1 passed."
- PASS: Does the product deliver capability 'commercial_dashboard' as the brief asked? -- evidence: "commercial_dashboard.py aggregates the tenant's claims, delay assessments and QA records. _claim_metrics returns gross, retention and net, with retention computed via formulas.retention_amount at contract_data.RETENTION_PCT. The module states it covers "cumulative certified amounts, retention balances, delay-damages exposure and open QA items". Layer 1 passed."
- FAIL: Does screen 'command_center' render the capability it is declared for? -- evidence: "SCREENS declares command_center with all six capabilities and routes such as "POST /v1/{capability}", but the rendered product does not include app/static/index.html. Layer 1 ui reports "UI run did not happen: no playwright report". Rendering cannot be confirmed from the product."
- FAIL: Does screen 'operational_chat' render the capability it is declared for? -- evidence: "The manifest declares operational_chat with document_register and contract_terms_governance and routes like "POST /v1/document_register/ask". No rendered UI markup is shown and the UI run failed ("no playwright report"), so there is no evidence the screen renders a cited-answer chat."
- FAIL: Does screen 'resident_engineer' render the capability it is declared for? -- evidence: "The manifest says resident_engineer is "the position across every capability, with record counts and authority", but no console HTML or screenshot is provided. The UI check reports "ran": false, so the screen is unverified."
- PASS: Is every number the product shows grounded in a kernel computation or a cited source? -- evidence: "Figures come from contract_data and sources (retention %, 730 days, 0.1% per day, 10% cap, BOQ rates and total) or from formulas.retention_amount and formulas.certified_amount. Missing inputs are stated as assumptions, e.g. "No commencement date on the record; exposure is assessed as zero rather than assuming a start date". The 0.8 alert fraction is declared as the platform's own convention."
- OPEN: Does the product deliver capability 'progress_claim_management' as the brief asked: Creates and tracks interim payment certificates and progress claims, linking claim lines to BOQ items and quantities from document:harbourline_boq.xlsx, applies the 5% retention under Clause 14.3 of document:harbourline_contract.pdf, and routes claims through approval.?
- OPEN: Does the product deliver capability 'delay_damages_tracking' as the brief asked: Tracks elapsed days against the 730-day Time for Completion in Clause 8.2 of document:harbourline_contract.pdf, computes delay damages at 0.1% per day capped at 10% of the Accepted Contract Amount under Clause 8.7, and raises alerts when the cap or milestones are approached.?
- OPEN: Does the product deliver capability 'qa_itp_records' as the brief asked: Captures Inspection and Test Plan records, hold points, inspection results, and sign-offs against work items, with evidence attachments and an immutable audit trail.?
- OPEN: Does the product deliver capability 'document_register' as the brief asked: Maintains a controlled register of project documents with version history, review status, and distribution; ingests the contract and BOQ as source-of-record documents and tracks revisions.?
- OPEN: Does the product deliver capability 'contract_terms_governance' as the brief asked: Extracts and governs key contract terms (time for completion, delay damages, retention, performance security, defects notification period) from document:harbourline_contract.pdf, provides a clause register, and checks claims and outputs against these terms.?
- OPEN: Does the product deliver capability 'commercial_dashboard' as the brief asked: Provides a project commercial dashboard showing claim status, cumulative certified amounts, retention balances, delay-damages exposure, and QA/ITP open items.?
- OPEN: Does screen 'command_center' render the capability it is declared for?
- OPEN: Does screen 'operational_chat' render the capability it is declared for?
- OPEN: Does screen 'resident_engineer' render the capability it is declared for?

## Next tasks
- re-run writer on: Does the product deliver capability 'progress_claim_management' as the brief asked: Creates and tracks interim payment certificates and progress claims, linking claim lines to BOQ items and quantities from document:harbourline_boq.xlsx, applies the 5% retention under Clause 14.3 of document:harbourline_contract.pdf, and routes claims through approval.?
- re-run writer on: Does the product deliver capability 'delay_damages_tracking' as the brief asked: Tracks elapsed days against the 730-day Time for Completion in Clause 8.2 of document:harbourline_contract.pdf, computes delay damages at 0.1% per day capped at 10% of the Accepted Contract Amount under Clause 8.7, and raises alerts when the cap or milestones are approached.?
- re-run writer on: Does the product deliver capability 'qa_itp_records' as the brief asked: Captures Inspection and Test Plan records, hold points, inspection results, and sign-offs against work items, with evidence attachments and an immutable audit trail.?
- re-run writer on: Does the product deliver capability 'document_register' as the brief asked: Maintains a controlled register of project documents with version history, review status, and distribution; ingests the contract and BOQ as source-of-record documents and tracks revisions.?
- re-run writer on: Does the product deliver capability 'contract_terms_governance' as the brief asked: Extracts and governs key contract terms (time for completion, delay damages, retention, performance security, defects notification period) from document:harbourline_contract.pdf, provides a clause register, and checks claims and outputs against these terms.?
- re-run writer on: Does the product deliver capability 'commercial_dashboard' as the brief asked: Provides a project commercial dashboard showing claim status, cumulative certified amounts, retention balances, delay-damages exposure, and QA/ITP open items.?
- re-run writer on: Does screen 'command_center' render the capability it is declared for?
- re-run writer on: Does screen 'operational_chat' render the capability it is declared for?
- re-run writer on: Does screen 'resident_engineer' render the capability it is declared for?
- remove baked literals from app/domain_ops.py: ['product']
- remove baked literals from vendor/cerebrum/core/finance_ops.py: ['product']
- stop leaking the prompt into the source: ['Contract', 'The', 'product']
