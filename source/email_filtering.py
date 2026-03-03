
import re

def extract_matter_id(text):
    """
    Checks a string for a Matter ID.
    Supports formats: M12345 or M-12345 (uppercase or lowercase).
    Returns the ID in uppercase without the hyphen if found, otherwise returns None.
    """
    # Pattern: \b for word boundary, M literal, -? for optional hyphen, \d{5} for 5 digits
    pattern = r'\bM-?\d{5}\b'
    
    # Search for the pattern
    match = re.search(pattern, text, re.IGNORECASE)
    
    if match:
        # Standardize output by removing hyphen and converting to uppercase
        return match.group(0).replace('-', '').upper()
    
    return None