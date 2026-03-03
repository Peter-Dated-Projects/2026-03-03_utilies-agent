
import re
from email.utils import parseaddr
from source.category_extractor import get_document_category
from source.email_sender import send_unknown_category_email

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


def extract_sender_name(sender: str) -> str:
    """
    Best-effort extraction of a human-readable first name from the From address.

    Strategy:
      1. Parse the display name from "Display Name <email@host>" format.
         Take the first word of the display name.
      2. Fall back to the part of the email address before the @ symbol,
         splitting on dots/underscores/hyphens to get the first token.
      3. Capitalise the result.

    Examples:
      "John Smith <j.smith@example.com>" -> "John"
      "j.smith@example.com"              -> "J"
      "john_doe@example.com"             -> "John"
    """
    display, addr = parseaddr(sender)

    if display:
        first = display.strip().split()[0]
        return first.capitalize()

    # Fall back to email prefix
    local = addr.split("@")[0] if "@" in addr else addr
    first = re.split(r'[._\-]+', local)[0]
    return first.capitalize() if first else "User"

def get_email_body(msg):
    """
    Extracts the plaintext body from an email message.
    """
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                charset = part.get_content_charset() or "utf-8"
                payload = part.get_payload(decode=True)
                if payload:
                    body += payload.decode(charset, errors="ignore")
    else:
        content_type = msg.get_content_type()
        if content_type == "text/plain":
            charset = msg.get_content_charset() or "utf-8"
            payload = msg.get_payload(decode=True)
            if payload:
                body += payload.decode(charset, errors="ignore")
    return body

def process_and_filter_email(msg, subject, sender):
    """
    Processes an email message to determine if it is relevant.
    Returns a dictionary with email data if relevant, None otherwise.
    """
    body = get_email_body(msg)
    
    # Check subject first, then body
    matter_id = extract_matter_id(subject)
    if not matter_id:
        matter_id = extract_matter_id(body)
        
    if matter_id:
        category = get_document_category(subject, body)
        
        if category == "UNKNOWN":
            send_unknown_category_email(sender, subject, matter_id)
            return {"matter_id": matter_id, "status": "missing_category"}
            
        return {
            "matter_id": matter_id,
            "category": category,
            "subject": subject,
            "sender": sender,
            "sender_name": extract_sender_name(sender),
            "body": body
        }
        
    return None