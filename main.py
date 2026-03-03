import os
import time
import imaplib
import email
from email.header import decode_header

from dotenv import load_dotenv
load_dotenv()


def check_inbox(imap):
    """Check the inbox for unseen messages."""
    status, _ = imap.select("INBOX")
    if status != "OK":
        print("Failed to select INBOX.")
        return

    # Fetch unseen messages
    status, unread_msg_nums = imap.search(None, "UNSEEN")
    if status == "OK":
        unread_list = unread_msg_nums[0].split()
        if unread_list:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Found {len(unread_list)} new unread messages.")
            for num in unread_list:
                status, msg_data = imap.fetch(num, "(RFC822)")
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
                            print(f"  -> From: {sender} | Subject: {subject}")
        else:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] No new messages.")

def start_polling(email_address, password, poll_interval=60):
    """Continuously poll for new emails."""
    print(f"Starting email polling for {email_address} (checking every {poll_interval}s)...")
    
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
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Authentication or IMAP error: {e}")
        except Exception as e:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Unexpected error during polling: {e}")
        
        time.sleep(poll_interval)

def main():
    email_address = os.environ.get("EMAIL")
    password = os.environ.get("PASSWORD")

    if not email_address or not password:
        print("Error: EMAIL or PASSWORD environment variables not set in .env.local.")
        return

    try:
        # Defaults to a 5-second polling interval
        start_polling(email_address, password, poll_interval=5)
    except KeyboardInterrupt:
        print("\nPolling stopped by user.")

if __name__ == "__main__":
    main()
