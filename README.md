# Aguas de Valencia — Home Assistant Integration

Custom component for Home Assistant that exposes water consumption data from the **Aguas de Valencia Virtual Office** as entities compatible with the Energy dashboard.

## Created entities

| Entity | Description | Energy dashboard |
|---|---|---|
| `sensor.aguas_de_valencia_lectura_del_contador` | Accumulated meter reading in m³ (`total_increasing`) | ✅ Use this one |
| `sensor.aguas_de_valencia_consumo_ultimo_periodo` | m³ consumed in the last billing period | ❌ Info only |
| `sensor.aguas_de_valencia_importe_ultima_factura` | Amount of the last invoice (€) | ❌ Info only |
| `sensor.aguas_de_valencia_periodo_ultima_factura` | Billing period of the last invoice | ❌ Info only |
| `sensor.aguas_de_valencia_estado_ultima_factura` | Status of the last invoice (Paid / Pending) | ❌ Info only |

> **Note:** Data is billed every two months. The Energy dashboard will display historical data correctly once Home Assistant accumulates a few updates.

## Installation

### Option A — HACS (recommended)

[![Add to HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=franlerma&repository=ha-aguas-de-valencia&category=integration)

Or manually: HACS → Integrations → ⋮ → Custom repositories → add `https://github.com/franlerma/ha-aguas-de-valencia`, category `Integration`.

### Option B — Manual

```bash
scp -r custom_components/aguas_de_valencia user@ha-host:/config/custom_components/
```

Or via the HA terminal:

```bash
cd /config/custom_components
# copy/paste or upload with the File Editor add-on
```

## Configuration

1. **Restart Home Assistant** after copying the files
2. Go to **Settings → Devices & Services → Add integration**
3. Search for "Aguas de Valencia"
4. Enter your Virtual Office email and password

Credentials are validated against the real API during the config flow.

## Energy dashboard

1. **Settings → Energy → Water**
2. Add source: `sensor.aguas_de_valencia_lectura_del_contador`
3. Home Assistant will calculate period consumption automatically

## Technical notes

- **Authentication:** Login obtains a `GO00_SessionId` cookie with a ~6 month expiry. The integration re-authenticates automatically when it expires.
- **Polling frequency:** Once per day — data is billed every two months, so more frequent polling is pointless.
- **No external dependencies:** Uses only `aiohttp`, which is bundled with Home Assistant.
