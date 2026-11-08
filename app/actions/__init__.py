"""Capability handlers.

Modules are imported by app.routes on demand; nothing is re-exported here,
so importing a handler never pulls in the HTTP surface (and vice versa).
"""
