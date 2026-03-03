import os
import sys
import time
from email.message import EmailMessage

# Add the project root to sys.path so we can import 'source'
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from source.email_filtering import process_and_filter_email
from source.email_handler import add_to_queue

def test_filtering():
    # Test 1: No Matter ID
    msg1 = EmailMessage()
    msg1.set_content("No matter id here.")
    res1 = process_and_filter_email(msg1, "No Subject", "Sender 1")
    assert res1 is None, f"Expected None, got {res1}"

    # Test 2: Matter ID in Body, has Category in Subject (Exhibits)
    msg2 = EmailMessage()
    msg2.set_content("This is about M-12345.")
    res2 = process_and_filter_email(msg2, "Attached are some Exhibits", "Sender 2")
    assert res2 is not None
    assert res2["matter_id"] == "M12345"
    assert res2["category"] == "Exhibits"
    assert res2["subject"] == "Attached are some Exhibits"
    
    # Test 3: Matter ID in Subject, Category in Body (Transcripts)
    msg4 = EmailMessage()
    msg4.set_content("Please find the transcripts below.")
    res4 = process_and_filter_email(msg4, "Subject with M99999", "Sender 4")
    assert res4 is not None
    assert res4["matter_id"] == "M99999"
    assert res4["category"] == "Transcripts"

    # Test 4: UNKNOWN Category (should return None + trigger email send mock)
    msg5 = EmailMessage()
    msg5.set_content("Here is some random file for M-55555.")
    res5 = process_and_filter_email(msg5, "Unknown File", "Sender 5")
    # This should return None because category is UNKNOWN and an email fired off instead.
    assert res5 is None, f"Expected None for UNKNOWN category, got {res5}"
    
    print("Filtering tests passed!")
    
    # testing queue
    if res2: add_to_queue(res2)
    if res4: add_to_queue(res4)
    
    print("Waiting for queue processing...")
    time.sleep(5)
    print("Test complete.")

if __name__ == "__main__":
    test_filtering()
