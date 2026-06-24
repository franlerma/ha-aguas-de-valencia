# Aguas de Valencia — Home Assistant Integration

Custom component para Home Assistant que expone el consumo de agua de la **Oficina Virtual de Aguas de Valencia** como entidades compatibles con el panel de Energía.

## Entidades creadas

| Entidad | Descripción | Para el panel de Energía |
|---|---|---|
| `sensor.aguas_de_valencia_lectura_del_contador` | Contador acumulado en m³ (`total_increasing`) | ✅ Usar esta |
| `sensor.aguas_de_valencia_consumo_ultimo_periodo` | m³ consumidos en el último trimestre | ❌ Solo info |

> **Nota:** Los datos son trimestrales (facturación real). El panel de energía mostrará el histórico correctamente una vez que HA acumule varias actualizaciones.

## Instalación

### Opción A — HACS (recomendado)

[![Añadir a HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=franlerma&repository=ha-aguas-de-valencia&category=integration)

O manualmente: HACS → Integraciones → ⋮ → Repositorios personalizados → añade `https://github.com/franlerma/ha-aguas-de-valencia`, categoría `Integration`.

### Opción B — Manual
```bash
# Desde tu máquina, copia la carpeta al config de HA
scp -r custom_components/aguas_de_valencia usuario@ha-host:/config/custom_components/
```
O con la terminal de HA:
```bash
cd /config/custom_components
# copia/pega o sube con el File Editor addon
```

## Configuración

1. **Reinicia Home Assistant** tras copiar los ficheros
2. Ve a **Ajustes → Dispositivos y Servicios → Añadir integración**
3. Busca "Aguas de Valencia"
4. Introduce tu correo y contraseña de la Oficina Virtual

La integración valida las credenciales en tiempo real durante el config flow.

## Panel de Energía

1. **Configuración → Energía → Agua**
2. Añade fuente: `sensor.aguas_de_valencia_lectura_del_contador`
3. HA calculará el consumo por periodo automáticamente

## Notas técnicas

- **Autenticación:** El login obtiene una cookie `GO00_SessionId` con caducidad de ~6 meses. La integración renueva la sesión automáticamente si expira.
- **Frecuencia de polling:** 1 vez al día (los datos son trimestrales, no tiene sentido más frecuencia).
- **Sin dependencias externas:** Solo usa `aiohttp`, que ya viene con HA.
