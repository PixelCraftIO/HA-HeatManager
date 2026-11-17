# HeatManager for Home Assistant

Weekly heating profiles with a visual 7‑day grid, profiles you assign to rooms, window detection and a pause function – as one integration with its own dashboard card.

*Deutsche Kurzbeschreibung weiter unten.*

## Features

- **Heating profiles** (e.g. “Kids”, “Bathroom”, “Home office”): mark time blocks in a Monday–Sunday grid by dragging, give each block its own temperature. Outside the blocks the profile’s base temperature applies.
- **Rooms**: one or more thermostats per room, optional window/door contacts. Each room follows a profile, *Frost protection* or *Manual* (left alone).
- **Window open**: after a configurable delay (default 30 s) the room drops to frost protection. When the window closes, the profile takes over again – or, for manual rooms and while paused, the previous setpoint is restored.
- **Override a room**: from the card (thermometer button on the room) or the `heatmanager.override_room` action hold one room at e.g. 22 °C for 1/2/4 h or until its next change in the profile – then it returns to its plan by itself.
- **Pause**: for 2 h, 8 h, 24 h, a week or until a date – thermostats keep their current temperature, the schedule resumes automatically.
- **Manual changes are respected** until the next change in the profile.
- **Reliable sending**: if a thermostat does not confirm a new setpoint, it is sent again (after 1, 2 and 5 minutes); thermostats that come back online get the current target.
- **Thermostat problems are reported**: if a thermostat still ignores its setpoint after the retries, or is unavailable for over an hour, the card marks the room and Home Assistant shows a repair notice (Settings → Repairs). Both disappear once the device works again.
- Works with any `climate` entity (Homematic IP, Zigbee2MQTT, ZHA, Tado, …). No cloud, no YAML.

## Installation

### HACS / Marketplace (custom repository)

1. Marketplace (HACS) → ⋮ → **Custom repositories** → add `https://github.com/PixelDevIO/HA-HeatManager`, category **Integration**.
2. Install **HeatManager** and restart Home Assistant.

### Manual

Copy `custom_components/heatmanager` into your `config/custom_components/` folder and restart Home Assistant.

## Setup

1. **Settings → Devices & services → Add integration → HeatManager.** Choose the frost protection temperature and the window delay.
2. Open HeatManager → **Configure** → **Add room**: name, thermostat(s), optional window contacts and area.
3. Add the card to a dashboard (the card is loaded automatically, no resource needed):

   ```yaml
   type: custom:heatmanager-card
   ```

   Tip: put it in a view of type **Panel** to give the grid the full width.

4. In the card create profiles with **New profile**, drag time blocks into the grid and assign profiles to rooms.
   On touch screens a normal swipe scrolls the page; **press and hold** a moment, then drag to create or move a block. A short tap opens a block.

Editing profiles requires an administrator account; everybody can assign profiles and pause.

## Entities

| Entity | Description |
|---|---|
| `select.heatmanager_<room>_heating_profile` | Profile of the room (incl. *Frost protection* and *Manual*) |
| `sensor.heatmanager_<room>_target_temperature` | Target HeatManager sets; attributes `reason`, `profile`, `window_open`, `next_change`, `next_temperature`, `override_until`, `problems` |
| `switch.heatmanager_schedule_paused` | On while paused; attribute `until` |

## Actions

| Action | Data |
|---|---|
| `heatmanager.pause` | optional `duration` (e.g. `"02:00:00"`) or `until` (datetime). Without either: until resumed |
| `heatmanager.resume` | – |
| `heatmanager.override_room` | `room` (name or id), `temperature`, and `duration`, `until` or `until_next_change: true`. Without an end: until cleared |
| `heatmanager.clear_room_override` | `room` |

Example – pause while everybody is away:

```yaml
action: heatmanager.pause
data:
  duration: "08:00:00"
```

## How targets are chosen

For each room, in this order:

1. A window has been open longer than the delay → frost protection temperature
2. Room overridden → the override temperature until its end
3. Schedule paused → leave the thermostat alone
4. Room set to *Frost protection* → frost protection temperature
5. Room set to *Manual* → leave the thermostat alone
6. Otherwise the profile: temperature of the active time block, else the base temperature

HeatManager only sends when the target changes (block start/end, profile or assignment change, window, end of pause). Changes made on the thermostat itself therefore last until the next change in the profile.

## Tips for thermostats with their own schedule

Put thermostats into a manual/heat mode so their internal week program does not fight HeatManager (e.g. Homematic IP: *Manu* instead of *Auto*; Sonoff TRVZB: `heat` instead of `auto`).

---

## Deutsch

HeatManager steuert Thermostate über **Heizprofile mit Wochenraster**. Zeitblöcke werden mit der Maus ins Raster gezogen (auf dem Tablet: kurz gedrückt halten, dann ziehen; normales Wischen scrollt), jeder Block bekommt eine eigene Temperatur, außerhalb gilt die Grundtemperatur. Räume (ein oder mehrere Thermostate, optional Fensterkontakte) bekommen ein Profil, *Frostschutz* oder *Manuell*.

**Fenster offen** → nach 30 s Frostschutz, beim Schließen zurück zum Profil bzw. zur vorherigen Temperatur. **Raum übersteuern**: über das Thermometer-Symbol am Raum z. B. 2 Std. auf 22 °C oder bis zum nächsten Wechsel, danach zurück zum Plan. **Pause** für Stunden, eine Woche oder bis zu einem Datum. Manuelle Änderungen am Thermostat gelten bis zum nächsten Wechsel im Profil. Nimmt ein Thermostat Sollwerte dauerhaft nicht an oder ist es über eine Stunde nicht erreichbar, zeigt die Karte das am Raum und Home Assistant erzeugt einen Reparaturhinweis.

Einrichtung: Integration hinzufügen → **Konfigurieren** → Räume anlegen → Karte `type: custom:heatmanager-card` aufs Dashboard (am besten in eine Ansicht vom Typ *Panel*).

## License

MIT
