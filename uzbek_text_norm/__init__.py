"""Self-contained Uzbek text normalization for fair ASR scoring.

Quick start::

    from uzbek_text_norm import normalize_reference, normalize_hypothesis

    ref = normalize_reference("2024-yil, G'alaba!")
    hyp = normalize_hypothesis("Ғалаба")        # Cyrillic model output

See ``uzbek_text_norm.core`` for the full configurable API.
"""

from .core import (
    DEFAULT_TAGS,
    OKINA,
    UzbekNormalizer,
    clean,
    cyrillic_to_latin,
    normalize,
    normalize_hypothesis,
    normalize_reference,
    number_to_ordinal_words,
    number_to_words,
    spell_numbers_in_text,
)

__version__ = "0.2.0"

__all__ = [
    "UzbekNormalizer",
    "normalize",
    "normalize_reference",
    "normalize_hypothesis",
    "clean",
    "cyrillic_to_latin",
    "spell_numbers_in_text",
    "number_to_words",
    "number_to_ordinal_words",
    "DEFAULT_TAGS",
    "OKINA",
    "__version__",
]
