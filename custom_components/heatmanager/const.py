"""Constants for HeatManager."""

from __future__ import annotations

DOMAIN = "heatmanager"
NAME = "HeatManager"
VERSION = "0.7.0"

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

DEFAULT_FROST_TEMP = 5.0
DEFAULT_WINDOW_DELAY = 30
DEFAULT_BASE_TEMP = 17.0
DEFAULT_AWAY_TEMP = 16.0
DEFAULT_AWAY_DELAY = 10  # minutes

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
# Safety re-evaluation interval (minutes)
RECHECK_INTERVAL_MIN = 5

TEMP_MIN = 4.0
TEMP_MAX = 30.0
