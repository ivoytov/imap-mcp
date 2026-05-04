# imap_mcp.py
import os
import imaplib
import email
from email.policy import default
from mcp.server.fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("IMAP Mail Reader")

@mcp.tool()
def get_latest_emails(limit: int = 3) -> str:
    """Fetch the latest emails from the inbox using IMAP."""
    username = os.environ.get("IMAP_USERNAME")
    app_password = os.environ.get("IMAP_APP_PASSWORD")
    
    if not username or not app_password:
        return "Error: IMAP credentials not set in environment."

    try:
        # Connect to Gmail IMAP
        mail = imaplib.IMAP4_SSL('imap.gmail.com')
        mail.login(username, app_password)
        mail.select('inbox')

        # Search for all emails
        status, messages = mail.search(None, 'ALL')
        email_ids = messages[0].split()
        
        # Get the latest 'limit' emails
        latest_ids = email_ids[-limit:]
        results = []

        for e_id in latest_ids:
            status, msg_data = mail.fetch(e_id, '(RFC822)')
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1], policy=default)
                    subject = msg['subject']
                    sender = msg['from']
                    results.append(f"From: {sender} | Subject: {subject}")

        mail.logout()
        return "\n".join(results) if results else "No emails found."

    except Exception as e:
        return f"IMAP connection failed: {str(e)}"

def main() -> None:
    mcp.run()