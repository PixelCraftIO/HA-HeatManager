"""Behaviour tests for the HeatManager integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed, async_mock_service

from custom_components.heatmanager.const import DOMAIN
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
    assert hass.states.get("select.heatmanager_kids_heating_profile").state == "Manual"
    assert hass.states.get("switch.heatmanager_schedule_paused").state == "off"


async def test_profile_assignment_sends_target(hass: HomeAssistant, setup) -> None:
    manager, calls, _, _ = setup
    pid = manager.save_profile({"name": "Kinder", "base_temp": 17, "week": WEEK_ALL_DAY})
    manager.set_assignment("r1", pid)
    await hass.async_block_till_done()
    assert last_temp(calls) == 21
    sensor = hass.states.get("sensor.heatmanager_kids_target_temperature")
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
    assert hass.states.get("sensor.heatmanager_kids_target_temperature").attributes["window_open"] is True
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
        {"entity_id": "select.heatmanager_kids_heating_profile", "option": "Kinder"},
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
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()
    assert [r["name"] for r in entry.options["rooms"]] == ["Bad"]
    assert hass.states.get("select.heatmanager_bad_heating_profile") is not None

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
    sensor = hass.states.get("sensor.heatmanager_kids_target_temperature")
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
