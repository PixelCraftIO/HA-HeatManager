"""Behaviour tests for the HeatManager integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.data_entry_flow import InvalidData
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed, async_mock_service

from custom_components.heatmanager.const import DOMAIN
from custom_components.heatmanager.diagnostics import async_get_config_entry_diagnostics
from custom_components.heatmanager.manager import HeatManager

CLIMATE = "climate.kids"
WINDOW = "binary_sensor.kids_window"
WEEK_ALL_DAY = {
    day: [{"from": "06:00", "to": "22:00", "temp": 21}]
    for day in ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
}


def climate_state(hass: HomeAssistant, temp: float) -> None:
    hass.states.async_set(
        CLIMATE,
        "heat",
        {"temperature": temp, "current_temperature": 19.5, "min_temp": 4, "max_temp": 30, "target_temp_step": 0.5},
    )


@pytest.fixture
async def setup(hass: HomeAssistant, freezer: FrozenDateTimeFactory):
    """Integration with one room, a thermostat at 18 °C and a closed window."""
    await hass.config.async_set_time_zone("Europe/Berlin")
    freezer.move_to(dt_util.parse_datetime("2026-11-17T12:00:00+01:00"))  # Tuesday noon
    climate_state(hass, 18)
    hass.states.async_set(WINDOW, "off", {"device_class": "window"})
    # load the real climate component first so the mock below replaces its service
    assert await async_setup_component(hass, "climate", {})
    calls: list[ServiceCall] = async_mock_service(hass, "climate", "set_temperature")

    def _apply(call: ServiceCall) -> None:  # let the fake thermostat follow commands
        climate_state(hass, call.data["temperature"])

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        options={
            "rooms": [{"id": "r1", "name": "Kids", "climates": [CLIMATE], "windows": [WINDOW], "area": None}],
            "frost_temp": 5.0,
            "window_delay": 30,
        },
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    manager: HeatManager = entry.runtime_data
    return manager, calls, _apply, entry


def last_temp(calls: list[ServiceCall]) -> float | None:
    return calls[-1].data["temperature"] if calls else None


async def test_new_room_is_manual_and_untouched(hass: HomeAssistant, setup) -> None:
    manager, calls, _, _ = setup
    assert manager.assignments["r1"] == "manual"
    assert calls == []
    assert hass.states.get("select.kids_heating_profile").state == "Manual"
    assert hass.states.get("switch.heatmanager_schedule_paused").state == "off"


async def test_profile_assignment_sends_target(hass: HomeAssistant, setup) -> None:
    manager, calls, _, _ = setup
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", pid)
    await hass.async_block_till_done()
    assert last_temp(calls) == 21
    sensor = hass.states.get("sensor.kids_target_temperature")
    assert float(sensor.state) == 21
    assert sensor.attributes["reason"] == "profile_block"


async def test_block_end_switches_to_base(hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory) -> None:
    manager, calls, apply, _ = setup
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", pid)
    await hass.async_block_till_done()
    apply(calls[-1])
    freezer.move_to(dt_util.parse_datetime("2026-11-17T22:00:01+01:00"))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert last_temp(calls) == 17


async def test_manual_change_kept_until_next_block(hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory) -> None:
    manager, calls, apply, _ = setup
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", pid)
    await hass.async_block_till_done()
    apply(calls[-1])
    await hass.async_block_till_done()
    count = len(calls)
    climate_state(hass, 23)  # someone turns the knob
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == count


async def test_window_open_and_close(hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory) -> None:
    manager, calls, apply, _ = setup
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", pid)
    await hass.async_block_till_done()
    apply(calls[-1])

    hass.states.async_set(WINDOW, "on")
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert last_temp(calls) == 21  # not yet

    freezer.tick(timedelta(seconds=25))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert last_temp(calls) == 5
    assert hass.states.get("sensor.kids_target_temperature").attributes["window_open"] is True
    apply(calls[-1])

    hass.states.async_set(WINDOW, "off")
    await hass.async_block_till_done()
    assert last_temp(calls) == 21


async def test_short_window_opening_ignored(hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory) -> None:
    manager, calls, apply, _ = setup
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", pid)
    await hass.async_block_till_done()
    apply(calls[-1])
    await hass.async_block_till_done()
    count = len(calls)
    hass.states.async_set(WINDOW, "on")
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=10))
    hass.states.async_set(WINDOW, "off")
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == count


async def test_window_restores_manual_room(hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory) -> None:
    _, calls, apply, _ = setup
    climate_state(hass, 22.5)
    hass.states.async_set(WINDOW, "on")
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert last_temp(calls) == 5
    apply(calls[-1])
    hass.states.async_set(WINDOW, "off")
    await hass.async_block_till_done()
    assert last_temp(calls) == 22.5


async def test_pause_and_resume(hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory) -> None:
    manager, calls, apply, _ = setup
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", pid)
    await hass.async_block_till_done()
    apply(calls[-1])

    await hass.services.async_call(DOMAIN, "pause", {"duration": {"hours": 2}}, blocking=True)
    assert hass.states.get("switch.heatmanager_schedule_paused").state == "on"
    climate_state(hass, 24)
    count = len(calls)
    freezer.tick(timedelta(minutes=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == count  # paused: hands off

    freezer.tick(timedelta(hours=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("switch.heatmanager_schedule_paused").state == "off"
    assert last_temp(calls) == 21


async def test_retry_when_thermostat_ignores(hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory) -> None:
    manager, calls, _, _ = setup
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", pid)
    await hass.async_block_till_done()
    assert len(calls) == 1
    freezer.tick(timedelta(seconds=61))  # thermostat still at 18
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(calls) == 2


async def test_delete_profile_sets_rooms_manual(hass: HomeAssistant, setup) -> None:
    manager, _, _, _ = setup
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": {}})
    manager.set_assignment("r1", pid)
    manager.delete_profile(pid)
    await hass.async_block_till_done()
    assert manager.assignments["r1"] == "manual"


async def test_profile_validation(hass: HomeAssistant, setup) -> None:
    manager, _, _, _ = setup
    manager.save_profile({"name": "Bad", "week": {}})
    with pytest.raises(ValueError):
        manager.save_profile({"name": "bad", "week": {}})
    with pytest.raises(ValueError):
        manager.save_profile({"name": "Frostschutz", "week": {}})
    with pytest.raises(ValueError):
        manager.save_profile({"name": "X", "week": {"monday": [{"from": "8:00", "to": "7:00", "temp": 20}]}})


async def test_select_entity_changes_assignment(hass: HomeAssistant, setup) -> None:
    manager, calls, _, _ = setup
    manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    await hass.async_block_till_done()
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": "select.kids_heating_profile", "option": "Kinder"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert manager.assignments["r1"] == "kinder"
    assert last_temp(calls) == 21


async def test_storage_survives_reload(hass: HomeAssistant, setup, hass_storage: dict[str, Any]) -> None:
    manager, _, _, entry = setup
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", pid)
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    reloaded: HeatManager = entry.runtime_data
    assert reloaded.assignments["r1"] == "kinder"
    assert reloaded.profiles["kinder"]["base_temp"] == 17


async def test_websocket(hass: HomeAssistant, setup, hass_ws_client) -> None:
    manager, calls, _, _ = setup
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "heatmanager/subscribe"})
    msg = await client.receive_json()
    assert msg["success"]
    msg = await client.receive_json()
    assert msg["event"]["rooms"][0]["name"] == "Kids"

    await client.send_json(
        {
            "id": 2,
            "type": "heatmanager/profile/save",
            "name": "Gäste",
            "base_temp": 16,
            "icon": "mdi:sofa",
            "week": WEEK_ALL_DAY,
        }
    )
    while (msg := await client.receive_json())["id"] != 2:
        pass
    assert msg["success"], msg
    pid = msg["result"]["profile_id"]
    assert pid == "gaste"

    await client.send_json({"id": 3, "type": "heatmanager/room/set_profile", "room_id": "r1", "profile": pid})
    while (msg := await client.receive_json())["id"] != 3:
        pass
    assert msg["success"]
    await hass.async_block_till_done()
    assert last_temp(calls) == 21

    await client.send_json({"id": 4, "type": "heatmanager/pause", "hours": 1})
    while (msg := await client.receive_json())["id"] != 4:
        pass
    assert manager.pause_active and manager.pause_until is not None

    await client.send_json(
        {
            "id": 5,
            "type": "heatmanager/profile/save",
            "name": "Broken",
            "week": {"monday": [{"from": "9:00", "to": "8:00", "temp": 20}]},
        }
    )
    while (msg := await client.receive_json())["id"] != 5:
        pass
    assert not msg["success"]


async def test_config_and_options_flow(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"frost_temp": 6, "window_delay": 20})
    assert result["type"] == "create_entry"
    entry = result["result"]
    assert entry.options["frost_temp"] == 6.0
    await hass.async_block_till_done()

    hass.states.async_set("climate.bath", "heat", {"temperature": 20})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "menu"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "add_room"})
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Bad", "climates": ["climate.bath"], "windows": []}
    )
    assert result["type"] == "form" and result["step_id"] == "room_temperature"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert [r["name"] for r in entry.options["rooms"]] == ["Bad"]
    assert entry.options["rooms"][0]["control"] == "thermostat"
    assert hass.states.get("select.bad_heating_profile") is not None

    # edit: two sensors, weights, upper limit, external inputs
    hass.states.async_set("sensor.bath_a", "20", {"device_class": "temperature"})
    hass.states.async_set("sensor.bath_b", "21", {"device_class": "temperature"})
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "edit_room"})
    room_id = entry.options["rooms"][0]["id"]
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"room": room_id})
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "name": "Bad",
            "climates": ["climate.bath"],
            "windows": [],
            "temp_sensors": ["sensor.bath_a", "sensor.bath_b"],
        },
    )
    assert result["step_id"] == "room_temperature"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "temp_method": "mean",
            "window_near_sensors": ["sensor.bath_a"],
            "sensor_max_age": 30,
            "upper_limit": 1.5,
            "control": "external",
            "weight_1": 1,
            "weight_2": 3,
        },
    )
    assert result["step_id"] == "room_external"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"input_1": "number.bath_external"})
    assert result["type"] == "create_entry"
    room = entry.options["rooms"][0]
    assert room["temp_sensors"] == ["sensor.bath_a", "sensor.bath_b"]
    assert room["sensor_weights"] == {"sensor.bath_a": 1.0, "sensor.bath_b": 3.0}
    assert room["upper_limit"] == 1.5 and room["sensor_max_age"] == 30
    assert room["window_near_sensors"] == ["sensor.bath_a"]
    assert room["external_inputs"] == {"climate.bath": "number.bath_external"}

    # second instance not allowed
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] == "abort"


async def test_override_for_duration(hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory) -> None:
    manager, calls, apply, _ = setup
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", pid)
    await hass.async_block_till_done()
    apply(calls[-1])
    await hass.services.async_call(
        DOMAIN, "override_room", {"room": "kids", "temperature": 23, "duration": {"hours": 2}}, blocking=True
    )
    await hass.async_block_till_done()
    assert last_temp(calls) == 23
    sensor = hass.states.get("sensor.kids_target_temperature")
    assert sensor.attributes["reason"] == "override"
    assert sensor.attributes["override_until"] is not None
    apply(calls[-1])

    freezer.tick(timedelta(hours=2, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert last_temp(calls) == 21
    assert "r1" not in manager.overrides


async def test_override_until_next_change(hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory) -> None:
    manager, calls, apply, _ = setup
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", pid)
    await hass.async_block_till_done()
    apply(calls[-1])
    until = manager.set_override("r1", 19, until_next_change=True)
    await hass.async_block_till_done()
    assert until == dt_util.parse_datetime("2026-11-17T22:00:00+01:00")
    assert last_temp(calls) == 19
    apply(calls[-1])
    freezer.move_to(dt_util.parse_datetime("2026-11-17T22:00:01+01:00"))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert last_temp(calls) == 17  # the plan's next temperature


async def test_override_manual_room_restores(hass: HomeAssistant, setup) -> None:
    manager, calls, apply, _ = setup
    climate_state(hass, 19.5)
    with pytest.raises(ValueError):
        manager.set_override("r1", 22, until_next_change=True)  # manual room has no plan
    manager.set_override("r1", 22)
    await hass.async_block_till_done()
    assert last_temp(calls) == 22
    apply(calls[-1])
    manager.clear_override("r1")
    await hass.async_block_till_done()
    assert last_temp(calls) == 19.5


async def test_override_survives_reload_and_websocket(hass: HomeAssistant, setup, hass_ws_client) -> None:
    manager, calls, _, entry = setup
    client = await hass_ws_client(hass)
    await client.send_json({"id": 1, "type": "heatmanager/room/override", "room_id": "r1", "temp": 22.5, "hours": 3})
    msg = await client.receive_json()
    assert msg["success"], msg
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    reloaded: HeatManager = entry.runtime_data
    assert reloaded.overrides["r1"]["temp"] == 22.5
    assert reloaded.room_info(reloaded.rooms["r1"])["override"]["until"] is not None
    await client.send_json({"id": 2, "type": "heatmanager/room/clear_override", "room_id": "r1"})
    msg = await client.receive_json()
    assert msg["success"], msg
    assert reloaded.overrides == {}


async def test_thermostat_problem_creates_repair_issue(
    hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory
) -> None:
    manager, calls, apply, _ = setup
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", pid)
    await hass.async_block_till_done()
    registry = ir.async_get(hass)
    for seconds in (61, 121, 301, 301):  # thermostat answers, but stays at 18 °C
        freezer.tick(timedelta(seconds=seconds))
        climate_state(hass, 18)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert len(calls) == 4
    issue = registry.async_get_issue(DOMAIN, f"thermostat_{CLIMATE}")
    assert issue is not None and issue.translation_key == "thermostat_not_accepting"
    info = manager.room_info(manager.rooms["r1"])
    assert info["problems"] == [{"entity_id": CLIMATE, "kind": "not_accepting"}]
    assert hass.states.get("sensor.kids_target_temperature").attributes["problems"] == {CLIMATE: "not_accepting"}

    apply(calls[-1])  # works again
    await hass.async_block_till_done()
    assert registry.async_get_issue(DOMAIN, f"thermostat_{CLIMATE}") is None
    assert manager.room_info(manager.rooms["r1"])["problems"] == []


async def test_silent_thermostat_reported_as_not_responding(
    hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory
) -> None:
    manager, calls, apply, _ = setup
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", pid)
    await hass.async_block_till_done()
    for seconds in (61, 121, 301, 301):  # thermostat sends nothing at all
        freezer.tick(timedelta(seconds=seconds))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    issue = ir.async_get(hass).async_get_issue(DOMAIN, f"thermostat_{CLIMATE}")
    assert issue is not None and issue.translation_key == "thermostat_not_responding"
    assert manager.room_info(manager.rooms["r1"])["problems"] == [{"entity_id": CLIMATE, "kind": "not_responding"}]
    apply(calls[-1])  # back online and takes the setpoint
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, f"thermostat_{CLIMATE}") is None


async def test_long_unavailable_thermostat_reported(hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory) -> None:
    manager, _, _, _ = setup
    hass.states.async_set(CLIMATE, "unavailable")
    registry = ir.async_get(hass)
    for _ in range(14):
        freezer.tick(timedelta(minutes=5))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    issue = registry.async_get_issue(DOMAIN, f"thermostat_{CLIMATE}")
    assert issue is not None and issue.translation_key == "thermostat_unavailable"
    climate_state(hass, 18)
    await hass.async_block_till_done()
    assert registry.async_get_issue(DOMAIN, f"thermostat_{CLIMATE}") is None


async def test_away_lowers_profile_rooms(hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory) -> None:
    manager, calls, apply, entry = setup
    hass.states.async_set("person.anna", "home")
    hass.states.async_set("person.ben", "not_home")
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", pid)
    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            "presence_entities": ["person.anna", "person.ben"],
            "away_temp": 16,
            "away_delay": 10,
        },
    )
    await hass.async_block_till_done()
    manager = entry.runtime_data
    apply(calls[-1])
    assert last_temp(calls) == 21

    hass.states.async_set("person.anna", "not_home")
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert last_temp(calls) == 21  # not yet
    freezer.tick(timedelta(minutes=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert last_temp(calls) == 16
    assert hass.states.get("sensor.kids_target_temperature").attributes["reason"] == "away"
    assert manager.as_dict()["presence"] == {"configured": True, "away": True, "away_temp": 16.0}
    apply(calls[-1])

    hass.states.async_set("person.ben", "home")
    await hass.async_block_till_done()
    assert last_temp(calls) == 21


async def test_vacation(hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory, hass_ws_client) -> None:
    manager, calls, apply, entry = setup
    client = await hass_ws_client(hass)
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", pid)
    await hass.async_block_till_done()
    apply(calls[-1])
    await hass.services.async_call(DOMAIN, "start_vacation", {"until": "2026-11-20 16:00:00"}, blocking=True)
    await hass.async_block_till_done()
    assert last_temp(calls) == 5
    assert hass.states.get("sensor.kids_target_temperature").attributes["reason"] == "vacation"
    apply(calls[-1])

    await hass.config_entries.async_reload(entry.entry_id)  # survives restarts
    await hass.async_block_till_done()
    assert entry.runtime_data.vacation_until is not None

    freezer.move_to(dt_util.parse_datetime("2026-11-20T16:00:01+01:00"))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert entry.runtime_data.vacation_until is None
    assert last_temp(calls) == 21
    apply(calls[-1])

    await client.send_json({"id": 1, "type": "heatmanager/vacation", "until": "2026-12-01T10:00:00"})
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done()
    assert last_temp(calls) == 5
    apply(calls[-1])
    await client.send_json({"id": 2, "type": "heatmanager/vacation", "end": True})
    assert (await client.receive_json())["success"]
    await hass.async_block_till_done()
    assert last_temp(calls) == 21


async def test_vacation_leaves_manual_rooms(hass: HomeAssistant, setup) -> None:
    manager, calls, _, _ = setup
    manager.set_vacation(dt_util.now() + timedelta(days=2))
    await hass.async_block_till_done()
    assert calls == []


async def test_today_timeline_and_profile_edit(hass: HomeAssistant, setup) -> None:
    manager, _, _, _ = setup
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", pid)
    room = manager.rooms["r1"]
    assert manager.today(room) == [
        [0, 360, 17.0, "profile_base"],
        [360, 1320, 21.0, "profile_block"],
        [1320, 1440, 17.0, "profile_base"],
    ]

    manager.set_override("r1", 23, until=dt_util.now() + timedelta(hours=2))  # 12:00 - 14:00
    assert manager.today(room)[1:4] == [
        [360, 720, 21.0, "profile_block"],
        [720, 840, 23.0, "override"],
        [840, 1320, 21.0, "profile_block"],
    ]

    # rename, new icon and color keep the id and the assignment
    manager.save_profile({**manager.profiles[pid], "name": "Kids", "icon": "mdi:bed", "color": "#123abc"}, pid)
    assert manager.profiles[pid]["name"] == "Kids" and manager.profiles[pid]["color"] == "#123abc"
    assert manager.assignments["r1"] == pid
    with pytest.raises(ValueError):
        manager.save_profile({**manager.profiles[pid], "color": "red"}, pid)


async def test_diagnostics(hass: HomeAssistant, setup) -> None:
    manager, _, _, entry = setup
    manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", "kinder")
    diag = await async_get_config_entry_diagnostics(hass, entry)
    assert diag["rooms"][0]["name"] == "Kids"
    assert diag["rooms"][0]["climate_states"][CLIMATE]["attributes"]["temperature"] == 18
    assert diag["profiles"]["kinder"]["base_temp"] == 17
    assert diag["options"]["presence_entities"] == "0 entities"


async def test_setup_component_registers_services(hass: HomeAssistant) -> None:
    assert await async_setup_component(hass, DOMAIN, {})
    assert hass.services.has_service(DOMAIN, "pause")
    assert hass.services.has_service(DOMAIN, "resume")


@pytest.fixture(autouse=True)
def _fast_store():
    with patch(
        "homeassistant.helpers.storage.Store.async_delay_save",
        lambda self, data_func, delay=0: self.hass.async_create_task(self.async_save(data_func())),
    ):
        yield


def room_climate(hass: HomeAssistant, entry) -> str:
    """Entity id of the room's own climate entity (climate.kids is taken by the fake thermostat)."""
    from homeassistant.helpers import entity_registry as er

    entity_id = er.async_get(hass).async_get_entity_id("climate", DOMAIN, f"{entry.entry_id}_r1_climate")
    assert entity_id is not None
    return entity_id


async def test_room_climate_entity(hass: HomeAssistant, setup) -> None:
    manager, calls, apply, entry = setup
    room = room_climate(hass, entry)
    st = hass.states.get(room)
    assert st.state == "heat"
    assert st.attributes["preset_mode"] == "Manual"
    assert st.attributes["current_temperature"] == 19.5  # thermostat reading as fallback
    assert st.attributes["temperature"] == 18  # manual: what the thermostat is set to

    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    await hass.services.async_call(
        "climate", "set_preset_mode", {"entity_id": room, "preset_mode": "Kinder"}, blocking=True
    )
    await hass.async_block_till_done()
    assert manager.assignments["r1"] == pid
    assert last_temp(calls) == 21
    apply(calls[-1])
    assert hass.states.get(room).attributes["temperature"] == 21

    # a temperature set on the room holds until the plan's next change (22:00)
    manager.set_room_temperature("r1", 23)
    await hass.async_block_till_done()
    assert last_temp(calls) == 23
    assert manager.overrides["r1"]["until"] == dt_util.parse_datetime("2026-11-17T22:00:00+01:00")
    apply(calls[-1])

    # off = frost protection, on = back to the profile it had before
    await hass.services.async_call("climate", "turn_off", {"entity_id": room}, blocking=True)
    await hass.async_block_till_done()
    assert manager.assignments["r1"] == "frost"
    assert hass.states.get(room).state == "off"
    assert last_temp(calls) == 5
    apply(calls[-1])

    await hass.config_entries.async_reload(entry.entry_id)  # remembered across restarts
    await hass.async_block_till_done()
    manager = entry.runtime_data
    await hass.services.async_call("climate", "set_hvac_mode", {"entity_id": room, "hvac_mode": "heat"}, blocking=True)
    await hass.async_block_till_done()
    assert manager.assignments["r1"] == pid
    assert last_temp(calls) == 21


async def test_room_climate_manual_passes_through(hass: HomeAssistant, setup) -> None:
    manager, calls, _, entry = setup
    assert manager.set_room_temperature("r1", 20.5) is None
    await hass.async_block_till_done()
    assert last_temp(calls) == 20.5
    assert "r1" not in manager.overrides
    with pytest.raises(ValueError):
        manager.set_room_temperature("r1", 40)


async def test_own_climates_not_offered_as_thermostats(hass: HomeAssistant, setup) -> None:
    _, _, _, entry = setup
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"next_step_id": "add_room"})
    with pytest.raises(InvalidData):  # the selector leaves HeatManager's own rooms out
        await hass.config_entries.options.async_configure(
            result["flow_id"], {"name": "Bad", "climates": [room_climate(hass, entry), "climate.bath"]}
        )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"name": "Bad", "climates": ["climate.bath"]}
    )
    assert result["step_id"] == "room_temperature"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    bath = next(r for r in entry.options["rooms"] if r["name"] == "Bad")
    assert bath["climates"] == ["climate.bath"]
    assert bath["occupancy_sensors"] == [] and bath["vacant_delay"] == 30 and bath["vacant_temp"] == 17


async def test_empty_room_is_lowered(hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory) -> None:
    manager, calls, apply, entry = setup
    motion, presence = "binary_sensor.kids_motion", "binary_sensor.kids_presence"
    hass.states.async_set(motion, "off")
    hass.states.async_set(presence, "on")
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", pid)
    room = {**entry.options["rooms"][0], "occupancy_sensors": [motion, presence], "vacant_delay": 20, "vacant_temp": 18}
    hass.config_entries.async_update_entry(entry, options={**entry.options, "rooms": [room]})
    await hass.async_block_till_done()
    manager = entry.runtime_data
    apply(calls[-1])
    assert last_temp(calls) == 21

    hass.states.async_set(presence, "off")
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=15))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert last_temp(calls) == 21  # not yet
    freezer.tick(timedelta(minutes=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert last_temp(calls) == 18
    target = hass.states.get("sensor.kids_target_temperature")
    assert target.attributes["reason"] == "vacant" and target.attributes["vacant"] is True
    info = manager.as_dict()["rooms"][0]
    assert info["vacant"] is True and info["vacant_temp"] == 18
    apply(calls[-1])

    # still empty after a restart: lowered right away
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    manager = entry.runtime_data
    assert manager.runtime["r1"].vacant is True

    hass.states.async_set(motion, "on")
    await hass.async_block_till_done()
    assert last_temp(calls) == 21
    assert manager.runtime["r1"].vacant is False


async def test_empty_room_unsure_sensor_keeps_warm(hass: HomeAssistant, setup, freezer: FrozenDateTimeFactory) -> None:
    manager, calls, apply, entry = setup
    motion = "binary_sensor.kids_motion"
    hass.states.async_set(motion, "unavailable")
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", pid)
    room = {**entry.options["rooms"][0], "occupancy_sensors": [motion], "vacant_delay": 10, "vacant_temp": 16}
    hass.config_entries.async_update_entry(entry, options={**entry.options, "rooms": [room]})
    await hass.async_block_till_done()
    manager = entry.runtime_data
    freezer.tick(timedelta(minutes=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert manager.runtime["r1"].vacant is False
    assert last_temp(calls) == 21
    # the empty-room temperature never raises a lower plan
    room = {**room, "vacant_temp": 22}
    hass.states.async_set(motion, "off")
    hass.config_entries.async_update_entry(entry, options={**entry.options, "rooms": [room]})
    await hass.async_block_till_done()
    freezer.tick(timedelta(minutes=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    manager = entry.runtime_data
    assert manager.runtime["r1"].vacant is True
    assert manager.runtime["r1"].reason == "profile_block"
