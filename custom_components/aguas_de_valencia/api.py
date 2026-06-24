"""Aguas de Valencia API client."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

import re

from .const import (
    COOKIE_GO_SESSION_ID,
    COOKIE_SESSION_ID,
    INVOICES_URL,
    LOGIN_ACTION_URL,
    LOGIN_PAGE_URL,
    READINGS_URL,
)

_LOGGER = logging.getLogger(__name__)

HEADERS_BASE = {
    "Accept": "*/*",
    "Accept-Language": "es-ES,es;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "DNT": "1",
    "Origin": "https://www.aguasdevalencia.es",
    "Pragma": "no-cache",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/148.0.0.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
    "sec-ch-ua": '"Chromium";v="148", "Google Chrome";v="148", "Not/A)Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


class AguasDeValenciaAuthError(Exception):
    """Authentication failed."""


class AguasDeValenciaApiError(Exception):
    """Generic API error."""


class AguasDeValenciaReading:
    """Represents a single metered reading."""

    def __init__(self, raw: dict[str, Any]) -> None:
        self.period: str = raw.get("Periodo", "")
        self.consumption_m3: int = int(raw.get("Consumo", 0))
        self.total_reading_m3: int = int(raw.get("Lectura", 0))
        self.reading_type: str = raw.get("TipoLectura", "").strip()
        # Parse MS-epoch timestamp: /Date(1708470000000)/
        fecha_raw: str = raw.get("Fecha", "")
        self.date: datetime | None = None
        if fecha_raw:
            try:
                ms = int(fecha_raw.replace("/Date(", "").replace(")/", ""))
                self.date = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
            except (ValueError, AttributeError):
                pass

    def __repr__(self) -> str:
        return (
            f"AguasDeValenciaReading(period={self.period}, "
            f"consumption={self.consumption_m3}m3, "
            f"total={self.total_reading_m3}m3, "
            f"date={self.date})"
        )


class AguasDeValenciaClient:
    """HTTP client for the Aguas de Valencia virtual office."""

    def __init__(self, username: str, password: str) -> None:
        self._username = username
        self._password = password
        self._session_id: str | None = None
        self._go_session_id: str | None = None

    async def authenticate(self, _unused_session: aiohttp.ClientSession | None = None) -> None:
        """Full login flow: GET login page -> POST credentials.

        Always uses a fresh CookieJar-less session to avoid stale cookie
        interference when re-authenticating after session expiry.
        """
        # Use a session with no shared CookieJar so previous cookies can't
        # interfere with the Set-Cookie the server sends on the login page.
        connector = aiohttp.TCPConnector()
        jar = aiohttp.CookieJar(unsafe=True)
        async with aiohttp.ClientSession(connector=connector, cookie_jar=jar) as auth_session:
            # Step 1: GET login page to receive anonymous x_SessionId cookie.
            async with auth_session.get(
                LOGIN_PAGE_URL,
                headers={**HEADERS_BASE, "Referer": "https://www.aguasdevalencia.es/"},
                allow_redirects=True,
            ) as resp:
                resp.raise_for_status()
                # Read directly from raw Set-Cookie header — most reliable approach
                self._session_id = None
                for header_value in resp.headers.getall("Set-Cookie", []):
                    for part in header_value.split(";"):
                        part = part.strip()
                        if part.startswith(f"{COOKIE_SESSION_ID}="):
                            self._session_id = part.split("=", 1)[1]
                            break
                    if self._session_id:
                        break
                # Fallback to jar
                if not self._session_id:
                    cookie = resp.cookies.get(COOKIE_SESSION_ID)
                    if cookie:
                        self._session_id = cookie.value
                if not self._session_id:
                    raise AguasDeValenciaAuthError(
                        f"Did not receive {COOKIE_SESSION_ID} cookie from login page"
                    )
                _LOGGER.debug("Got x_SessionId: %s", self._session_id)

            # Step 2: POST credentials — send x_SessionId explicitly, ignore jar
            async with auth_session.post(
                LOGIN_ACTION_URL,
                headers={
                    **HEADERS_BASE,
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "Referer": LOGIN_PAGE_URL,
                },
                cookies={COOKIE_SESSION_ID: self._session_id},
                data={
                    "login": self._username,
                    "pass": self._password,
                    "remember": "true",
                    "suministro": "",
                    "action": "",
                },
            ) as resp:
                resp.raise_for_status()
                # Read GO00_SessionId from raw header
                self._go_session_id = None
                for header_value in resp.headers.getall("Set-Cookie", []):
                    for part in header_value.split(";"):
                        part = part.strip()
                        if part.startswith(f"{COOKIE_GO_SESSION_ID}="):
                            self._go_session_id = part.split("=", 1)[1]
                            break
                    if self._go_session_id:
                        break
                if not self._go_session_id:
                    cookie = resp.cookies.get(COOKIE_GO_SESSION_ID)
                    if cookie:
                        self._go_session_id = cookie.value
                if not self._go_session_id:
                    raise AguasDeValenciaAuthError(
                        f"Did not receive {COOKIE_GO_SESSION_ID} — check credentials"
                    )
                body = await resp.json(content_type=None)
                if not body.get("result"):
                    raise AguasDeValenciaAuthError(
                        f"Login rejected by server: {body.get('error', 'unknown')}"
                    )
                _LOGGER.debug("Authentication successful")

    @property
    def is_authenticated(self) -> bool:
        return bool(self._session_id and self._go_session_id)

    async def get_readings(
        self,
        session: aiohttp.ClientSession,
        start: str | None = None,
        end: str | None = None,
        _retry: bool = True,
    ) -> list[AguasDeValenciaReading]:
        """Fetch billed readings. Re-authenticates once if session expired."""
        if not self.is_authenticated:
            await self.authenticate()

        now = datetime.now()
        if end is None:
            end = now.strftime("%d/%m/%Y")
        if start is None:
            # El servidor rechaza fechas de más de 5 años — usamos 4 años y medio de margen
            start = (now.replace(year=now.year - 4) - timedelta(days=180)).strftime("%d/%m/%Y")

        async with session.post(
            READINGS_URL,
            headers={
                **HEADERS_BASE,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Referer": "https://www.aguasdevalencia.es/VirtualOffice/Secure/Readings",
            },
            cookies={
                COOKIE_SESSION_ID: self._session_id,
                COOKIE_GO_SESSION_ID: self._go_session_id,
            },
            data={"start": start, "end": end},
            allow_redirects=False,  # 302 al login = sesión expirada
        ) as resp:
            # 302 redirect → el servidor nos manda al login, sesión expirada
            # 401/403 → por si acaso el servidor evoluciona
            if resp.status in (301, 302, 401, 403):
                if not _retry:
                    raise AguasDeValenciaAuthError(
                        f"Session expired and re-authentication failed (HTTP {resp.status})"
                    )
                _LOGGER.warning("Session expired (HTTP %s), re-authenticating...", resp.status)
                self._session_id = None
                self._go_session_id = None
                await self.authenticate()
                return await self.get_readings(session, start, end, _retry=False)

            resp.raise_for_status()
            body = await resp.json(content_type=None)

        # result=false con 200 también puede indicar sesión expirada
        if not body.get("result"):
            if _retry:
                _LOGGER.warning(
                    "API returned result=false (possible expired session), re-authenticating..."
                )
                self._session_id = None
                self._go_session_id = None
                await self.authenticate()
                return await self.get_readings(session, start, end, _retry=False)
            raise AguasDeValenciaApiError(
                f"API returned result=false after re-auth: {body}"
            )

        table: list[dict] = body.get("table", [])
        readings = [AguasDeValenciaReading(row) for row in table]
        _LOGGER.debug("Fetched %d readings", len(readings))
        return readings

    async def get_invoices(
        self,
        session: aiohttp.ClientSession,
        start: str | None = None,
        end: str | None = None,
        _retry: bool = True,
    ) -> list[AguasDeValenciaInvoice]:
        """Fetch invoices. Re-authenticates once if session expired."""
        if not self.is_authenticated:
            await self.authenticate()

        now = datetime.now()
        if end is None:
            end = now.strftime("%d/%m/%Y")
        if start is None:
            start = (now.replace(year=now.year - 4) - timedelta(days=180)).strftime("%d/%m/%Y")

        async with session.post(
            INVOICES_URL,
            headers={
                **HEADERS_BASE,
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "Referer": "https://www.aguasdevalencia.es/VirtualOffice/Secure/Billing",
            },
            cookies={
                COOKIE_SESSION_ID: self._session_id,
                COOKIE_GO_SESSION_ID: self._go_session_id,
            },
            data={"start": start, "end": end},
            allow_redirects=False,
        ) as resp:
            if resp.status in (301, 302, 401, 403):
                if not _retry:
                    raise AguasDeValenciaAuthError(
                        f"Session expired fetching invoices (HTTP {resp.status})"
                    )
                _LOGGER.warning("Session expired (HTTP %s), re-authenticating...", resp.status)
                self._session_id = None
                self._go_session_id = None
                await self.authenticate()
                return await self.get_invoices(session, start, end, _retry=False)

            resp.raise_for_status()
            body = await resp.json(content_type=None)

        if not body.get("result"):
            if _retry:
                _LOGGER.warning("Invoices API result=false, re-authenticating...")
                self._session_id = None
                self._go_session_id = None
                await self.authenticate()
                return await self.get_invoices(session, start, end, _retry=False)
            raise AguasDeValenciaApiError(
                f"Invoices API returned result=false after re-auth: {body}"
            )

        data: list[dict] = body.get("data", [])
        invoices = [AguasDeValenciaInvoice(row) for row in data]
        _LOGGER.debug("Fetched %d invoices", len(invoices))
        return invoices


class AguasDeValenciaInvoice:
    """Represents a single invoice (factura)."""

    # Matches the visible amount: "96,26 €" or "63,93 €"
    _AMOUNT_RE = re.compile(r"([\d]+(?:[,.][\d]+)?)\s*€")

    def __init__(self, raw: dict[str, Any]) -> None:
        self.invoice_number: str = raw.get("NFactura", "")
        self.period: str = raw.get("Periodo", "").strip()

        # Estado: strip HTML tags like <i class='fa fa-check-circle'></i>
        estado_raw = raw.get("Estado", "")
        self.status: str = re.sub(r"<[^>]+>", "", estado_raw).strip()

        # Importe: parse from "...<span...>000096</span>96,26 €"
        importe_raw = raw.get("Importe", "")
        self.amount: float | None = None
        match = self._AMOUNT_RE.search(importe_raw)
        if match:
            self.amount = float(match.group(1).replace(",", "."))

        # Date from MS epoch
        fecha_raw: str = raw.get("Fecha", "")
        self.date: datetime | None = None
        if fecha_raw:
            try:
                ms = int(fecha_raw.replace("/Date(", "").replace(")/", ""))
                self.date = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
            except (ValueError, AttributeError):
                pass

    @property
    def is_paid(self) -> bool:
        return "pagado" in self.status.lower()

    def __repr__(self) -> str:
        return (
            f"AguasDeValenciaInvoice(number={self.invoice_number}, "
            f"period={self.period}, amount={self.amount}€, status={self.status})"
        )
