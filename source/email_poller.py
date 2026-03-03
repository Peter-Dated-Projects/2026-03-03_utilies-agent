import time
import imaplib
import email
from email.header import decode_header
from source.logger import get_logger
from source.email_filtering import process_and_filter_email
from source.email_handler import add_to_queue

logger = get_logger(__name__)



def check_inbox(imap):
    """Check the inbox for unseen messages."""
    status, _ = imap.select("INBOX")
    if status != "OK":
        logger.error("Failed to select INBOX.")
        return

    # Fetch unseen messages
    status, unread_msg_nums = imap.search(None, "UNSEEN")
    if status == "OK":
        unread_list = unread_msg_nums[0].split()
        if unread_list:
            logger.info("Found %d new unread messages.", len(unread_list))
            
            # Process in chunks of 50 to avoid sending an IMAP command that is too long
            chunk_size = 50
            for i in range(0, len(unread_list), chunk_size):
                chunk = unread_list[i:i + chunk_size]
                # Join message IDs with a comma to fetch multiple at once (in one single IMAP swoop)
                nums_str = b",".join(chunk)
                
                status, msg_data = imap.fetch(nums_str, "(RFC822)")
                if status == "OK":
                    for response_part in msg_data:
                        if isinstance(response_part, tuple):
                            msg = email.message_from_bytes(response_part[1])
                            subject_header = msg["Subject"]
                            
                            if subject_header:
                                subject, encoding = decode_header(subject_header)[0]
                                if isinstance(subject, bytes):
                                    subject = subject.decode(encoding if encoding else "utf-8", errors="ignore")
                            else:
                                subject = "(No Subject)"
                                
                            sender = msg.get("From", "(Unknown Sender)")
                            logger.info("  -> From: %s | Subject: %s", sender, subject)
                            
                            email_data = process_and_filter_email(msg, subject, sender)
                            if email_data:
                                if email_data.get("status") == "missing_category":
                                    logger.info("  => Category unknown. Clarified with sender for Matter ID: %s", email_data["matter_id"])
                                else:
                                    add_to_queue(email_data)
                                    logger.info("  => Relevant email found and queued for Matter ID: %s", email_data["matter_id"])
                            else:
                                logger.debug("  => Irrelevant email, ignored.")
        else:
            logger.debug("No new messages.")

def start_polling(email_address, password, poll_interval=60):
    """Continuously poll for new emails."""
    logger.info("Starting email polling for %s (checking every %ds)...", email_address, poll_interval)
    
    while True:
        try:
            # Connect to IMAP server (Gmail is used here as an example)
            imap = imaplib.IMAP4_SSL("imap.gmail.com")
            imap.login(email_address, password)
            
            check_inbox(imap)
            
            # Close connection properly after each poll
            imap.close()
            imap.logout()
        except imaplib.IMAP4.error as e:
            logger.error("Authentication or IMAP error: %s", e)
        except Exception as e:
            logger.exception("Unexpected error during polling.")
        
        time.sleep(poll_interval)
