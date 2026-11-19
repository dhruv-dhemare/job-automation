"""Gmail OAuth, draft creation, and explicit user-approved sending."""

import base64
from email.message import EmailMessage
from pathlib import Path

from config import settings

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def _service():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    credentials = None
    if settings.google_token.exists():
        credentials = Credentials.from_authorized_user_file(str(settings.google_token), SCOPES)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            if not settings.google_client_secret.exists():
                raise FileNotFoundError("Add Google OAuth desktop credentials as credentials.json")
            credentials = InstalledAppFlow.from_client_secrets_file(str(settings.google_client_secret), SCOPES).run_local_server(port=0)
        settings.google_token.write_text(credentials.to_json(), encoding="utf-8")
    return build("gmail", "v1", credentials=credentials)


def create_draft(to: str, subject: str, body: str, attachment: Path | None = None) -> str:
    if not to or "@" not in to:
        raise ValueError("A valid recipient email is required")
    message = EmailMessage()
    message["To"], message["Subject"] = to, subject
    message.set_content(body)
    if attachment and attachment.exists():
        message.add_attachment(attachment.read_bytes(), maintype="application", subtype="pdf", filename=attachment.name)
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    result = _service().users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
    return result["id"]


def send_draft(draft_id: str) -> str:
    result = _service().users().drafts().send(userId="me", body={"id": draft_id}).execute()
    return result.get("id", draft_id)
