"""Small compatibility surface the vendored Store blocks import.

The vendored blocks read ``app.core.file_crypto`` for decrypt-at-rest. This
platform stores plaintext documents in its own storage root, so the
plaintext path is the honest implementation: it yields the file unchanged.
"""
