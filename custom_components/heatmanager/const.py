"""Constants for HeatManager."""

from __future__ import annotations

DOMAIN = "heatmanager"
NAME = "HeatManager"
VERSION = "0.1.0"

CONF_ROOMS = "rooms"
CONF_ROOM_ID = "id"
CONF_ROOM_NAME = "name"
CONF_CLIMATES = "climates"
CONF_WINDOWS = "windows"
CONF_AREA = "area"
CONF_FROST_TEMP = "frost_temp"
CONF_WINDOW_DELAY = "window_delay"

DEFAULT_FROST_TEMP = 5.0
DEFAULT_WINDOW_DELAY = 30
DEFAULT_BASE_TEMP = 17.0

# Special room assignments besides real profiles
ASSIGN_FROST = "frost"
ASSIGN_MANUAL = "manual"
SPECIAL_ASSIGNMENTS = (ASSIGN_FROST, ASSIGN_MANUAL)

# Why a room has its current target
REASON_PROFILE_BLOCK = "profile_block"
REASON_PROFILE_BASE = "profile_base"
REASON_FROST = "frost"
REASON_WINDOW = "window"
REASON_PAUSED = "paused"
REASON_MANUAL = "manual"

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

SIGNAL_UPDATE = f"{DOMAIN}_update"

FRONTEND_URL = "/heatmanager_static"
CARD_FILENAME = "heatmanager-card.js"

# Seconds after a command before checking whether the thermostat took it
RETRY_DELAYS = (60, 120, 300)
# Safety re-evaluation interval (minutes)
RECHECK_INTERVAL_MIN = 5

TEMP_MIN = 4.0
TEMP_MAX = 30.0
