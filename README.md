# Senpilot Regulatory Agent Challenge

This repository contains a Python-based email bot designed to automate the retrieval of regulatory documents from the Nova Scotia Utility and Review Board (UARB) database. It acts as a data ingestion pipeline, built for the Senpilot Software Engineering Intern (S26) challenge.

## What It Does

The agent listens for incoming emails requesting specific regulatory documents, retrieves them from the web, and emails them back to the user as a compressed archive along with a metadata summary.

**Core Capabilities:**

1. **Email Parsing:** Reads incoming emails to extract a specific "Matter Number" (e.g., `M12205`) and a "Document Type" (e.g., `Exhibits`, `Key Documents`, `Other Documents`).

2. **Automated Scraping:** Navigates the UARB database (FileMaker WebDirect interface), searches for the requested matter, and extracts key metadata (Title, Category, Filing Dates, and file counts per tab).

3. **File Extraction & Compression:** Downloads up to 10 documents from the requested category and compresses them into a single `.zip` file.

4. **Automated Response:** Replies to the original sender with the requested `.zip` attachment and a summary of the matter's metadata.

## How It Works

The system is built using an asynchronous, polling architecture to ensure reliability and bypass complex cloud email routing configurations.

* **Ingestion (IMAP):** The bot continuously polls a dedicated Gmail inbox every 15 seconds using Python's `imaplib`. This avoids aggressive rate-limiting while maintaining a responsive user experience.

* **Processing (Web Automation):** Once a valid request is found, it uses web automation (e.g., Selenium/Playwright) to interact with the UARB portal. It inputs the Matter Number, navigates the UI to find the correct document tab, and clicks the "Go Get It" buttons to download the files.

* **Delivery (SMTP):** Downloaded files are zipped using Python's `zipfile` module. The bot formats a reply string containing the scraped metadata and sends the email back to the user via `smtplib` over TLS.

* **Hosting:** The bot is designed to run as a continuous Background Worker on Render.

## Usage / Demo

To interact with the agent:

1. Send an email to: `thefreedomfightersguild@gmail.com`

2. In the body or subject, specify the Matter Number and Document Type.

   * *Example:* "Hi Agent, Can you give me Other Documents files from M12205? Thanks!"

3. Wait approximately 1-2 minutes for the agent to scrape the database, download the files, and reply with the ZIP attachment.

## Local Setup

To run this bot locally:

1. Clone the repository and install dependencies (`pip install -r requirements.txt`).

2. Set the following Environment Variables:

   * `EMAIL_ACCOUNT`: Your dedicated bot Gmail address.

   * `APP_PASSWORD`: Your Gmail App Password (bypasses 2FA).

3. Run the main polling script: `python main.py`.