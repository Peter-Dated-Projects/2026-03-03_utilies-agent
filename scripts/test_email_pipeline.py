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
    assert res5 is None, f"Expected None for UNKNOWN category, got {res5}"
    
    # Test 5: Singular form and improper casing (Exhibit instead of Exhibits, KeY DoCumEnt)
    msg6 = EmailMessage()
    msg6.set_content("Attached is the eXhiBit for M-77777.")
    res6 = process_and_filter_email(msg6, "some KeY DoCumEnt attached", "Sender 6")
    
    assert res6 is not None
    assert res6["matter_id"] == "M77777"
    # The system returns the official category name from the CATEGORIES list
    assert res6["category"] == "Key Documents", f"Expected 'Key Documents', got {res6['category']}"

    # Test 6: Another Singular form test in Body
    msg7 = EmailMessage()
    msg7.set_content("Here is the transcript for M-88888.")
    res7 = process_and_filter_email(msg7, "No category here", "Sender 7")
    
    assert res7 is not None
    assert res7["category"] == "Transcripts"
    
    print("Filtering tests passed!")
    
    # testing queue
    if res2: add_to_queue(res2)
    if res4: add_to_queue(res4)
    if res6: add_to_queue(res6)
    if res7: add_to_queue(res7)
    
    print("Waiting for queue processing...")
    time.sleep(10)
    print("Test complete.")

if __name__ == "__main__":
    test_filtering()
