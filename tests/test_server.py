import imaplib
import base64

from imap_mcp.server import (
    archive_email,
    fetch_attachment,
    get_email_by_uid,
    get_latest_emails,
    list_inbox_uids,
    send_email,
)


class FakeIMAPSuccess:
    def login(self, username, app_password):
        return "OK", [b"logged in"]

    def select(self, mailbox):
        return "OK", [b"1"]

    def search(self, charset, criteria):
        return "OK", [b"1 2 3"]

    def fetch(self, e_id, query):
        messages = {
            b"2": (
                b"From: Bob <bob@example.com>\n"
                b"Subject: Latest 2\n"
                b"\n"
                b"Body"
            ),
            b"3": (
                b"From: Alice <alice@example.com>\n"
                b"Subject: Latest 3\n"
                b"\n"
                b"Body"
            ),
        }
        return "OK", [(b"RFC822", messages[e_id])]

    def logout(self):
        return "OK", [b"bye"]


class FakeIMAPFailure:
    def __init__(self, *_args, **_kwargs):
        raise imaplib.IMAP4.error("auth failed")


class FakeIMAPHtmlOnly:
    def login(self, username, app_password):
        return "OK", [b"logged in"]

    def select(self, mailbox):
        return "OK", [b"1"]

    def search(self, charset, criteria):
        return "OK", [b"1"]

    def fetch(self, e_id, query):
        message = (
            b"From: Html Sender <html@example.com>\n"
            b"Subject: Html Message\n"
            b"MIME-Version: 1.0\n"
            b"Content-Type: text/html; charset=utf-8\n"
            b"\n"
            b"<h1>Hello</h1><p><strong>World</strong></p>"
        )
        return "OK", [(b"RFC822", message)]

    def logout(self):
        return "OK", [b"bye"]


class FakeIMAPUIDList:
    def login(self, username, app_password):
        return "OK", [b"logged in"]

    def select(self, mailbox):
        return "OK", [b"1"]

    def uid(self, command, charset, criteria):
        assert command == "SEARCH"
        assert charset is None
        assert criteria == "ALL"
        return "OK", [b"101 102 103 104 105"]

    def logout(self):
        return "OK", [b"bye"]


class FakeIMAPUIDListEmpty:
    def login(self, username, app_password):
        return "OK", [b"logged in"]

    def select(self, mailbox):
        return "OK", [b"1"]

    def uid(self, command, charset, criteria):
        assert command == "SEARCH"
        return "OK", [b""]

    def logout(self):
        return "OK", [b"bye"]


class FakeIMAPUIDListFailure:
    def login(self, username, app_password):
        return "OK", [b"logged in"]

    def select(self, mailbox):
        return "OK", [b"1"]

    def uid(self, *_args):
        return "NO", [b"error"]

    def logout(self):
        return "OK", [b"bye"]


class FakeIMAPArchiveSuccess:
    def login(self, username, app_password):
        return "OK", [b"logged in"]

    def select(self, mailbox):
        return "OK", [b"1"]

    def uid(self, command, message_uid, labels_op, labels):
        assert command == "STORE"
        assert labels_op == "-X-GM-LABELS"
        assert labels == "(\\Inbox)"
        assert message_uid == "12345"
        return "OK", [b"updated"]

    def logout(self):
        return "OK", [b"bye"]


class FakeIMAPArchiveFailure:
    def login(self, username, app_password):
        return "OK", [b"logged in"]

    def select(self, mailbox):
        return "OK", [b"1"]

    def uid(self, *_args):
        return "NO", [b"error"]

    def logout(self):
        return "OK", [b"bye"]


class FakeIMAPAttachmentSuccess:
    def login(self, username, app_password):
        return "OK", [b"logged in"]

    def select(self, mailbox):
        return "OK", [b"1"]

    def uid(self, command, message_uid, fetch_query):
        assert command == "FETCH"
        assert fetch_query == "(RFC822)"
        assert message_uid == "12345"
        msg = (
            b"From: Sender <sender@example.com>\n"
            b"Subject: Has attachment\n"
            b"MIME-Version: 1.0\n"
            b"Content-Type: multipart/mixed; boundary=\"b1\"\n"
            b"\n"
            b"--b1\n"
            b"Content-Type: text/plain; charset=utf-8\n"
            b"\n"
            b"Body text\n"
            b"--b1\n"
            b"Content-Type: text/plain\n"
            b"Content-Disposition: attachment; filename=\"notes.txt\"\n"
            b"Content-Transfer-Encoding: base64\n"
            b"\n"
            + base64.b64encode(b"attachment-content")
            + b"\n"
            b"--b1--\n"
        )
        return "OK", [(b"RFC822", msg)]

    def logout(self):
        return "OK", [b"bye"]


class FakeIMAPAttachmentNoAttachment:
    def login(self, username, app_password):
        return "OK", [b"logged in"]

    def select(self, mailbox):
        return "OK", [b"1"]

    def uid(self, *_args):
        msg = (
            b"From: Sender <sender@example.com>\n"
            b"Subject: No attachment\n"
            b"\n"
            b"body"
        )
        return "OK", [(b"RFC822", msg)]

    def logout(self):
        return "OK", [b"bye"]


class FakeIMAPAttachmentFetchFailure:
    def login(self, username, app_password):
        return "OK", [b"logged in"]

    def select(self, mailbox):
        return "OK", [b"1"]

    def uid(self, *_args):
        return "NO", [b"error"]

    def logout(self):
        return "OK", [b"bye"]


class FakeIMAPGetByUIDSuccess:
    def login(self, username, app_password):
        return "OK", [b"logged in"]

    def select(self, mailbox):
        return "OK", [b"1"]

    def uid(self, command, message_uid, fetch_query):
        assert command == "FETCH"
        assert fetch_query == "(RFC822)"
        assert message_uid == "777"
        msg = (
            b"From: Uid Sender <uid@example.com>\n"
            b"Subject: UID Message\n"
            b"\n"
            b"UID body"
        )
        return "OK", [(b"RFC822", msg)]

    def logout(self):
        return "OK", [b"bye"]


class FakeIMAPGetByUIDHtmlOnly:
    def login(self, username, app_password):
        return "OK", [b"logged in"]

    def select(self, mailbox):
        return "OK", [b"1"]

    def uid(self, command, message_uid, fetch_query):
        assert command == "FETCH"
        assert fetch_query == "(RFC822)"
        assert message_uid == "888"
        msg = (
            b"From: Html UID <html-uid@example.com>\n"
            b"Subject: HTML UID Message\n"
            b"MIME-Version: 1.0\n"
            b"Content-Type: text/html; charset=utf-8\n"
            b"\n"
            b"<h1>UID Hello</h1><p><strong>UID World</strong></p>"
        )
        return "OK", [(b"RFC822", msg)]

    def logout(self):
        return "OK", [b"bye"]


class FakeIMAPGetByUIDFailure:
    def login(self, username, app_password):
        return "OK", [b"logged in"]

    def select(self, mailbox):
        return "OK", [b"1"]

    def uid(self, *_args):
        return "NO", [b"error"]

    def logout(self):
        return "OK", [b"bye"]


class FakeIMAPGetByUIDNoData:
    def login(self, username, app_password):
        return "OK", [b"logged in"]

    def select(self, mailbox):
        return "OK", [b"1"]

    def uid(self, *_args):
        return "OK", [b""]

    def logout(self):
        return "OK", [b"bye"]


class FakeSMTPSuccess:
    def __init__(self, host, port, timeout=None):
        assert host == "smtp.gmail.com"
        assert port == 587
        assert timeout == 12.0
        self.logged_in = False
        self.tls_started = False
        self.sent_to = None
        self.sent_cc = None
        self.sent_subject = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def ehlo(self):
        return 250, b"hello"

    def starttls(self, context=None):
        assert context is not None
        self.tls_started = True
        return 220, b"ready for tls"

    def login(self, username, app_password):
        assert self.tls_started is True
        self.logged_in = True
        return 235, b"2.7.0 Accepted"

    def send_message(self, msg):
        self.sent_to = msg["To"]
        self.sent_cc = msg["Cc"]
        self.sent_subject = msg["Subject"]


class FakeSMTPFailure:
    def __init__(self, *_args, **_kwargs):
        raise RuntimeError("smtp unavailable")


class FakeSMTPTimeout:
    def __init__(self, *_args, **_kwargs):
        raise TimeoutError("timed out")


def test_get_latest_emails_missing_credentials(monkeypatch):
    monkeypatch.delenv("IMAP_USERNAME", raising=False)
    monkeypatch.delenv("IMAP_APP_PASSWORD", raising=False)

    result = get_latest_emails()

    assert result == "Error: IMAP credentials not set in environment."


def test_get_latest_emails_success(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr("imap_mcp.server.imaplib.IMAP4_SSL", lambda *_args, **_kwargs: FakeIMAPSuccess())

    result = get_latest_emails(limit=2)
    assert "From: Bob <bob@example.com>" in result
    assert "Subject: Latest 2" in result
    assert "Body-Type: text/plain" in result
    assert "Body:\nBody" in result
    assert "From: Alice <alice@example.com>" in result
    assert "Subject: Latest 3" in result


def test_get_latest_emails_legacy_summary_mode(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr("imap_mcp.server.imaplib.IMAP4_SSL", lambda *_args, **_kwargs: FakeIMAPSuccess())

    result = get_latest_emails(limit=2, include_body=False)
    lines = result.splitlines()

    assert len(lines) == 2
    assert "From: Bob <bob@example.com> | Subject: Latest 2" in lines
    assert "From: Alice <alice@example.com> | Subject: Latest 3" in lines


def test_get_latest_emails_html_converted_to_markdown(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr("imap_mcp.server.imaplib.IMAP4_SSL", lambda *_args, **_kwargs: FakeIMAPHtmlOnly())

    monkeypatch.setattr("imap_mcp.server.convert_html_to_markdown", lambda html: "# Hello\n\n**World**")

    result = get_latest_emails(limit=1)

    assert "Body-Type: text/markdown" in result
    assert "# Hello" in result
    assert "**World**" in result


def test_get_latest_emails_html_without_conversion_returns_html(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr("imap_mcp.server.imaplib.IMAP4_SSL", lambda *_args, **_kwargs: FakeIMAPHtmlOnly())

    result = get_latest_emails(limit=1, convert_html_to_md=False)

    assert "Body-Type: text/html" in result
    assert "<h1>Hello</h1><p><strong>World</strong></p>" in result


def test_get_latest_emails_imap_failure(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "wrong-password")
    monkeypatch.setattr("imap_mcp.server.imaplib.IMAP4_SSL", FakeIMAPFailure)

    result = get_latest_emails()

    assert result == "IMAP connection failed: auth failed"


def test_get_latest_emails_invalid_limit(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr("imap_mcp.server.imaplib.IMAP4_SSL", lambda *_args, **_kwargs: FakeIMAPSuccess())

    result = get_latest_emails(limit=0)
    assert result == "Error: limit must be greater than 0."


def test_get_email_by_uid_missing_credentials(monkeypatch):
    monkeypatch.delenv("IMAP_USERNAME", raising=False)
    monkeypatch.delenv("IMAP_APP_PASSWORD", raising=False)

    result = get_email_by_uid("777")

    assert result == "Error: IMAP credentials not set in environment."


def test_get_email_by_uid_empty_uid(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")

    result = get_email_by_uid("")

    assert result == "Error: message_uid cannot be empty."


def test_get_email_by_uid_success(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr(
        "imap_mcp.server.imaplib.IMAP4_SSL",
        lambda *_args, **_kwargs: FakeIMAPGetByUIDSuccess(),
    )

    result = get_email_by_uid("777")

    assert "UID: 777" in result
    assert "From: Uid Sender <uid@example.com>" in result
    assert "Subject: UID Message" in result
    assert "Body-Type: text/plain" in result
    assert "Body:\nUID body" in result


def test_get_email_by_uid_summary_mode(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr(
        "imap_mcp.server.imaplib.IMAP4_SSL",
        lambda *_args, **_kwargs: FakeIMAPGetByUIDSuccess(),
    )

    result = get_email_by_uid("777", include_body=False)

    assert result == "UID: 777 | From: Uid Sender <uid@example.com> | Subject: UID Message"


def test_get_email_by_uid_html_converted_to_markdown(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr(
        "imap_mcp.server.imaplib.IMAP4_SSL",
        lambda *_args, **_kwargs: FakeIMAPGetByUIDHtmlOnly(),
    )
    monkeypatch.setattr("imap_mcp.server.convert_html_to_markdown", lambda html: "# UID Hello\n\n**UID World**")

    result = get_email_by_uid("888")

    assert "UID: 888" in result
    assert "Body-Type: text/markdown" in result
    assert "# UID Hello" in result
    assert "**UID World**" in result


def test_get_email_by_uid_fetch_failure(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr(
        "imap_mcp.server.imaplib.IMAP4_SSL",
        lambda *_args, **_kwargs: FakeIMAPGetByUIDFailure(),
    )

    result = get_email_by_uid("777")

    assert result == "Email fetch failed for UID 777."


def test_get_email_by_uid_no_message_data(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr(
        "imap_mcp.server.imaplib.IMAP4_SSL",
        lambda *_args, **_kwargs: FakeIMAPGetByUIDNoData(),
    )

    result = get_email_by_uid("777")

    assert result == "No message data returned for UID 777."


def test_list_inbox_uids_missing_credentials(monkeypatch):
    monkeypatch.delenv("IMAP_USERNAME", raising=False)
    monkeypatch.delenv("IMAP_APP_PASSWORD", raising=False)

    result = list_inbox_uids()

    assert result == "Error: IMAP credentials not set in environment."


def test_list_inbox_uids_invalid_limit(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")

    result = list_inbox_uids(limit=0)

    assert result == "Error: limit must be greater than 0."


def test_list_inbox_uids_success(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr(
        "imap_mcp.server.imaplib.IMAP4_SSL",
        lambda *_args, **_kwargs: FakeIMAPUIDList(),
    )

    result = list_inbox_uids(limit=3)

    assert result == "103 104 105"


def test_list_inbox_uids_empty(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr(
        "imap_mcp.server.imaplib.IMAP4_SSL",
        lambda *_args, **_kwargs: FakeIMAPUIDListEmpty(),
    )

    result = list_inbox_uids()

    assert result == "No emails found."


def test_list_inbox_uids_search_failure(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr(
        "imap_mcp.server.imaplib.IMAP4_SSL",
        lambda *_args, **_kwargs: FakeIMAPUIDListFailure(),
    )

    result = list_inbox_uids()

    assert result == "Failed to list inbox UIDs."


def test_send_email_missing_credentials(monkeypatch):
    monkeypatch.delenv("IMAP_USERNAME", raising=False)
    monkeypatch.delenv("IMAP_APP_PASSWORD", raising=False)

    result = send_email("to@example.com", "Hello", "Body")

    assert result == "Error: IMAP credentials not set in environment."


def test_send_email_success(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr("imap_mcp.server.smtplib.SMTP", FakeSMTPSuccess)

    result = send_email("to@example.com", "Subject", "Body")

    assert result == "Email sent to to@example.com."


def test_send_email_success_with_cc(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr("imap_mcp.server.smtplib.SMTP", FakeSMTPSuccess)

    result = send_email("to@example.com", "Subject", "Body", cc="copy@example.com")

    assert result == "Email sent to to@example.com (cc: copy@example.com)."


def test_send_email_smtp_failure(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr("imap_mcp.server.smtplib.SMTP", FakeSMTPFailure)

    result = send_email("to@example.com", "Subject", "Body")

    assert result == "SMTP send failed: smtp unavailable"


def test_send_email_smtp_timeout(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr("imap_mcp.server.smtplib.SMTP", FakeSMTPTimeout)

    result = send_email("to@example.com", "Subject", "Body")

    assert result == "SMTP send failed: timed out."


def test_archive_email_missing_credentials(monkeypatch):
    monkeypatch.delenv("IMAP_USERNAME", raising=False)
    monkeypatch.delenv("IMAP_APP_PASSWORD", raising=False)

    result = archive_email("12345")

    assert result == "Error: IMAP credentials not set in environment."


def test_archive_email_success(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr(
        "imap_mcp.server.imaplib.IMAP4_SSL",
        lambda *_args, **_kwargs: FakeIMAPArchiveSuccess(),
    )

    result = archive_email("12345")

    assert result == "Archived email UID 12345."


def test_archive_email_store_failure(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr(
        "imap_mcp.server.imaplib.IMAP4_SSL",
        lambda *_args, **_kwargs: FakeIMAPArchiveFailure(),
    )

    result = archive_email("12345")

    assert result == "Archive failed for UID 12345."


def test_fetch_attachment_missing_credentials(monkeypatch):
    monkeypatch.delenv("IMAP_USERNAME", raising=False)
    monkeypatch.delenv("IMAP_APP_PASSWORD", raising=False)

    result = fetch_attachment("12345")
    assert result == "Error: IMAP credentials not set in environment."


def test_fetch_attachment_empty_uid(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")

    result = fetch_attachment("")
    assert result == "Error: message_uid cannot be empty."


def test_fetch_attachment_invalid_index(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")

    result = fetch_attachment("12345", attachment_index=0)
    assert result == "Error: attachment_index must be greater than 0."


def test_fetch_attachment_success_default_index(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr(
        "imap_mcp.server.imaplib.IMAP4_SSL",
        lambda *_args, **_kwargs: FakeIMAPAttachmentSuccess(),
    )

    result = fetch_attachment("12345")
    expected_payload = base64.b64encode(b"attachment-content").decode("ascii")

    assert "UID: 12345" in result
    assert "Filename: notes.txt" in result
    assert "Content-Type: text/plain" in result
    assert "Content-Transfer: base64" in result
    assert f"Content-Base64: {expected_payload}" in result


def test_fetch_attachment_success_by_filename(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr(
        "imap_mcp.server.imaplib.IMAP4_SSL",
        lambda *_args, **_kwargs: FakeIMAPAttachmentSuccess(),
    )

    result = fetch_attachment("12345", filename="notes.txt")

    assert "Filename: notes.txt" in result
    assert "Content-Base64:" in result


def test_fetch_attachment_not_found_by_filename(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr(
        "imap_mcp.server.imaplib.IMAP4_SSL",
        lambda *_args, **_kwargs: FakeIMAPAttachmentSuccess(),
    )

    result = fetch_attachment("12345", filename="missing.pdf")
    assert "Attachment 'missing.pdf' not found for UID 12345." in result


def test_fetch_attachment_index_out_of_range(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr(
        "imap_mcp.server.imaplib.IMAP4_SSL",
        lambda *_args, **_kwargs: FakeIMAPAttachmentSuccess(),
    )

    result = fetch_attachment("12345", attachment_index=2)
    assert result == "Attachment index 2 out of range for UID 12345. Found 1 attachment(s)."


def test_fetch_attachment_none_found(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr(
        "imap_mcp.server.imaplib.IMAP4_SSL",
        lambda *_args, **_kwargs: FakeIMAPAttachmentNoAttachment(),
    )

    result = fetch_attachment("12345")
    assert result == "No attachments found for UID 12345."


def test_fetch_attachment_fetch_failure(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr(
        "imap_mcp.server.imaplib.IMAP4_SSL",
        lambda *_args, **_kwargs: FakeIMAPAttachmentFetchFailure(),
    )

    result = fetch_attachment("12345")
    assert result == "Attachment fetch failed for UID 12345."
