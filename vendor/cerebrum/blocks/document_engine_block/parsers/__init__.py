"""Store-unwired document_engine.parsers.

Without it, a product dies on
``No module named vendor.cerebrum.blocks.document_engine.parsers``.
Text comes from the caller payload (prepare_block_input already sets it).
"""


def parse(*args, **kwargs):
    return ""


def extract_text(*args, **kwargs):
    return ""


class Parser:
    def parse(self, *args, **kwargs):
        return ""

    def extract_text(self, *args, **kwargs):
        return ""
