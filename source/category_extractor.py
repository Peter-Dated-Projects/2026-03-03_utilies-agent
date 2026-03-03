import os
import re
from source.logger import get_logger

logger = get_logger(__name__)

# Allowed categories
CATEGORIES = [
    "Exhibits",
    "Key Documents",
    "Other Documents",
    "Transcripts",
    "Recordings"
]

def extract_category_regex(text):
    """
    Attempts to find a matching category strictly using simple regex/substring rules.
    Matches both singular and plural forms.
    """
    text_lower = text.lower()
    for cat in CATEGORIES:
        # Create a singular base by removing trailing 's' if present
        base_cat = cat[:-1] if cat.endswith('s') else cat
        # Match the base word with an optional 's' at the end
        pattern = r'\b' + re.escape(base_cat.lower()) + r'(?:s)?\b'
        if re.search(pattern, text_lower):
            return cat
    return None

def get_document_category(subject, body):
    """
    Categorization logic:
    Tries regex on the subject, then body.
    """
    # 1. Regex on Subject
    cat = extract_category_regex(subject)
    if cat:
        return cat
        
    # 2. Regex on Body
    cat = extract_category_regex(body)
    if cat:
        return cat
        
    return "UNKNOWN"
