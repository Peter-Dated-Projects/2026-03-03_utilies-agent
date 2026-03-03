import os
from dotenv import load_dotenv
from source.email_poller import start_polling
from source.logger import get_logger

load_dotenv()

logger = get_logger(__name__)

def main():
    email_address = os.environ.get("EMAIL")
    password = os.environ.get("PASSWORD")

    if not email_address or not password:
        logger.error("EMAIL or PASSWORD environment variables not set in .env.local.")
        return

    try:
        # Defaults to a 5-second polling interval
        start_polling(email_address, password, poll_interval=5)
    except KeyboardInterrupt:
        logger.info("\nPolling stopped by user.")

if __name__ == "__main__":
    main()
