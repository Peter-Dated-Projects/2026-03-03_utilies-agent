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
    """
    text_lower = text.lower()
    for cat in CATEGORIES:
        if cat.lower() in text_lower:
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
