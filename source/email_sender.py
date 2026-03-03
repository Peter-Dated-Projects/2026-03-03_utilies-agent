import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr
from source.logger import get_logger

logger = get_logger(__name__)


def _get_smtp_credentials() -> tuple[str, str] | tuple[None, None]:
    """Return (email, password) from env, or (None, None) if not configured."""
    email_address = os.environ.get("EMAIL")
    password = os.environ.get("PASSWORD")
    if not email_address or not password:
        logger.error("EMAIL or PASSWORD environment variables are not set.")
        return None, None
    return email_address, password


def _from_header(email_address: str) -> str:
    """Build a display-name From header using APP_NAME from env if set."""
    app_name = os.environ.get("APP_NAME", "")
    return formataddr((app_name, email_address)) if app_name else email_address


def send_unknown_category_email(to_address: str, original_subject: str, matter_id: str) -> None:
    """
    Sends an email to the user indicating the category could not be determined.
    Currently mocked — logs the email content without actually sending via SMTP.
    """
    email_address, password = _get_smtp_credentials()
    if not email_address:
        return

    msg = EmailMessage()
    msg["Subject"] = f"Re: {original_subject} - Clarification Required"
    msg["From"] = _from_header(email_address)
    msg["To"] = to_address

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
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(email_address, password)
            smtp.send_message(msg)
        logger.info("Sent clarification email to: %s for Matter: %s", to_address, matter_id)
    except Exception as e:
        logger.error("Failed to send clarification email to %s: %s", to_address, e)


def send_result_email(
    to_address: str,
    matter_id: str,
    category: str,
    summary: str,
    zip_path: str,
) -> bool:
    """
    Send the completed job result to the requester.

    Attaches the zip archive and includes the LLM summary as the email body.

    Args:
        to_address: Recipient email address.
        matter_id:  e.g. "M12205"
        category:   e.g. "Exhibits"
        summary:    Plain-text LLM summary to use as the body.
        zip_path:   Absolute path to the zip file to attach.

    Returns:
        True on success, False on failure.
    """
    email_address, password = _get_smtp_credentials()
    if not email_address:
        return False

    msg = EmailMessage()
    msg["Subject"] = f"[UARB Agent] Matter {matter_id} – {category} Summary"
    msg["From"] = _from_header(email_address)
    msg["To"] = to_address
    msg.set_content(summary)

    logger.info(
        "Result Email Content Output:\n" + "=" * 60 +
        f"\nSubject: {msg['Subject']}\nFrom: {msg['From']}\nTo: {msg['To']}\n\n{summary}\n" +
        "=" * 60
    )

    if zip_path:
        try:
            with open(zip_path, "rb") as f:
                zip_data = f.read()
            zip_filename = os.path.basename(zip_path)
            msg.add_attachment(zip_data, maintype="application", subtype="zip", filename=zip_filename)
            logger.debug("Attached zip: %s (%d bytes)", zip_filename, len(zip_data))
        except Exception as e:
            logger.error("Failed to read zip file '%s': %s", zip_path, e)
            return False

    # Send via SMTP
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(email_address, password)
            smtp.send_message(msg)
        logger.info(
            "Result email sent to %s for Matter ID: %s / %s",
            to_address, matter_id, category
        )
        return True
    except Exception as e:
        logger.error("Failed to send result email to %s: %s", to_address, e)
        return False
