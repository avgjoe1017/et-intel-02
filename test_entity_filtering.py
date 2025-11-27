#!/usr/bin/env python
"""Test entity filtering logic."""

import re

def is_valid_discovered_entity(name: str, entity_type: str) -> bool:
    """Filter out invalid discovered entities (emojis, single characters, etc.)."""
    
    # Filter out emojis and emoji-only strings
    emoji_pattern = re.compile(
        "["
        "\U0001F300-\U0001F9FF"  # Miscellaneous Symbols and Pictographs
        "\U00002600-\U000026FF"  # Miscellaneous Symbols
        "\U00002700-\U000027BF"  # Dingbats
        "\U0001F600-\U0001F64F"  # Emoticons
        "\U0001F680-\U0001F6FF"  # Transport and Map Symbols
        "\U0001F1E0-\U0001F1FF"  # Flags
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "]+"
    )
    
    # Check if name is only emojis
    if emoji_pattern.fullmatch(name.strip()):
        return False
    
    # Filter out single characters or very short names
    name_clean = name.strip()
    if len(name_clean) < 2:
        return False
    
    # Filter out names that are only punctuation or numbers
    if not re.search(r'[a-zA-Z]', name_clean):
        return False
    
    # Filter out common non-entity words
    common_words = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
        'been', 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
        'would', 'could', 'should', 'may', 'might', 'must', 'can'
    }
    if name_clean.lower() in common_words:
        return False
    
    return True

# Test cases from your discovered entities
test_cases = [
    ("🙏", "PERSON", False),  # Emoji only
    ("🎂", "PERSON", False),  # Emoji only
    ("😍", "PERSON", False),  # Emoji only
    ("💚🩷", "PERSON", False),  # Multiple emojis
    ("Michael B. Jordan", "PERSON", True),  # Valid entity
    ("Kate", "PERSON", True),  # Valid (even if ambiguous)
    ("Colleen", "PERSON", True),  # Valid
    ("Colleen Hoover", "PERSON", True),  # Valid full name
    ("a", "PERSON", False),  # Too short
    ("the", "PERSON", False),  # Common word
    ("123", "PERSON", False),  # Numbers only
    ("", "PERSON", False),  # Empty
]

print("Entity Filtering Test Results:")
print("=" * 60)

for name, entity_type, expected in test_cases:
    result = is_valid_discovered_entity(name, entity_type)
    status = "✅" if result == expected else "❌"
    action = "KEEP" if result else "FILTER"
    print(f"{status} {name:20} ({entity_type:6}) -> {action:6} (expected: {'KEEP' if expected else 'FILTER'})")

print("\n" + "=" * 60)
print("Filter will exclude emojis, short names, and common words.")
print("Valid entities like 'Michael B. Jordan' and 'Colleen' will be kept.")

