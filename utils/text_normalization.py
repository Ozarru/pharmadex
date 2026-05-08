"""
Utilities for text normalization in search functionality.
Allows accent-insensitive and case-insensitive searching.
Example: 'Dègue' -> 'degue', 'ÉMILE' -> 'emile'
"""
import unicodedata


def normalize_search_text(text: str) -> str:
    """
    Normalizes text for search by removing accents and converting to lowercase.

    Args:
        text: The text to normalize

    Returns:
        Normalized text (no accents, lowercase)

    Examples:
        >>> normalize_search_text('Dègue')
        'degue'
        >>> normalize_search_text('ÉMILE')
        'emile'
        >>> normalize_search_text('Côte d\'Ivoire')
        "cote d'ivoire"
    """
    if not text:
        return ''

    # Decompose Unicode characters (separates letters from their accents)
    # NFD = Normalization Form Canonical Decomposition
    nfd = unicodedata.normalize('NFD', text)

    # Filter combining characters (accents)
    # Mn = Nonspacing_Mark (Unicode category for accents)
    without_accents = ''.join(
        char for char in nfd
        if unicodedata.category(char) != 'Mn'
    )

    # Convert to lowercase
    return without_accents.lower()