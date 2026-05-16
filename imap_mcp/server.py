# imap_mcp.py
import os
import imaplib
import email
import smtplib
import socket
import ssl
import base64
from typing import Any
from email.policy import default
from email.message import EmailMessage
from html_to_markdown import convert as convert_html_to_markdown
from mcp.server.fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("IMAP Mail Reader")


def _get_credentials() -> tuple[str | None, str | None]:
    username = os.environ.get("IMAP_USERNAME")
    app_password = os.environ.get("IMAP_APP_PASSWORD")
    return username, app_password


def _get_network_timeout() -> float:
    raw = os.environ.get("EMAIL_NETWORK_TIMEOUT_SEC", "12")
    try:
        value = float(raw)
        return value if value > 0 else 12.0
    except ValueError:
        return 12.0


def _decode_part(part: EmailMessage) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        text_payload = part.get_payload()
        return text_payload if isinstance(text_payload, str) else ""
    charset = part.get_content_charset() or "utf-8"
    return payload.decode(charset, errors="replace")


def _html_to_markdown(html: str) -> tuple[str, str]:
    converted = convert_html_to_markdown(html)
    if not isinstance(converted, str):
        converted = str(converted)
    return converted, ""


def _extract_body(msg: EmailMessage, convert_html_to_md: bool = True) -> tuple[str, str, str]:
    """
    Returns (body_text, body_type, conversion_note).
    body_type is one of: text/plain, text/markdown, text/html, empty.
    """
    plain_text: str | None = None
    html_text: str | None = None

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            if (part.get("Content-Disposition") or "").lower().startswith("attachment"):
                continue

            content_type = part.get_content_type().lower()
            if content_type == "text/plain" and plain_text is None:
                plain_text = _decode_part(part)
            elif content_type == "text/html" and html_text is None:
                html_text = _decode_part(part)
    else:
        content_type = msg.get_content_type().lower()
        if content_type == "text/plain":
            plain_text = _decode_part(msg)
        elif content_type == "text/html":
            html_text = _decode_part(msg)

    if plain_text and plain_text.strip():
        return plain_text.strip(), "text/plain", ""

    if html_text and html_text.strip():
        if convert_html_to_md:
            markdown, note = _html_to_markdown(html_text)
            return markdown.strip(), "text/markdown", note
        return html_text.strip(), "text/html", ""

    return "", "empty", ""


def _collect_attachments(msg: EmailMessage) -> list[dict[str, Any]]:
    attachments: list[dict[str, Any]] = []
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        disposition = (part.get("Content-Disposition") or "").lower()
        filename = part.get_filename()
        if not filename and "attachment" not in disposition:
            continue
        payload = part.get_payload(decode=True) or b""
        attachments.append(
            {
                "filename": filename or "",
                "content_type": part.get_content_type(),
                "size_bytes": len(payload),
                "payload": payload,
            }
        )
    return attachments


def _format_email_result(
    msg: EmailMessage,
    include_body: bool,
    convert_html_to_md: bool,
    message_uid: str = "",
) -> str:
    subject = msg["subject"]
    sender = msg["from"]

    if include_body:
        body, body_type, conversion_note = _extract_body(
            msg,
            convert_html_to_md=convert_html_to_md,
        )
        parts = []
        if message_uid:
            parts.append(f"UID: {message_uid}")
        parts.extend(
            [
                f"From: {sender}",
                f"Subject: {subject}",
                f"Body-Type: {body_type}",
                f"Body:\n{body if body else '(empty body)'}",
            ]
        )
        if conversion_note:
            parts.append(f"Conversion-Note: {conversion_note}")
        return "\n".join(parts)

    if message_uid:
        return f"UID: {message_uid} | From: {sender} | Subject: {subject}"
    return f"From: {sender} | Subject: {subject}"


@mcp.tool()
def get_latest_emails(limit: int = 3, include_body: bool = True, convert_html_to_md: bool = True) -> str:
    """Fetch latest emails from inbox. By default includes message body and converts HTML body to Markdown."""
    username, app_password = _get_credentials()
    
    if not username or not app_password:
        return "Error: IMAP credentials not set in environment."

    try:
        # Connect to Gmail IMAP
        mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=_get_network_timeout())
        mail.login(username, app_password)
        mail.select('inbox')

        if limit <= 0:
            mail.logout()
            return "Error: limit must be greater than 0."

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
                    results.append(
                        _format_email_result(
                            msg,
                            include_body=include_body,
                            convert_html_to_md=convert_html_to_md,
                        )
                    )

        mail.logout()
        return "\n".join(results) if results else "No emails found."

    except (TimeoutError, socket.timeout):
        return "IMAP connection failed: timed out."
    except Exception as e:
        return f"IMAP connection failed: {str(e)}"


@mcp.tool()
def get_email_by_uid(message_uid: str, include_body: bool = True, convert_html_to_md: bool = True) -> str:
    """Fetch one email by IMAP UID. By default includes message body and converts HTML body to Markdown."""
    username, app_password = _get_credentials()

    if not username or not app_password:
        return "Error: IMAP credentials not set in environment."

    if not message_uid.strip():
        return "Error: message_uid cannot be empty."

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=_get_network_timeout())
        mail.login(username, app_password)
        mail.select("inbox")

        status, msg_data = mail.uid("FETCH", message_uid, "(RFC822)")
        if status != "OK":
            mail.logout()
            return f"Email fetch failed for UID {message_uid}."

        parsed_message: EmailMessage | None = None
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                parsed_message = email.message_from_bytes(response_part[1], policy=default)
                break

        if parsed_message is None:
            mail.logout()
            return f"No message data returned for UID {message_uid}."

        result = _format_email_result(
            parsed_message,
            include_body=include_body,
            convert_html_to_md=convert_html_to_md,
            message_uid=message_uid,
        )
        mail.logout()
        return result
    except (TimeoutError, socket.timeout):
        return "IMAP email fetch failed: timed out."
    except Exception as e:
        return f"IMAP email fetch failed: {str(e)}"


@mcp.tool()
def fetch_attachment(message_uid: str, filename: str = "", attachment_index: int = 1) -> str:
    """
    Fetch a single attachment by UID.
    This tool is explicit/opt-in and does not run as part of get_latest_emails.
    Returns attachment content as base64 plus metadata.
    """
    username, app_password = _get_credentials()

    if not username or not app_password:
        return "Error: IMAP credentials not set in environment."

    if not message_uid.strip():
        return "Error: message_uid cannot be empty."

    if attachment_index <= 0:
        return "Error: attachment_index must be greater than 0."

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=_get_network_timeout())
        mail.login(username, app_password)
        mail.select("inbox")

        status, msg_data = mail.uid("FETCH", message_uid, "(RFC822)")
        if status != "OK":
            mail.logout()
            return f"Attachment fetch failed for UID {message_uid}."

        parsed_message: EmailMessage | None = None
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                parsed_message = email.message_from_bytes(response_part[1], policy=default)
                break

        if parsed_message is None:
            mail.logout()
            return f"No message data returned for UID {message_uid}."

        attachments = _collect_attachments(parsed_message)
        if not attachments:
            mail.logout()
            return f"No attachments found for UID {message_uid}."

        selected: dict[str, Any] | None = None
        if filename.strip():
            for item in attachments:
                if item["filename"] == filename:
                    selected = item
                    break
            if selected is None:
                mail.logout()
                available = ", ".join(
                    item["filename"] or f"(unnamed-{i + 1})" for i, item in enumerate(attachments)
                )
                return f"Attachment '{filename}' not found for UID {message_uid}. Available: {available}"
        else:
            index = attachment_index - 1
            if index >= len(attachments):
                mail.logout()
                return (
                    f"Attachment index {attachment_index} out of range for UID {message_uid}. "
                    f"Found {len(attachments)} attachment(s)."
                )
            selected = attachments[index]

        payload: bytes = selected["payload"]
        payload_b64 = base64.b64encode(payload).decode("ascii")
        mail.logout()
        return "\n".join(
            [
                f"UID: {message_uid}",
                f"Filename: {selected['filename'] or '(unnamed)'}",
                f"Content-Type: {selected['content_type']}",
                f"Size-Bytes: {selected['size_bytes']}",
                "Content-Transfer: base64",
                f"Content-Base64: {payload_b64}",
            ]
        )
    except (TimeoutError, socket.timeout):
        return "IMAP attachment fetch failed: timed out."
    except Exception as e:
        return f"IMAP attachment fetch failed: {str(e)}"


@mcp.tool()
def list_inbox_uids(limit: int = 20) -> str:
    """List latest inbox UIDs to help other tools (for example archive_email)."""
    username, app_password = _get_credentials()

    if not username or not app_password:
        return "Error: IMAP credentials not set in environment."

    if limit <= 0:
        return "Error: limit must be greater than 0."

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=_get_network_timeout())
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
    except (TimeoutError, socket.timeout):
        return "IMAP UID listing failed: timed out."
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
        timeout = _get_network_timeout()
        msg = EmailMessage()
        msg["From"] = username
        msg["To"] = to
        if cc.strip():
            msg["Cc"] = cc
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP("smtp.gmail.com", 587, timeout=timeout) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            smtp.login(username, app_password)
            smtp.send_message(msg)

        return f"Email sent to {to}" + (f" (cc: {cc})." if cc.strip() else ".")
    except (TimeoutError, socket.timeout):
        return "SMTP send failed: timed out."
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
        mail = imaplib.IMAP4_SSL("imap.gmail.com", timeout=_get_network_timeout())
        mail.login(username, app_password)
        mail.select("inbox")

        status, _ = mail.uid("STORE", message_uid, "-X-GM-LABELS", "(\\Inbox)")
        mail.logout()

        if status != "OK":
            return f"Archive failed for UID {message_uid}."

        return f"Archived email UID {message_uid}."
    except (TimeoutError, socket.timeout):
        return "IMAP archive failed: timed out."
    except Exception as e:
        return f"IMAP archive failed: {str(e)}"


def main() -> None:
    mcp.run()
