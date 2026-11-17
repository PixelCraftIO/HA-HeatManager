"""Constants for HeatManager."""

from __future__ import annotations

DOMAIN = "heatmanager"
NAME = "HeatManager"
VERSION = "0.8.0"

CONF_ROOMS = "rooms"
CONF_ROOM_ID = "id"
CONF_ROOM_NAME = "name"
CONF_CLIMATES = "climates"
CONF_WINDOWS = "windows"
CONF_AREA = "area"
CONF_FROST_TEMP = "frost_temp"
CONF_WINDOW_DELAY = "window_delay"
CONF_PRESENCE = "presence_entities"
CONF_AWAY_TEMP = "away_temp"
CONF_AWAY_DELAY = "away_delay"
# Room temperature (several sensors per room)
CONF_SENSORS = "temp_sensors"
CONF_TEMP_METHOD = "temp_method"
CONF_PRIMARY = "primary_sensor"
CONF_WEIGHTS = "sensor_weights"
CONF_WINDOW_NEAR = "window_near_sensors"
CONF_MAX_AGE = "sensor_max_age"
CONF_UPPER_LIMIT = "upper_limit"
CONF_CONTROL = "control"
CONF_EXTERNAL = "external_inputs"

DEFAULT_FROST_TEMP = 5.0
DEFAULT_WINDOW_DELAY = 30
DEFAULT_BASE_TEMP = 17.0
DEFAULT_AWAY_TEMP = 16.0
DEFAULT_AWAY_DELAY = 10  # minutes
DEFAULT_MAX_AGE = 60  # minutes without a report before a sensor counts as stale
# A window-near sensor is ignored while a window is open and this long after
WINDOW_NEAR_GRACE_MIN = 15
# External temperature inputs are refreshed at least this often
EXTERNAL_REFRESH_MIN = 15

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
REASON_OVERRIDE = "override"
REASON_AWAY = "away"
REASON_VACATION = "vacation"
REASON_TOO_WARM = "too_warm"

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")

STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

SIGNAL_UPDATE = f"{DOMAIN}_update"

FRONTEND_URL = "/heatmanager_static"
CARD_FILENAME = "heatmanager-card.js"

# Seconds after a command before checking whether the thermostat took it
RETRY_DELAYS = (60, 120, 300)
# A thermostat unavailable this long is reported as a problem
UNAVAILABLE_PROBLEM_AFTER = 3600
PROBLEM_NOT_ACCEPTING = "not_accepting"
PROBLEM_UNAVAILABLE = "unavailable"
# thermostat sent no state update at all while we kept sending it commands
PROBLEM_NOT_RESPONDING = "not_responding"
# Safety re-evaluation interval (minutes)
RECHECK_INTERVAL_MIN = 5

TEMP_MIN = 4.0
TEMP_MAX = 30.0
