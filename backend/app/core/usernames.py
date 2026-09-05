"""Username normalization helpers.

Staff usernames are a business login identifier and are case-insensitive.
Passwords remain case-sensitive.
"""


def normalize_username(value: str) -> str:
    return value.strip().lower()
