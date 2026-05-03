"""
app/services/email_integration/providers.py

OAuth + email fetching for Gmail (Google) and Outlook (Microsoft Graph).

Each provider implements:
  - get_auth_url()     → redirect user to OAuth consent screen
  - exchange_code()    → swap authorization code for tokens
  - refresh_access()   → use refresh token to get a new access token
  - fetch_messages()   → get recent emails (incremental via cursor)
  - get_user_email()   → get the authenticated user's email address

Designed for basic Phase 1 — no full 5-year scan yet.
Fetches last 90 days of job-related emails on first sync,
then incremental on subsequent syncs.
"""

from __future__ import annotations

import structlog
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

import httpx

from app.config import settings

logger = structlog.get_logger(__name__)

# Gmail API scopes — read-only access to messages
GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
]

# Microsoft Graph scopes — read-only mail
MICROSOFT_SCOPES = [
    "Mail.Read",
    "User.Read",
    "offline_access",
]


@dataclass
class OAuthTokens:
    access_token: str
    refresh_token: str | None
    expires_at: datetime | None


@dataclass
class EmailMessage:
    """Normalized email message from any provider."""
    message_id: str
    sender: str
    subject: str
    date: datetime
    snippet: str  # first ~200 chars


class EmailProvider(ABC):
    """Abstract base for email providers."""

    @abstractmethod
    def get_auth_url(self, redirect_uri: str, state: str | None = None) -> str: ...

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthTokens: ...

    @abstractmethod
    async def refresh_access(self, refresh_token: str) -> OAuthTokens: ...

    @abstractmethod
    async def fetch_messages(
        self, access_token: str, cursor: str | None = None, max_results: int = 100,
    ) -> tuple[list[EmailMessage], str | None]: ...

    @abstractmethod
    async def get_user_email(self, access_token: str) -> str: ...


# ── Gmail Provider ────────────────────────────────────────────────────────────

class GmailProvider(EmailProvider):
    """Gmail via Google OAuth2 + Gmail API."""

    OAUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
    TOKEN_URL = "https://oauth2.googleapis.com/token"
    GMAIL_API = "https://gmail.googleapis.com/gmail/v1"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

    def get_auth_url(self, redirect_uri: str, state: str | None = None) -> str:
        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(GMAIL_SCOPES),
            "access_type": "offline",
            "prompt": "consent",
        }
        if state:
            params["state"] = state
        _qs = "&".join(f"{k}={httpx.URL('', params={k: v}).params}" for k, v in params.items())
        # Use httpx to build proper query string
        return str(httpx.URL(self.OAUTH_URL, params=params))

    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthTokens:
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            })
            resp.raise_for_status()
            data = resp.json()

        from datetime import UTC, timedelta
        expires_at = None
        if "expires_in" in data:
            expires_at = datetime.now(UTC) + timedelta(seconds=data["expires_in"])

        return OAuthTokens(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=expires_at,
        )

    async def refresh_access(self, refresh_token: str) -> OAuthTokens:
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data={
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            })
            resp.raise_for_status()
            data = resp.json()

        from datetime import UTC, timedelta
        expires_at = None
        if "expires_in" in data:
            expires_at = datetime.now(UTC) + timedelta(seconds=data["expires_in"])

        return OAuthTokens(
            access_token=data["access_token"],
            refresh_token=refresh_token,  # Google doesn't always return a new refresh token
            expires_at=expires_at,
        )

    async def get_user_email(self, access_token: str) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                self.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            return resp.json()["email"]

    async def fetch_messages(
        self, access_token: str, cursor: str | None = None, max_results: int = 100,
    ) -> tuple[list[EmailMessage], str | None]:
        """
        Fetch job-related emails from Gmail.
        Uses Gmail search query to filter for application-related emails.
        Returns (messages, new_cursor) where cursor is historyId for incremental sync.
        """
        headers = {"Authorization": f"Bearer {access_token}"}

        # Search for job-application-related emails
        query = (
            "subject:(application OR interview OR offer OR rejection OR "
            '"thank you for applying" OR "we received your application" OR '
            '"schedule an interview" OR "pleased to offer" OR '
            '"unfortunately" OR "moved forward" OR "next steps")'
        )

        async with httpx.AsyncClient() as client:
            # List message IDs matching our query
            params: dict = {"q": query, "maxResults": max_results}
            if cursor:
                # For incremental: use historyId-based list
                # But for simplicity in Phase 1, we just re-query
                pass

            resp = await client.get(
                f"{self.GMAIL_API}/users/me/messages",
                headers=headers,
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

            message_ids = [m["id"] for m in data.get("messages", [])]
            if not message_ids:
                return [], cursor

            # Fetch each message's metadata (batch would be better but keep simple)
            messages = []
            for msg_id in message_ids[:max_results]:
                msg_resp = await client.get(
                    f"{self.GMAIL_API}/users/me/messages/{msg_id}",
                    headers=headers,
                    params={"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
                )
                if msg_resp.status_code != 200:
                    continue

                msg_data = msg_resp.json()
                headers_list = msg_data.get("payload", {}).get("headers", [])
                header_map = {h["name"]: h["value"] for h in headers_list}

                # Parse date
                from email.utils import parsedate_to_datetime
                try:
                    email_date = parsedate_to_datetime(header_map.get("Date", ""))
                except Exception:
                    from datetime import UTC
                    email_date = datetime.now(UTC)

                messages.append(EmailMessage(
                    message_id=msg_id,
                    sender=header_map.get("From", ""),
                    subject=header_map.get("Subject", ""),
                    date=email_date,
                    snippet=msg_data.get("snippet", "")[:200],
                ))

            # Use the profile's historyId as cursor for next sync
            profile_resp = await client.get(
                f"{self.GMAIL_API}/users/me/profile",
                headers=headers,
            )
            new_cursor = None
            if profile_resp.status_code == 200:
                new_cursor = str(profile_resp.json().get("historyId", ""))

        return messages, new_cursor

    async def fetch_all_messages(
        self, access_token: str, max_results: int = 500, years: int = 3,
    ) -> list[EmailMessage]:
        """
        Fetch ALL sent+received emails from the past N years for deep intelligence.
        No keyword filter — we want everything to analyze patterns.
        """
        headers = {"Authorization": f"Bearer {access_token}"}
        from datetime import UTC, timedelta
        cutoff = datetime.now(UTC) - timedelta(days=years * 365)
        after_str = cutoff.strftime("%Y/%m/%d")

        all_messages: list[EmailMessage] = []

        async with httpx.AsyncClient(timeout=30) as client:
            # Fetch SENT emails (reveals application patterns)
            for query, label in [
                (f"after:{after_str} in:sent", "sent"),
                (f"after:{after_str} in:inbox", "inbox"),
            ]:
                params: dict = {"q": query, "maxResults": min(max_results, 250)}
                try:
                    resp = await client.get(
                        f"{self.GMAIL_API}/users/me/messages",
                        headers=headers,
                        params=params,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                except Exception:
                    continue

                message_ids = [m["id"] for m in data.get("messages", [])]

                for msg_id in message_ids:
                    if any(m.message_id == msg_id for m in all_messages):
                        continue
                    try:
                        msg_resp = await client.get(
                            f"{self.GMAIL_API}/users/me/messages/{msg_id}",
                            headers=headers,
                            params={"format": "metadata", "metadataHeaders": ["From", "To", "Subject", "Date"]},
                        )
                        if msg_resp.status_code != 200:
                            continue
                        msg_data = msg_resp.json()
                        headers_list = msg_data.get("payload", {}).get("headers", [])
                        header_map = {h["name"]: h["value"] for h in headers_list}

                        from email.utils import parsedate_to_datetime
                        try:
                            email_date = parsedate_to_datetime(header_map.get("Date", ""))
                        except Exception:
                            email_date = datetime.now(UTC)

                        all_messages.append(EmailMessage(
                            message_id=msg_id,
                            sender=header_map.get("From", ""),
                            subject=header_map.get("Subject", ""),
                            date=email_date,
                            snippet=msg_data.get("snippet", "")[:300],
                        ))
                    except Exception:
                        continue

        return all_messages


# ── Outlook Provider ──────────────────────────────────────────────────────────

class OutlookProvider(EmailProvider):
    """Outlook via Microsoft Identity Platform + Graph API."""

    OAUTH_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    GRAPH_API = "https://graph.microsoft.com/v1.0"

    def get_auth_url(self, redirect_uri: str, state: str | None = None) -> str:
        params = {
            "client_id": settings.microsoft_client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(MICROSOFT_SCOPES),
            "response_mode": "query",
            "prompt": "select_account",
        }
        if state:
            params["state"] = state
        return str(httpx.URL(self.OAUTH_URL, params=params))

    async def exchange_code(self, code: str, redirect_uri: str) -> OAuthTokens:
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data={
                "client_id": settings.microsoft_client_id,
                "client_secret": settings.microsoft_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "scope": " ".join(MICROSOFT_SCOPES),
            })
            resp.raise_for_status()
            data = resp.json()

        from datetime import UTC, timedelta
        expires_at = None
        if "expires_in" in data:
            expires_at = datetime.now(UTC) + timedelta(seconds=data["expires_in"])

        return OAuthTokens(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            expires_at=expires_at,
        )

    async def refresh_access(self, refresh_token: str) -> OAuthTokens:
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.TOKEN_URL, data={
                "client_id": settings.microsoft_client_id,
                "client_secret": settings.microsoft_client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
                "scope": " ".join(MICROSOFT_SCOPES),
            })
            resp.raise_for_status()
            data = resp.json()

        from datetime import UTC, timedelta
        expires_at = None
        if "expires_in" in data:
            expires_at = datetime.now(UTC) + timedelta(seconds=data["expires_in"])

        return OAuthTokens(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", refresh_token),
            expires_at=expires_at,
        )

    async def get_user_email(self, access_token: str) -> str:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.GRAPH_API}/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("mail") or data.get("userPrincipalName", "")

    async def fetch_messages(
        self, access_token: str, cursor: str | None = None, max_results: int = 100,
    ) -> tuple[list[EmailMessage], str | None]:
        """Fetch recent emails from Outlook via Microsoft Graph."""
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=30) as client:
            params: dict = {
                "$top": max_results,
                "$select": "id,from,subject,receivedDateTime,bodyPreview",
                "$orderby": "receivedDateTime desc",
            }

            resp = await client.get(
                f"{self.GRAPH_API}/me/messages",
                headers=headers,
                params=params,
            )
            resp.raise_for_status()
            data = resp.json()

        return self._parse_graph_messages(data), None

    async def fetch_all_messages(
        self, access_token: str, max_results: int = 500, years: int = 3,
    ) -> list[EmailMessage]:
        """Fetch ALL emails from past N years for deep intelligence."""
        headers = {"Authorization": f"Bearer {access_token}"}
        from datetime import UTC, timedelta
        cutoff = (datetime.now(UTC) - timedelta(days=years * 365)).isoformat()

        all_messages: list[EmailMessage] = []

        async with httpx.AsyncClient(timeout=30) as client:
            # Fetch inbox
            for folder in ["inbox", "sentitems"]:
                params: dict = {
                    "$top": min(max_results, 250),
                    "$select": "id,from,toRecipients,subject,receivedDateTime,bodyPreview",
                    "$orderby": "receivedDateTime desc",
                    "$filter": f"receivedDateTime ge {cutoff}",
                }
                try:
                    resp = await client.get(
                        f"{self.GRAPH_API}/me/mailFolders/{folder}/messages",
                        headers=headers,
                        params=params,
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    all_messages.extend(self._parse_graph_messages(data))
                except Exception:
                    continue

        return all_messages

    def _parse_graph_messages(self, data: dict) -> list[EmailMessage]:
        """Parse Microsoft Graph message response into EmailMessage list."""
        messages = []
        for msg in data.get("value", []):
            from_data = msg.get("from", {}).get("emailAddress", {})
            sender = from_data.get("address", "")

            try:
                email_date = datetime.fromisoformat(
                    msg["receivedDateTime"].replace("Z", "+00:00")
                )
            except Exception:
                from datetime import UTC
                email_date = datetime.now(UTC)

            messages.append(EmailMessage(
                message_id=msg["id"],
                sender=sender,
                subject=msg.get("subject", ""),
                date=email_date,
                snippet=(msg.get("bodyPreview") or "")[:300],
            ))
        return messages


# ── Factory ───────────────────────────────────────────────────────────────────

def get_provider(provider: str) -> EmailProvider:
    if provider == "gmail":
        return GmailProvider()
    elif provider == "outlook":
        return OutlookProvider()
    else:
        raise ValueError(f"Unknown email provider: {provider}")
