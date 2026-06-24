"""DataUpdateCoordinator for Aguas de Valencia."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    AguasDeValenciaApiError,
    AguasDeValenciaAuthError,
    AguasDeValenciaClient,
    AguasDeValenciaInvoice,
    AguasDeValenciaReading,
)
from .const import DOMAIN, SCAN_INTERVAL_HOURS

_LOGGER = logging.getLogger(__name__)


@dataclass
class AguasDeValenciaData:
    readings: list[AguasDeValenciaReading]
    invoices: list[AguasDeValenciaInvoice]


class AguasDeValenciaCoordinator(DataUpdateCoordinator[AguasDeValenciaData]):
    """Fetches and caches readings and invoices from Aguas de Valencia."""

    def __init__(self, hass: HomeAssistant, client: AguasDeValenciaClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(hours=SCAN_INTERVAL_HOURS),
        )
        self._client = client
        self._http_session: aiohttp.ClientSession | None = None

    async def _async_update_data(self) -> AguasDeValenciaData:
        """Called by HA to refresh sensor data."""
        if self._http_session is None or self._http_session.closed:
            self._http_session = aiohttp.ClientSession()

        try:
            readings, invoices = await asyncio.gather(
                self._client.get_readings(self._http_session),
                self._client.get_invoices(self._http_session),
            )
        except AguasDeValenciaAuthError as err:
            raise ConfigEntryAuthFailed(f"Authentication error: {err}") from err
        except AguasDeValenciaApiError as err:
            raise UpdateFailed(f"API error: {err}") from err
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Network error: {err}") from err

        if not readings:
            raise UpdateFailed("API returned empty readings list")

        return AguasDeValenciaData(readings=readings, invoices=invoices)

    async def async_shutdown(self) -> None:
        """Close the HTTP session when the integration is unloaded."""
        if self._http_session and not self._http_session.closed:
            await self._http_session.close()
        await super().async_shutdown()
