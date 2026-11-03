WORKFLOWS = [
  {
    "description": "Default linear workflow over planned capabilities.",
    "name": "Capability sequence",
    "steps": [
      {
        "capability_id": "progress_claims",
        "role": "execute"
      },
      {
        "capability_id": "delay_damages_tracking",
        "role": "execute"
      },
      {
        "capability_id": "qa_itp_records",
        "role": "execute"
      },
      {
        "capability_id": "document_register",
        "role": "execute"
      },
      {
        "capability_id": "performance_security_tracking",
        "role": "execute"
      },
      {
        "capability_id": "defects_notification_period",
        "role": "execute"
      },
      {
        "capability_id": "claim_evidence_and_approvals",
        "role": "execute"
      }
    ],
    "workflow_id": "product.capability_sequence"
  }
]
