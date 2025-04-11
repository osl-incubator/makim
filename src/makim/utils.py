"""Utility classes and functions for Makim."""


def kebab_to_camel(kebab_str: str) -> str:
    """Convert kebab-case to camelCase."""
    words = kebab_str.split('-')
    camel = words[0]
    for word in words[1:]:
        camel += word.capitalize()
    return camel
