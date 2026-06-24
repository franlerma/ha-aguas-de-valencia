"""Constants for Aguas de Valencia integration."""

DOMAIN = "aguas_de_valencia"

BASE_URL = "https://www.aguasdevalencia.es/VirtualOffice"
LOGIN_PAGE_URL = f"{BASE_URL}/Login"
LOGIN_ACTION_URL = f"{BASE_URL}/action_Login"
READINGS_URL = f"{BASE_URL}/Secure/action_getLecturasFacturadasAbonado"
INVOICES_URL = f"{BASE_URL}/Secure/action_obtenerFacturasAbonadoEntreFechas"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"

COOKIE_SESSION_ID = "x_SessionId"
COOKIE_GO_SESSION_ID = "GO00_SessionId"

SCAN_INTERVAL_HOURS = 24

COORDINATOR = "coordinator"
