# HeatManager for Home Assistant

Weekly heating profiles with a visual 7‑day grid, profiles you assign to rooms, window detection and a pause function – as one integration with its own dashboard card.

*Deutsche Kurzbeschreibung weiter unten.*

## Features

- **Heating profiles** (e.g. “Kids”, “Bathroom”, “Home office”): mark time blocks in a Monday–Sunday grid by dragging, give each block its own temperature. Outside the blocks the profile’s base temperature applies.
- **Today at a glance**: a slim timeline with one row per room shows when each room heats today (hide it with `show_today: false`).
- **Profiles** can be renamed and get a new icon and colour at any time (*Edit* next to the grid).
- **Rooms**: one or more thermostats per room, optional window/door contacts. Each room follows a profile, *Frost protection* or *Manual* (left alone).
- **Room temperature from several sensors**: add any number of temperature sensors to a room. HeatManager combines them (weighted mean, lowest, highest, or a main sensor with the others as fallback), ignores sensors that are unavailable or have not reported for a while (default 60 min) and falls back to the thermostats' own readings. Sensors near a window can be ignored while it is open. An optional **upper limit** stops heating while any sensor is too far above the target (e.g. warm at the bed, cold at the window).
- **How thermostats use it** (per room): *Thermostat controls itself* (default, same setpoint for all), *Send room temperature to the thermostats* (for devices with an external temperature input, refreshed at least every 15 min) or *Compensate each thermostat's setpoint* (works with any thermostat: a thermostat reading 1.5 K too warm gets 1.5 K more).
- **Window open**: after a configurable delay (default 30 s) the room drops to frost protection. When the window closes, the profile takes over again – or, for manual rooms and while paused, the previous setpoint is restored.
- **Override a room**: from the card (thermometer button on the room) or the `heatmanager.override_room` action hold one room at e.g. 22 °C for 1/2/4 h or until its next change in the profile – then it returns to its plan by itself.
- **Pause**: for 2 h, 8 h, 24 h, a week or until a date – thermostats keep their current temperature, the schedule resumes automatically.
- **Away**: optionally link persons/device trackers (Configure → *Away & presence*). When nobody has been home for a while (default 10 min), rooms with a profile are lowered to an away temperature (default 16 °C) and come back as soon as somebody is home.
- **Vacation**: frost protection in all scheduled rooms until a date (card button *Vacation…* or `heatmanager.start_vacation`), then the schedule continues. Unlike the pause, which only holds the current temperatures.
- **Manual changes are respected** until the next change in the profile.
- **Reliable sending**: if a thermostat does not confirm a new setpoint, it is sent again (after 1, 2 and 5 minutes); thermostats that come back online get the current target.
- **Thermostat problems are reported**: if a thermostat still ignores its setpoint after the retries, stops responding altogether (no update at all, e.g. lost Zigbee connection while Home Assistant still shows old values), or is unavailable for over an hour, the card marks the room and Home Assistant shows a repair notice (Settings → Repairs). Both disappear once the device works again.
- Works with any `climate` entity (Homematic IP, Zigbee2MQTT, ZHA, Tado, …). No cloud, no YAML.

## Installation

### HACS / Marketplace (custom repository)

1. Marketplace (HACS) → ⋮ → **Custom repositories** → add `https://github.com/PixelDevIO/HA-HeatManager`, category **Integration**.
2. Install **HeatManager** and restart Home Assistant.

### Manual

Copy `custom_components/heatmanager` into your `config/custom_components/` folder and restart Home Assistant.

## Setup

1. **Settings → Devices & services → Add integration → HeatManager.** Choose the frost protection temperature and the window delay.
2. Open HeatManager → **Configure** → **Add room**: name, thermostat(s), optional window contacts, temperature sensors and area. The second page sets how the room temperature is formed and how the thermostats use it; the defaults behave exactly like before.
3. Add the card to a dashboard (the card is loaded automatically, no resource needed):

   ```yaml
   type: custom:heatmanager-card
   ```

   HeatManager also keeps a small entry named *HeatManager card loader* under **Settings → Dashboards → Resources**. It makes the card appear on dashboards that were opened while Home Assistant was still starting, without reloading the browser. It is removed together with the integration. With YAML resources (`resource_mode: yaml`) nothing is added there.

   Tip: put it in a view of type **Panel** to give the grid the full width. Options: `show_today: false` hides the timeline, `hour_height` (default 22) sets the grid row height.

4. In the card create profiles with **New profile**, drag time blocks into the grid and assign profiles to rooms.
   Every section (Today, Profiles, Rooms) folds via its header and the card remembers this per browser. The week grid shows as a compact 7‑day preview; tap it (or select/create a profile) to edit.
   To delete several blocks at once, tap **Select**, mark blocks (or tap a weekday for the whole day, or **All**) and tap **Delete**. Nothing is stored until **Save**, and **Undo** brings them back.
   On touch screens a normal swipe scrolls the page; **press and hold** a moment, then drag to create or move a block. A short tap opens a block.

Editing profiles requires an administrator account; everybody can assign profiles and pause.

## Entities

| Entity | Description |
|---|---|
| `select.<room>_heating_profile` | Profile of the room (incl. *Frost protection* and *Manual*) |
| `sensor.<room>_target_temperature` | Target HeatManager sets; attributes `reason`, `profile`, `window_open`, `next_change`, `next_temperature`, `override_until`, `problems` |
| `sensor.<room>_room_temperature` | Actual room temperature (sensors combined, thermostats as fallback); attributes `source`, `method`, `sensors`, `valid_sensors`, `too_warm`, `control` |
| `switch.heatmanager_schedule_paused` | On while paused; attribute `until` |

Room devices are named after the room (e.g. *Kids Heating profile*). Installations from before 0.6.0 keep their existing entity IDs (`select.heatmanager_<room>_…`).

## Actions

| Action | Data |
|---|---|
| `heatmanager.pause` | optional `duration` (e.g. `"02:00:00"`) or `until` (datetime). Without either: until resumed |
| `heatmanager.resume` | – |
| `heatmanager.override_room` | `room` (name or id), `temperature`, and `duration`, `until` or `until_next_change: true`. Without an end: until cleared |
| `heatmanager.clear_room_override` | `room` |
| `heatmanager.start_vacation` | `until` (datetime) |
| `heatmanager.end_vacation` | – |

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
3. Vacation (rooms with a profile or frost protection) → frost protection temperature
4. Schedule paused → leave the thermostat alone
5. Room set to *Frost protection* → frost protection temperature
6. Room set to *Manual* → leave the thermostat alone
7. Otherwise the profile: temperature of the active time block, else the base temperature – at most the away temperature while nobody is home
8. Upper limit set and a sensor too far above that target → the profile's base temperature (or frost protection) until it is 0.5 K below the limit again

HeatManager only sends when the target changes (block start/end, profile or assignment change, window, end of pause). Changes made on the thermostat itself therefore last until the next change in the profile.

## Tips for thermostats with their own schedule

Put thermostats into a manual/heat mode so their internal week program does not fight HeatManager (e.g. Homematic IP: *Manu* instead of *Auto*; Sonoff TRVZB: `heat` instead of `auto`).

---

## Deutsch

HeatManager steuert Thermostate über **Heizprofile mit Wochenraster**. Zeitblöcke werden mit der Maus ins Raster gezogen (auf dem Tablet: kurz gedrückt halten, dann ziehen; normales Wischen scrollt), jeder Block bekommt eine eigene Temperatur, außerhalb gilt die Grundtemperatur. Alle Abschnitte der Karte lassen sich über ihre Überschrift einklappen (wird pro Browser gemerkt); das Wochenraster erscheint als kompakte Vorschau und öffnet sich per Antippen, bei Profilauswahl oder beim Anlegen eines Profils. Räume (ein oder mehrere Thermostate, optional Fensterkontakte) bekommen ein Profil, *Frostschutz* oder *Manuell*.

**Fenster offen** → nach 30 s Frostschutz, beim Schließen zurück zum Profil bzw. zur vorherigen Temperatur. **Raum übersteuern**: über das Thermometer-Symbol am Raum z. B. 2 Std. auf 22 °C oder bis zum nächsten Wechsel, danach zurück zum Plan. **Abwesenheit**: optional Personen verknüpfen (Konfigurieren › Abwesenheit); ist niemand zu Hause, gilt eine Absenktemperatur. **Urlaub**: Frostschutz bis zu einem Datum, danach läuft der Plan weiter. **Pause** für Stunden, eine Woche oder bis zu einem Datum. Manuelle Änderungen am Thermostat gelten bis zum nächsten Wechsel im Profil. **Raumtemperatur**: pro Raum beliebig viele Temperatursensoren, kombiniert als (gewichteter) Mittelwert, Minimum, Maximum oder Hauptsensor; ausgefallene oder zu lange stumme Sensoren zählen nicht, ersatzweise gelten die Thermostate. Fensternahe Sensoren zählen bei offenem Fenster nicht, eine Obergrenze verhindert Überheizen. Pro Raum wählbar: Thermostat regelt selbst, Raumtemperatur ans Thermostat senden oder Sollwert je Thermostat ausgleichen. Nimmt ein Thermostat Sollwerte dauerhaft nicht an oder ist es über eine Stunde nicht erreichbar, zeigt die Karte das am Raum und Home Assistant erzeugt einen Reparaturhinweis.

Die Zeitleiste **Heute** zeigt pro Raum, wann geheizt wird. Profile lassen sich jederzeit umbenennen, Symbol und Farbe ändern (*Bearbeiten*).

Einrichtung: Integration hinzufügen → **Konfigurieren** → Räume anlegen → Karte `type: custom:heatmanager-card` aufs Dashboard (am besten in eine Ansicht vom Typ *Panel*).

## Bug reports

Please attach diagnostics: **Settings → Devices & services → HeatManager → ⋮ → Download diagnostics**. They contain rooms, profiles and the thermostat states HeatManager sees (presence entities are left out).

## Releases

Every version bump on `main` creates a GitHub release automatically (`.github/workflows/release.yml`), which HACS offers as an update.

## License

MIT
