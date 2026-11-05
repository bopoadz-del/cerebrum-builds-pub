"""Vendored cerebrum block registry (verification tree)."""
import importlib
_BLOCK_DEFS = {
    "agriculture_v2": ("vendor.cerebrum.blocks.agriculture_v2", "AgricultureBlockV2"),
    "analytics": ("vendor.cerebrum.blocks.analytics", "AnalyticsBlock"),
    "approval_rules": ("vendor.cerebrum.blocks.approval_rules", "ApprovalRulesBlock"),
    "audit": ("vendor.cerebrum.blocks.audit", "AuditBlock"),
    "audit_chain": ("vendor.cerebrum.blocks.audit_chain", "AuditChainBlock"),
    "auth": ("vendor.cerebrum.blocks.auth", "AuthBlock"),
    "billing": ("vendor.cerebrum.blocks.billing", "BillingBlock"),
    "capture": ("vendor.cerebrum.blocks.capture", "CaptureBlock"),
    "config": ("vendor.cerebrum.blocks.config", "ConfigBlock"),
    "cpm_engine": ("vendor.cerebrum.blocks.cpm_engine", "CpmEngineBlock"),
    "dashboard": ("vendor.cerebrum.blocks.dashboard", "DashboardBlock"),
    "database": ("vendor.cerebrum.blocks.database", "DatabaseBlock"),
    "document_engine": ("vendor.cerebrum.blocks.document_engine", "DocumentEngineBlock"),
    "email": ("vendor.cerebrum.blocks.email", "EmailBlock"),
    "estate_registry": ("vendor.cerebrum.blocks.estate_registry", "EstateRegistryBlock"),
    "evidence_chain": ("vendor.cerebrum.blocks.evidence_chain", "EvidenceChainBlock"),
    "finance_canonical_model": ("vendor.cerebrum.blocks.finance_canonical_model", "FinanceCanonicalModelBlock"),
    "finance_coa_governance": ("vendor.cerebrum.blocks.finance_coa_governance", "FinanceCoAGovernanceBlock"),
    "finance_data_quality": ("vendor.cerebrum.blocks.finance_data_quality", "FinanceDataQualityBlock"),
    "finance_reconciliation": ("vendor.cerebrum.blocks.finance_reconciliation", "FinanceReconciliationBlock"),
    "formula_executor": ("vendor.cerebrum.blocks.formula_executor", "FormulaExecutorBlock"),
    "governance_gate": ("vendor.cerebrum.blocks.governance_gate", "GovernanceGateBlock"),
    "ingestion_provenance": ("vendor.cerebrum.blocks.ingestion_provenance", "IngestionProvenanceBlock"),
    "knowledge": ("vendor.cerebrum.blocks.knowledge", "KnowledgeBlock"),
    "loyalty_referrals": ("vendor.cerebrum.blocks.loyalty_referrals", "LoyaltyReferralsBlock"),
    "marker": ("vendor.cerebrum.blocks.marker", "MarkerBlock"),
    "memory": ("vendor.cerebrum.blocks.memory", "MemoryBlock"),
    "multi_tenant_rbac": ("vendor.cerebrum.blocks.multi_tenant_rbac", "MultiTenantRbacBlock"),
    "notification": ("vendor.cerebrum.blocks.notification", "NotificationBlock"),
    "orchestrator": ("vendor.cerebrum.blocks.orchestrator", "OrchestratorBlock"),
    "payment_split": ("vendor.cerebrum.blocks.payment_split", "PaymentSplitBlock"),
    "pdf": ("vendor.cerebrum.blocks.pdf", "PDFBlock"),
    "portfolio_rollup": ("vendor.cerebrum.blocks.portfolio_rollup", "PortfolioRollupBlock"),
    "search": ("vendor.cerebrum.blocks.search", "SearchBlock"),
    "transaction_state_machine": ("vendor.cerebrum.blocks.transaction_state_machine", "TransactionStateMachineBlock"),
    "user_auth": ("vendor.cerebrum.blocks.user_auth", "UserAuthBlock"),
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
