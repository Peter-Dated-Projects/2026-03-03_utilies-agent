import time
from email.message import EmailMessage
from source.email_filtering import process_and_filter_email
from source.email_handler import add_to_queue

def test_filtering():
    # Test 1: No Matter ID
    msg1 = EmailMessage()
    msg1.set_content("No matter id here.")
    res1 = process_and_filter_email(msg1, "No Subject", "Sender 1")
    assert res1 is None, f"Expected None, got {res1}"

    # Test 2: Matter ID in Body
    msg2 = EmailMessage()
    msg2.set_content("This is about M-12345.")
    res2 = process_and_filter_email(msg2, "Subject no matter id", "Sender 2")
    assert res2 is not None
    assert res2["matter_id"] == "M12345"
    assert res2["subject"] == "Subject no matter id"
    
    # Test 3: Matter ID in Subject
    msg4 = EmailMessage()
    msg4.set_content("Body no matter id")
    res4 = process_and_filter_email(msg4, "Subject with M99999", "Sender 4")
    assert res4 is not None
    assert res4["matter_id"] == "M99999"

    print("Filtering tests passed!")
    
    # testing queue
    if res2: add_to_queue(res2)
    if res4: add_to_queue(res4)
    
    print("Waiting for queue processing...")
    time.sleep(5)
    print("Test complete.")

if __name__ == "__main__":
    test_filtering()
