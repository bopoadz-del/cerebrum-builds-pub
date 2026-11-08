WORKFLOWS = [
  {
    "description": "Default linear workflow over planned capabilities.",
    "name": "Capability sequence",
    "steps": [
      {
        "capability_id": "progress_claim_processing",
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
        "capability_id": "contract_clause_grounding",
        "role": "execute"
      },
      {
        "capability_id": "performance_security_tracking",
        "role": "execute"
      },
      {
        "capability_id": "compliance_dashboard",
        "role": "execute"
      }
    ],
    "workflow_id": "product.capability_sequence"
  }
]
