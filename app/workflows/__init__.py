WORKFLOWS = [
  {
    "description": "Default linear workflow over planned capabilities.",
    "name": "Capability sequence",
    "steps": [
      {
        "capability_id": "contract_source_of_record",
        "role": "execute"
      },
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
        "capability_id": "contract_compliance_gate",
        "role": "execute"
      }
    ],
    "workflow_id": "product.capability_sequence"
  }
]
