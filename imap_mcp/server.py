# imap_mcp.py
import os
import imaplib
import email
import smtplib
from email.policy import default
from email.message import EmailMessage
from mcp.server.fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("IMAP Mail Reader")


def _get_credentials() -> tuple[str | None, str | None]:
    username = os.environ.get("IMAP_USERNAME")
    app_password = os.environ.get("IMAP_APP_PASSWORD")
    return username, app_password

@mcp.tool()
def get_latest_emails(limit: int = 3) -> str:
    """Fetch the latest emails from the inbox using IMAP."""
    username, app_password = _get_credentials()
    
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


@mcp.tool()
def list_inbox_uids(limit: int = 20) -> str:
    """List latest inbox UIDs to help other tools (for example archive_email)."""
    username, app_password = _get_credentials()

    if not username or not app_password:
        return "Error: IMAP credentials not set in environment."

    if limit <= 0:
        return "Error: limit must be greater than 0."

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(username, app_password)
        mail.select("inbox")

        status, data = mail.uid("SEARCH", None, "ALL")
        if status != "OK":
            mail.logout()
            return "Failed to list inbox UIDs."

        uid_bytes = data[0] if data else b""
        uids = uid_bytes.split() if uid_bytes else []
        latest = uids[-limit:]

        mail.logout()
        return " ".join(uid.decode("utf-8") for uid in latest) if latest else "No emails found."
    except Exception as e:
        return f"IMAP UID listing failed: {str(e)}"


@mcp.tool()
def send_email(to: str, subject: str, body: str, cc: str = "") -> str:
    """Send an email with Gmail SMTP using IMAP_USERNAME and IMAP_APP_PASSWORD."""
    username, app_password = _get_credentials()

    if not username or not app_password:
        return "Error: IMAP credentials not set in environment."

    if not to.strip():
        return "Error: recipient email cannot be empty."

    try:
        msg = EmailMessage()
        msg["From"] = username
        msg["To"] = to
        if cc.strip():
            msg["Cc"] = cc
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(username, app_password)
            smtp.send_message(msg)

        return f"Email sent to {to}" + (f" (cc: {cc})." if cc.strip() else ".")
    except Exception as e:
        return f"SMTP send failed: {str(e)}"


@mcp.tool()
def archive_email(message_uid: str) -> str:
    """
    Archive an email in Gmail by removing the Inbox label.
    This matches Gmail's archive behavior (message remains in All Mail).
    """
    username, app_password = _get_credentials()

    if not username or not app_password:
        return "Error: IMAP credentials not set in environment."

    if not message_uid.strip():
        return "Error: message_uid cannot be empty."

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(username, app_password)
        mail.select("inbox")

        status, _ = mail.uid("STORE", message_uid, "-X-GM-LABELS", "(\\Inbox)")
        mail.logout()

        if status != "OK":
            return f"Archive failed for UID {message_uid}."

        return f"Archived email UID {message_uid}."
    except Exception as e:
        return f"IMAP archive failed: {str(e)}"


def main() -> None:
    mcp.run()
