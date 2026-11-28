"""Capability handler modules.

Each module is imported by its own name (``app.actions.<capability>``) by the
router.  There are deliberately no eager re-exports here: importing this
package must not import every handler and its blocks.
"""
