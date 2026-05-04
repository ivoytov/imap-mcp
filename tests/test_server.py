import imaplib

from imap_mcp.server import archive_email, get_latest_emails, list_inbox_uids, send_email


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


class FakeSMTPSuccess:
    def __init__(self, host, port):
        assert host == "smtp.gmail.com"
        assert port == 465
        self.logged_in = False
        self.sent_to = None
        self.sent_cc = None
        self.sent_subject = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def login(self, username, app_password):
        self.logged_in = True
        return 235, b"2.7.0 Accepted"

    def send_message(self, msg):
        self.sent_to = msg["To"]
        self.sent_cc = msg["Cc"]
        self.sent_subject = msg["Subject"]


class FakeSMTPFailure:
    def __init__(self, *_args, **_kwargs):
        raise RuntimeError("smtp unavailable")


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
    lines = result.splitlines()

    assert len(lines) == 2
    assert "From: Bob <bob@example.com> | Subject: Latest 2" in lines
    assert "From: Alice <alice@example.com> | Subject: Latest 3" in lines


def test_get_latest_emails_imap_failure(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "wrong-password")
    monkeypatch.setattr("imap_mcp.server.imaplib.IMAP4_SSL", FakeIMAPFailure)

    result = get_latest_emails()

    assert result == "IMAP connection failed: auth failed"


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
    monkeypatch.setattr("imap_mcp.server.smtplib.SMTP_SSL", FakeSMTPSuccess)

    result = send_email("to@example.com", "Subject", "Body")

    assert result == "Email sent to to@example.com."


def test_send_email_success_with_cc(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr("imap_mcp.server.smtplib.SMTP_SSL", FakeSMTPSuccess)

    result = send_email("to@example.com", "Subject", "Body", cc="copy@example.com")

    assert result == "Email sent to to@example.com (cc: copy@example.com)."


def test_send_email_smtp_failure(monkeypatch):
    monkeypatch.setenv("IMAP_USERNAME", "user@example.com")
    monkeypatch.setenv("IMAP_APP_PASSWORD", "app-password")
    monkeypatch.setattr("imap_mcp.server.smtplib.SMTP_SSL", FakeSMTPFailure)

    result = send_email("to@example.com", "Subject", "Body")

    assert result == "SMTP send failed: smtp unavailable"


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
