"""Wire this product's capabilities into the kernel's S12 domain specs.

app.domain_ops is the Factory's contract: it runs ten named outcomes through
execute_action. It reads SPECS/DEFAULT_CAPABILITY, which are the product's
declaration -- filled here from app.models and app.jobs, once.
"""

from __future__ import annotations


def install() -> None:
    from app import domain_ops, jobs, kernel_bridge

    if getattr(domain_ops, "_PRODUCT_REGISTRY_INSTALLED", False):
        return
    domain_ops.SPECS.update(kernel_bridge.specs())
    domain_ops.DEFAULT_CAPABILITY = jobs.CAPABILITY_IDS[0]
    domain_ops.SAMPLE = {}
    domain_ops._PRODUCT_REGISTRY_INSTALLED = True


install()
