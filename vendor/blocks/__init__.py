"""Vendored registry (verification tree)."""
import importlib
_BLOCK_DEFS = {
    "analytics": ("vendor.cerebrum.blocks.analytics", "AnalyticsBlock"),
    "approval_rules": ("vendor.cerebrum.blocks.approval_rules", "ApprovalRulesBlock"),
    "audit": ("vendor.cerebrum.blocks.audit", "AuditBlock"),
    "auth": ("vendor.cerebrum.blocks.auth", "AuthBlock"),
    "config": ("vendor.cerebrum.blocks.config", "ConfigBlock"),
    "dashboard": ("vendor.cerebrum.blocks.dashboard", "DashboardBlock"),
    "database": ("vendor.cerebrum.blocks.database", "DatabaseBlock"),
    "email": ("vendor.cerebrum.blocks.email", "EmailBlock"),
    "evidence_chain": ("vendor.cerebrum.blocks.evidence_chain", "EvidenceChainBlock"),
    "formula_executor": ("vendor.cerebrum.blocks.formula_executor", "FormulaExecutorBlock"),
    "governance_gate": ("vendor.cerebrum.blocks.governance_gate", "GovernanceGateBlock"),
    "ingestion_provenance": ("vendor.cerebrum.blocks.ingestion_provenance", "IngestionProvenanceBlock"),
    "knowledge": ("vendor.cerebrum.blocks.knowledge", "KnowledgeBlock"),
    "memory": ("vendor.cerebrum.blocks.memory", "MemoryBlock"),
    "notification": ("vendor.cerebrum.blocks.notification", "NotificationBlock"),
    "orchestrator": ("vendor.cerebrum.blocks.orchestrator", "OrchestratorBlock"),
    "pdf": ("vendor.cerebrum.blocks.pdf", "PDFBlock"),
    "transaction_state_machine": ("vendor.cerebrum.blocks.transaction_state_machine", "TransactionStateMachineBlock"),
    "validation": ("vendor.cerebrum.blocks.validation", "ValidationBlock"),
    "vector_search": ("vendor.cerebrum.blocks.vector_search", "VectorSearchBlock"),
    "version": ("vendor.cerebrum.blocks.version", "VersionBlock"),
    "version_diff": ("vendor.cerebrum.blocks.version_diff", "VersionDiffBlock"),
    "workbench": ("vendor.cerebrum.blocks.workbench", "WorkbenchBlock"),
    "workflow": ("vendor.cerebrum.blocks.workflow", "WorkflowBlock"),
}
def get_block(name):
    try:
        module_path, class_name = _BLOCK_DEFS[name]
    except KeyError:
        raise KeyError(f"block {name!r} is not vendored in this platform") from None
    return getattr(importlib.import_module(module_path), class_name)
class _LazyRegistry:
    def __contains__(self, name):
        return name in _BLOCK_DEFS
    def __getitem__(self, name):
        return get_block(name)
    def get(self, name, default=None):
        try:
            return get_block(name)
        except KeyError:
            return default
    def keys(self):
        return _BLOCK_DEFS.keys()
BLOCK_REGISTRY = _LazyRegistry()
