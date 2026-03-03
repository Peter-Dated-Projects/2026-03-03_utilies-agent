import queue
import threading
import time
from source.logger import get_logger

logger = get_logger(__name__)

email_queue = queue.Queue()

def process_email_job(email_data):
    """
    Simulates processing an individual email.
    """
    matter_id = email_data.get("matter_id")
    subject = email_data.get("subject")
    
    logger.info("Handling email for Matter ID: %s | Subject: %s", matter_id, subject)
    # Simulate processing time
    time.sleep(2)
    logger.info("Finished handling email for Matter ID: %s", matter_id)

def worker():
    """
    Background worker that continuously processes emails from the queue.
    Blocks when the queue is empty.
    """
    logger.info("Email handler worker thread started, waiting for jobs...")
    while True:
        try:
            # Block until an item is available
            email_data = email_queue.get()
            process_email_job(email_data)
        except Exception as e:
            logger.error("Error processing email job: %s", e)
        finally:
            # Mark the task as done
            email_queue.task_done()

def add_to_queue(email_data):
    """
    Adds an email data dictionary to the handler queue.
    """
    email_queue.put(email_data)
    logger.debug("Added email to queue for Matter ID: %s", email_data.get("matter_id"))

# Start the background worker thread as a daemon thread
worker_thread = threading.Thread(target=worker, daemon=True)
worker_thread.start()
