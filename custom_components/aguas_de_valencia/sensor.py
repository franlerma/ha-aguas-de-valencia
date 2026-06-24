"""Sensor platform for Aguas de Valencia."""
from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import COORDINATOR, DOMAIN
from .coordinator import AguasDeValenciaCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: AguasDeValenciaCoordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    async_add_entities([
        AguasDeValenciaTotalSensor(coordinator, entry),
        AguasDeValenciaLastConsumptionSensor(coordinator, entry),
        AguasDeValenciaLastInvoiceAmountSensor(coordinator, entry),
        AguasDeValenciaLastInvoicePeriodSensor(coordinator, entry),
        AguasDeValenciaLastInvoiceStatusSensor(coordinator, entry),
    ])


def _device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Aguas de Valencia",
        manufacturer="Aguas de Valencia",
        model="Virtual Office",
        entry_type="service",
    )


def _last_main_invoice(coordinator: AguasDeValenciaCoordinator):
    """Return the most recent main invoice (FC prefix, not SCY/FCY corrections)."""
    if not coordinator.data or not coordinator.data.invoices:
        return None
    main = [i for i in coordinator.data.invoices if "FC" in i.invoice_number and "FCY" not in i.invoice_number]
    return main[-1] if main else coordinator.data.invoices[-1]


# ---------------------------------------------------------------------------
# Lectura del contador (para el panel de Energía)
# ---------------------------------------------------------------------------

class AguasDeValenciaTotalSensor(
    CoordinatorEntity[AguasDeValenciaCoordinator], SensorEntity
):
    """Contador acumulado en m³ (total_increasing) — para el panel de Energía."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:water-pump"
    _attr_has_entity_name = True
    _attr_translation_key = "total_reading"

    def __init__(self, coordinator: AguasDeValenciaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_total_reading"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data or not self.coordinator.data.readings:
            return None
        return self.coordinator.data.readings[-1].total_reading_m3

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.data or not self.coordinator.data.readings:
            return {}
        last = self.coordinator.data.readings[-1]
        return {
            "period": last.period,
            "reading_type": last.reading_type,
            "reading_date": last.date.isoformat() if last.date else None,
        }


# ---------------------------------------------------------------------------
# Consumo último periodo
# ---------------------------------------------------------------------------

class AguasDeValenciaLastConsumptionSensor(
    CoordinatorEntity[AguasDeValenciaCoordinator], SensorEntity
):
    """m³ consumidos en el último periodo de lectura."""

    _attr_device_class = SensorDeviceClass.WATER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfVolume.CUBIC_METERS
    _attr_icon = "mdi:water"
    _attr_has_entity_name = True
    _attr_translation_key = "last_consumption"

    def __init__(self, coordinator: AguasDeValenciaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_last_consumption"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> int | None:
        if not self.coordinator.data or not self.coordinator.data.readings:
            return None
        return self.coordinator.data.readings[-1].consumption_m3

    @property
    def extra_state_attributes(self) -> dict:
        if not self.coordinator.data or not self.coordinator.data.readings:
            return {}
        last = self.coordinator.data.readings[-1]
        return {
            "period": last.period,
            "reading_type": last.reading_type,
            "reading_date": last.date.isoformat() if last.date else None,
            "all_readings": [
                {
                    "period": r.period,
                    "consumption_m3": r.consumption_m3,
                    "total_m3": r.total_reading_m3,
                    "date": r.date.isoformat() if r.date else None,
                    "type": r.reading_type,
                }
                for r in self.coordinator.data.readings
            ],
        }


# ---------------------------------------------------------------------------
# Sensores de facturación
# ---------------------------------------------------------------------------

class AguasDeValenciaLastInvoiceAmountSensor(
    CoordinatorEntity[AguasDeValenciaCoordinator], SensorEntity
):
    """Importe de la última factura principal en €."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "EUR"
    _attr_icon = "mdi:receipt-text"
    _attr_has_entity_name = True
    _attr_translation_key = "last_invoice_amount"

    def __init__(self, coordinator: AguasDeValenciaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_last_invoice_amount"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> float | None:
        invoice = _last_main_invoice(self.coordinator)
        return invoice.amount if invoice else None

    @property
    def extra_state_attributes(self) -> dict:
        invoice = _last_main_invoice(self.coordinator)
        if not invoice:
            return {}
        return {
            "invoice_number": invoice.invoice_number,
            "period": invoice.period,
            "status": invoice.status,
            "date": invoice.date.isoformat() if invoice.date else None,
        }


class AguasDeValenciaLastInvoicePeriodSensor(
    CoordinatorEntity[AguasDeValenciaCoordinator], SensorEntity
):
    """Periodo de la última factura (ej. '2026  3º Bimestre')."""

    _attr_icon = "mdi:calendar-text"
    _attr_has_entity_name = True
    _attr_translation_key = "last_invoice_period"

    def __init__(self, coordinator: AguasDeValenciaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_last_invoice_period"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str | None:
        invoice = _last_main_invoice(self.coordinator)
        return invoice.period if invoice else None

    @property
    def extra_state_attributes(self) -> dict:
        invoice = _last_main_invoice(self.coordinator)
        if not invoice:
            return {}
        return {
            "invoice_number": invoice.invoice_number,
            "date": invoice.date.isoformat() if invoice.date else None,
        }


class AguasDeValenciaLastInvoiceStatusSensor(
    CoordinatorEntity[AguasDeValenciaCoordinator], SensorEntity
):
    """Estado de la última factura ('Pagado' / 'Pendiente')."""

    _attr_icon = "mdi:check-circle-outline"
    _attr_has_entity_name = True
    _attr_translation_key = "last_invoice_status"

    def __init__(self, coordinator: AguasDeValenciaCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_last_invoice_status"
        self._attr_device_info = _device_info(entry)

    @property
    def native_value(self) -> str | None:
        invoice = _last_main_invoice(self.coordinator)
        return invoice.status if invoice else None

    @property
    def extra_state_attributes(self) -> dict:
        invoice = _last_main_invoice(self.coordinator)
        if not invoice:
            return {}
        return {
            "invoice_number": invoice.invoice_number,
            "period": invoice.period,
            "amount": invoice.amount,
            "date": invoice.date.isoformat() if invoice.date else None,
        }
