"""Constants for the Codex Rates integration."""

from __future__ import annotations

DOMAIN = "codex_rates"

CONF_MODE = "mode"
CONF_BASE_URL = "base_url"
CONF_PASSWORD = "password"
CONF_TOTP_SECRET = "totp_secret"
CONF_AUTH_METHOD = "auth_method"
CONF_AUTH_JSON_PATH = "auth_json_path"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_ID_TOKEN = "id_token"
CONF_ACCOUNT_ID = "account_id"
CONF_EMAIL = "email"
CONF_POLL_INTERVAL = "poll_interval"
CONF_RICH_SENSORS = "rich_sensors"
CONF_VERIFY_SSL = "verify_ssl"

MODE_CODEX_LB = "codex_lb"
MODE_CHATGPT = "chatgpt"

AUTH_METHOD_DEVICE_CODE = "device_code"
AUTH_METHOD_PASTE_CALLBACK = "paste_callback"
AUTH_METHOD_AUTH_JSON = "auth_json"
AUTH_METHOD_TOKENS = "tokens"

DEFAULT_POLL_INTERVAL = 60
MIN_POLL_INTERVAL = 30
DEFAULT_RICH_SENSORS = False
DEFAULT_VERIFY_SSL = True

# OpenAI Codex CLI OAuth (same as Codex-LB / Codex CLI)
OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
OAUTH_AUTH_BASE_URL = "https://auth.openai.com"
OAUTH_REDIRECT_URI = "http://localhost:1455/auth/callback"
OAUTH_SCOPE = "openid profile email offline_access"
OAUTH_ORIGINATOR = "codex_cli_rs"

CHATGPT_USAGE_URL = "https://chatgpt.com/backend-api/wham/usage"

# Codex-LB dashboard cookie names seen in the wild
LB_SESSION_COOKIES = (
    "codex_lb_dashboard_session",
    "dashboard_session",
)

ATTR_USED_PERCENT = "used_percent"
ATTR_WINDOW_MINUTES = "window_minutes"
ATTR_ACCOUNT_ID = "account_id"
ATTR_EMAIL = "email"
ATTR_MIN = "min"
ATTR_MAX = "max"
ATTR_ACCOUNT_COUNT = "account_count"
ATTR_ACTIVE_COUNT = "active_count"

POOL_DEVICE_ID = "pool"
