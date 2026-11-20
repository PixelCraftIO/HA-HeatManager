# HeatManager für Home Assistant

Wöchentliche Heizprofile mit einem grafischen 7‑Tage-Raster, Profile, die du Räumen zuweist, Fenstererkennung und eine Pausenfunktion – als eine Integration mit eigener Dashboard-Karte.

## Funktionen

- **Heizprofile** (z. B. „Kinder“, „Bad“, „Homeoffice“): Zeitblöcke im Raster Montag–Sonntag per Ziehen markieren, jeder Block bekommt seine eigene Temperatur. Außerhalb der Blöcke gilt die Grundtemperatur des Profils.
- **Heute auf einen Blick**: Eine schmale Zeitleiste mit einer Zeile pro Raum zeigt, wann heute in welchem Raum geheizt wird (ausblenden mit `show_today: false`).
- **Profile** lassen sich jederzeit umbenennen und bekommen ein neues Symbol und eine neue Farbe (*Bearbeiten* neben dem Raster).
- **Räume**: ein oder mehrere Thermostate pro Raum, optional Fenster-/Türkontakte. Jeder Raum folgt einem Profil, *Frostschutz* oder *Manuell* (wird in Ruhe gelassen).
- **Raumtemperatur aus mehreren Sensoren**: Einem Raum lassen sich beliebig viele Temperatursensoren hinzufügen. HeatManager kombiniert sie (gewichteter Mittelwert, niedrigster Wert, höchster Wert oder ein Hauptsensor mit den anderen als Ersatz), ignoriert Sensoren, die nicht verfügbar sind oder sich eine Weile nicht gemeldet haben (Standard 60 Min.), und greift ersatzweise auf die Messwerte der Thermostate zurück. Sensoren in Fensternähe können bei offenem Fenster ignoriert werden. Eine optionale **Obergrenze** stoppt das Heizen, solange ein Sensor zu weit über dem Sollwert liegt (z. B. warm am Bett, kalt am Fenster).
- **Wie die Thermostate sie nutzen** (pro Raum): *Thermostat regelt selbst* (Standard, gleicher Sollwert für alle), *Raumtemperatur an die Thermostate senden* (für Geräte mit externem Temperatureingang, mindestens alle 15 Min. aktualisiert) oder *Sollwert je Thermostat ausgleichen* (funktioniert mit jedem Thermostat: Ein Thermostat, das 1,5 K zu warm misst, bekommt 1,5 K mehr).
- **Fenster offen**: Nach einer einstellbaren Verzögerung (Standard 30 s) geht der Raum auf Frostschutz. Wird das Fenster geschlossen, übernimmt wieder das Profil – bzw. bei manuellen Räumen und während einer Pause wird der vorherige Sollwert wiederhergestellt.
- **Raum übersteuern**: Über die Karte (Thermometer-Symbol am Raum) oder die Aktion `heatmanager.override_room` einen Raum z. B. 1/2/4 Std. oder bis zum nächsten Wechsel im Profil auf 22 °C halten – danach kehrt er von selbst zu seinem Plan zurück.
- **Pause**: für 2 Std., 8 Std., 24 Std., eine Woche oder bis zu einem Datum – die Thermostate behalten ihre aktuelle Temperatur, der Zeitplan läuft danach automatisch weiter.
- **Abwesenheit**: Optional Personen/Geräte-Tracker verknüpfen (Konfigurieren → *Abwesenheit*). Ist eine Weile niemand zu Hause (Standard 10 Min.), werden Räume mit Profil auf eine Abwesenheitstemperatur abgesenkt (Standard 16 °C) und kehren zurück, sobald jemand heimkommt.
- **Leere Räume**: Einem Raum optional Bewegungs- oder Präsenzmelder geben (jeder `binary_sensor`, `on` = jemand da). Sind alle eine Weile aus (Standard 30 Min.), wird der Raum auf seine Temperatur für leere Räume abgesenkt (Standard 17 °C) und heizt wieder normal, sobald einer anspricht. Nur für Räume mit Profil und nie über den Plan hinaus. Ein nicht verfügbarer Sensor hält den Raum warm. Für Räume, in denen man still sitzt oder schläft, eignen sich Präsenzmelder (mmWave) besser als Bewegungsmelder.
- **Jeder Raum ist ein Thermostat**: HeatManager legt pro Raum eine `climate`-Entität an. Nutzbar mit der Thermostat-Kachel, Sprachassistenten (Assist, Alexa, Google) oder HomeKit: Die Raumtemperatur ist der kombinierte Messwert, die Voreinstellungen sind deine Heizprofile, *Aus* setzt den Raum auf Frostschutz und *Heizen* holt das vorherige Profil zurück. Eine dort eingestellte Temperatur gilt bis zum nächsten Wechsel im Profil (Räume auf *Manuell*: Sie geht direkt an die Thermostate).
- **Urlaub**: Frostschutz in allen Räumen mit Plan bis zu einem Datum (Karten-Button *Urlaub…* oder `heatmanager.start_vacation`), danach läuft der Plan weiter. Anders als die Pause, die nur die aktuellen Temperaturen hält.
- **Manuelle Änderungen werden respektiert** bis zum nächsten Wechsel im Profil.
- **Zuverlässiges Senden**: Bestätigt ein Thermostat einen neuen Sollwert nicht, wird er erneut gesendet (nach 1, 2 und 5 Minuten); Thermostate, die wieder online kommen, bekommen den aktuellen Sollwert.
- **Thermostat-Probleme werden gemeldet**: Ignoriert ein Thermostat seinen Sollwert auch nach den Wiederholungen, reagiert es gar nicht mehr (überhaupt keine Aktualisierung, z. B. Zigbee-Verbindung verloren, während Home Assistant noch alte Werte zeigt) oder ist es über eine Stunde nicht verfügbar, markiert die Karte den Raum und Home Assistant zeigt einen Reparaturhinweis (Einstellungen → Reparaturen). Beides verschwindet, sobald das Gerät wieder funktioniert.
- Funktioniert mit jeder `climate`-Entität (Homematic IP, Zigbee2MQTT, ZHA, Tado, …). Keine Cloud, kein YAML.

## Installation

### HACS / Marketplace (benutzerdefiniertes Repository)

1. Marketplace (HACS) → ⋮ → **Benutzerdefinierte Repositories** → `https://github.com/PixelDevIO/HA-HeatManager` hinzufügen, Kategorie **Integration**.
2. **HeatManager** installieren und Home Assistant neu starten.

### Manuell

`custom_components/heatmanager` in deinen Ordner `config/custom_components/` kopieren und Home Assistant neu starten.

## Einrichtung

1. **Einstellungen → Geräte & Dienste → Integration hinzufügen → HeatManager.** Frostschutztemperatur und Fensterverzögerung wählen.
2. HeatManager öffnen → **Konfigurieren** → **Raum hinzufügen**: Name, Thermostat(e), optional Fensterkontakte, Temperatursensoren und Bereich. Auf der zweiten Seite legst du fest, wie die Raumtemperatur gebildet wird und wie die Thermostate sie nutzen; die Standardwerte verhalten sich genau wie bisher.
3. Die Karte zu einem Dashboard hinzufügen (die Karte wird automatisch geladen, keine Ressource nötig):

   ```yaml
   type: custom:heatmanager-card
   ```

   HeatManager legt außerdem einen kleinen Eintrag namens *HeatManager card loader* unter **Einstellungen → Dashboards → Ressourcen** an. Er sorgt dafür, dass die Karte auch auf Dashboards erscheint, die geöffnet wurden, während Home Assistant noch startete, ohne den Browser neu zu laden. Er wird zusammen mit der Integration entfernt. Bei YAML-Ressourcen (`resource_mode: yaml`) wird dort nichts hinzugefügt.

   Tipp: Die Karte in eine Ansicht vom Typ **Panel** legen, damit das Raster die volle Breite bekommt. Optionen: `show_today: false` blendet die Zeitleiste aus, `hour_height` (Standard 22) legt die Zeilenhöhe des Rasters fest.

4. In der Karte mit **Neues Profil** Profile anlegen, Zeitblöcke ins Raster ziehen und den Räumen Profile zuweisen.
   Jeder Abschnitt (Heute, Profile, Räume) lässt sich über seine Überschrift einklappen, die Karte merkt sich das pro Browser. Das Wochenraster erscheint als kompakte 7‑Tage-Vorschau; zum Bearbeiten antippen (oder ein Profil auswählen/anlegen).
   Um mehrere Blöcke auf einmal zu löschen, **Auswählen** antippen, Blöcke markieren (oder einen Wochentag für den ganzen Tag antippen, oder **Alle**) und **Löschen** antippen. Gespeichert wird erst mit **Speichern**, und **Rückgängig** holt sie zurück.
   Auf Touchscreens scrollt normales Wischen die Seite; **kurz gedrückt halten**, dann ziehen, um einen Block anzulegen oder zu verschieben. Kurzes Antippen öffnet einen Block.

Profile bearbeiten erfordert ein Administratorkonto; Profile zuweisen und pausieren kann jeder.

## Entitäten

| Entität | Beschreibung |
|---|---|
| `climate.<room>` | Der Raum als ein Thermostat: Raumtemperatur, Sollwert, Voreinstellungen = Profile, *Aus* = Frostschutz |
| `select.<room>_heating_profile` | Profil des Raums (inkl. *Frostschutz* und *Manuell*) |
| `sensor.<room>_target_temperature` | Sollwert, den HeatManager setzt; Attribute `reason`, `profile`, `window_open`, `next_change`, `next_temperature`, `override_until`, `problems`, `vacant` |
| `sensor.<room>_room_temperature` | Tatsächliche Raumtemperatur (Sensoren kombiniert, Thermostate als Ersatz); Attribute `source`, `method`, `sensors`, `valid_sensors`, `too_warm`, `control` |
| `switch.heatmanager_schedule_paused` | An während einer Pause; Attribut `until` |

Die Geräte der Räume sind nach dem Raum benannt (z. B. *Kinder Heizprofil*). Home Assistant bildet die Entitäts-IDs aus dem Namen in der Sprache der Oberfläche, bei deutscher Oberfläche also z. B. `select.<raum>_heizprofil`. Installationen von vor 0.6.0 behalten ihre bestehenden Entitäts-IDs (`select.heatmanager_<room>_…`).

## Aktionen

| Aktion | Daten |
|---|---|
| `heatmanager.pause` | optional `duration` (z. B. `"02:00:00"`) oder `until` (Datum/Uhrzeit). Ohne beides: bis zur Fortsetzung |
| `heatmanager.resume` | – |
| `heatmanager.override_room` | `room` (Name oder ID), `temperature` und `duration`, `until` oder `until_next_change: true`. Ohne Ende: bis zum Aufheben |
| `heatmanager.clear_room_override` | `room` |
| `heatmanager.start_vacation` | `until` (Datum/Uhrzeit) |
| `heatmanager.end_vacation` | – |

Beispiel – pausieren, während alle unterwegs sind:

```yaml
action: heatmanager.pause
data:
  duration: "08:00:00"
```

## Wie der Sollwert bestimmt wird

Für jeden Raum, in dieser Reihenfolge:

1. Ein Fenster ist länger als die Verzögerung offen → Frostschutztemperatur
2. Raum übersteuert → die Übersteuerungstemperatur bis zu ihrem Ende
3. Urlaub (Räume mit Profil oder Frostschutz) → Frostschutztemperatur
4. Zeitplan pausiert → Thermostat wird in Ruhe gelassen
5. Raum auf *Frostschutz* → Frostschutztemperatur
6. Raum auf *Manuell* → Thermostat wird in Ruhe gelassen
7. Sonst das Profil: Temperatur des aktiven Zeitblocks, sonst die Grundtemperatur – höchstens die Abwesenheitstemperatur, solange niemand zu Hause ist, und höchstens die Temperatur für leere Räume, solange die Bewegungs-/Präsenzmelder des Raums niemanden melden
8. Obergrenze gesetzt und ein Sensor zu weit über diesem Sollwert → Grundtemperatur des Profils (oder Frostschutz), bis er wieder 0,5 K unter der Grenze liegt

HeatManager sendet nur, wenn sich der Sollwert ändert (Blockbeginn/-ende, Profil- oder Zuweisungswechsel, Fenster, Ende der Pause). Änderungen direkt am Thermostat gelten deshalb bis zum nächsten Wechsel im Profil.

## Tipps für Thermostate mit eigenem Zeitplan

Thermostate in einen manuellen bzw. Heizmodus stellen, damit ihr internes Wochenprogramm nicht gegen HeatManager arbeitet (z. B. Homematic IP: *Manu* statt *Auto*; Sonoff TRVZB: `heat` statt `auto`).

## Fehler melden

Bitte Diagnosedaten anhängen: **Einstellungen → Geräte & Dienste → HeatManager → ⋮ → Diagnosedaten herunterladen**. Sie enthalten Räume, Profile und die Thermostatzustände, die HeatManager sieht (Anwesenheits-Entitäten werden weggelassen).

## Releases

Jede Versionserhöhung auf `main` erzeugt automatisch ein GitHub-Release (`.github/workflows/release.yml`), das HACS als Update anbietet.

## Lizenz

MIT
