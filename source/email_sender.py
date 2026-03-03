import smtplib
from email.message import EmailMessage
import os
from source.logger import get_logger

logger = get_logger(__name__)

def send_unknown_category_email(to_address, original_subject, matter_id):
    """
    Sends an email to the user indicating the category could not be determined.
    """
    email_address = os.environ.get("EMAIL")
    password = os.environ.get("PASSWORD")
    
    if not email_address or not password:
        logger.error("EMAIL or PASSWORD not configured for sending notifications.")
        return
        
    msg = EmailMessage()
    msg['Subject'] = f"Re: {original_subject} - Clarification Required"
    msg['From'] = email_address
    msg['To'] = to_address
    
    body = (
        f"Hello,\n\n"
        f"We received your request regarding Matter ID {matter_id}.\n"
        f"However, we were unable to determine the document category from your email.\n\n"
        f"Please reply with one of the following exact categories so we can process your request:\n"
        f"- Exhibits\n"
        f"- Key Documents\n"
        f"- Other Documents\n"
        f"- Transcripts\n"
        f"- Recordings\n\n"
        f"Thank you."
    )
    
    msg.set_content(body)
    
    try:
        # Example using Gmail SMTP. Update if using a different provider.
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(email_address, password)
            smtp.send_message(msg)
            logger.info("Clarification email sent to %s for Matter %s", to_address, matter_id)
    except Exception as e:
        logger.error("Failed to send clarification email: %s", e)
