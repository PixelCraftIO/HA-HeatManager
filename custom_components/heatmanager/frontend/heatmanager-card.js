/* HeatManager card – weekly heating profiles, room assignment, pause and window state.
 * Served and auto-loaded by the HeatManager integration. */
const VERSION = "0.7.1";
const DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
const PALETTE = ["#f4a340", "#7e8ef1", "#3fb8c9", "#8bc34a", "#e57373", "#ba68c8", "#4db6ac", "#ffb74d"];
const ICONS = ["mdi:radiator", "mdi:sofa", "mdi:bed", "mdi:teddy-bear", "mdi:shower", "mdi:desk", "mdi:silverware-fork-knife", "mdi:account-group", "mdi:dumbbell", "mdi:home-export-outline", "mdi:snowflake", "mdi:fire"];
const SNAP = 15;
const HOLD_MS = 350; // touch: press and hold this long before dragging

const I18N = {
  de: {
    days: ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"],
    daysLong: ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"],
    active: "Heizplan aktiv", activeSub: "Alle Räume folgen ihrem Heizprofil",
    paused: "Heizplan pausiert", pausedUntil: "bis {t} · Thermostate halten ihre Temperatur", pausedOpen: "bis zum Fortsetzen · Thermostate halten ihre Temperatur",
    resume: "Fortsetzen", pause: "Pausieren", extend: "Verlängern", hours: "{n} Std.", week: "1 Woche", untilDate: "Bis Datum…",
    profiles: "Heizprofile", newProfile: "Neues Profil", deleteProfile: "Profil löschen",
    base: "Grundtemperatur", baseHint: "(außerhalb der Zeitblöcke)",
    hint: "Im Raster ziehen = neuer Zeitblock · Block antippen = bearbeiten · Ränder ziehen = Zeit ändern",
    hintTouch: "Wischen = scrollen · Antippen = bearbeiten · Gedrückt halten und ziehen = Block anlegen oder verschieben",
    unsaved: "Ungespeicherte Änderungen am Profil „{p}“", discard: "Verwerfen", save: "Speichern",
    rooms: "Räume & Profile", unreachable: "nicht erreichbar", windowOpen: "Fenster offen", next: "ab {t} → {v}",
    legend: "<b>Frostschutz</b> = {f} °C · <b>Manuell</b> = Raum wird nicht gesteuert · <b>Fenster offen</b> (ab {d} s) = {f} °C, danach zurück",
    frost: "Frostschutz", manual: "Manuell",
    block: "Zeitblock", from: "Von", to: "Bis", alsoFor: "Auch für diese Tage übernehmen:", monFri: "Mo–Fr", weekend: "Sa–So", all: "Alle",
    del: "Löschen", cancel: "Abbrechen", apply: "Übernehmen", copyTo: "{d} kopieren nach", copyHint: "Die Zeitblöcke der gewählten Tage werden ersetzt.", clearDay: "Tag leeren", copy: "Kopieren", copyDay: "Tag kopieren",
    newTitle: "Neues Heizprofil", name: "Name", namePh: "z. B. Gäste", icon: "Symbol", startWith: "Starten mit", empty: "Leerem Wochenplan", copyOf: "Kopie von „{p}“", create: "Anlegen", creating: "Wird angelegt…",
    delTitle: "Profil „{p}“ löschen?", delUsed: "Diese Räume nutzen das Profil noch und werden auf <b>Manuell</b> gestellt: {r}", delUnused: "Das Profil wird von keinem Raum genutzt.", delFinal: "Der Wochenplan wird endgültig entfernt.",
    pauseTitle: "Heizplan pausieren bis", dateTime: "Datum & Uhrzeit", pauseHint: "Danach läuft der Heizplan automatisch weiter.",
    errFuture: "Bitte einen Zeitpunkt in der Zukunft wählen", errName: "Bitte einen Namen eingeben", errOrder: "„Bis“ muss nach „Von“ liegen",
    saved: "Profil „{p}“ gespeichert", created: "Profil „{p}“ angelegt – jetzt Zeitblöcke ins Raster ziehen", deleted: "Profil „{p}“ gelöscht", failed: "Fehlgeschlagen: {e}",
    notLoaded: "HeatManager ist nicht eingerichtet. Füge die Integration unter Einstellungen › Geräte & Dienste hinzu.",
    noRooms: "Noch keine Räume. Lege sie unter Einstellungen › Geräte & Dienste › HeatManager › Konfigurieren an.",
    noProfiles: "Noch keine Heizprofile – lege mit „Neues Profil“ das erste an.",
    adminOnly: "Profile bearbeiten können nur Administratoren.",
    showWeek: "Wochenplan bearbeiten", hideWeek: "Wochenplan einklappen", expand: "Aufklappen", collapse: "Einklappen",
    usedBy: "genutzt von {r}", usedByNone: "von keinem Raum genutzt",
    today: "Heute", todayOff: "nicht gesteuert", editProfile: "Bearbeiten", editTitle: "Profil bearbeiten", color: "Farbe",
    vacation: "Urlaubsmodus", vacationSub: "bis {t} · Frostschutz in allen Räumen mit Plan", vacationBtn: "Urlaub…", vacationTitle: "Urlaub bis", vacationHint: "Bis dahin Frostschutz in allen Räumen mit Profil oder Frostschutz, danach läuft der Heizplan weiter. Räume auf Manuell bleiben unberührt.", vacationStart: "Urlaub starten", vacationEnd: "Urlaub beenden",
    away: "Niemand zu Hause · höchstens {t} °C", home: "Jemand zu Hause",
    probNotAccepting: "{n} nimmt Sollwert nicht an", probNotResponding: "{n} antwortet nicht", probUnavailable: "{n} seit über 1 Std. nicht erreichbar", probHint: "Details unter Einstellungen › Reparaturen",
    override: "Übersteuern", overrideTitle: "{r} übersteuern", overrideFor: "Wie lange?", untilNext: "Bis zum nächsten Wechsel", untilNextAt: "Bis zum Wechsel um {t}",
    overrideActive: "{v} bis {t}", overrideEnd: "Beenden", overrideHint: "Danach folgt der Raum wieder seinem Plan.", overrideHintManual: "Danach bekommt das Thermostat wieder seinen vorherigen Wert.",
  },
  en: {
    days: ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"],
    daysLong: ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
    active: "Schedule active", activeSub: "All rooms follow their heating profile",
    paused: "Schedule paused", pausedUntil: "until {t} · thermostats keep their temperature", pausedOpen: "until resumed · thermostats keep their temperature",
    resume: "Resume", pause: "Pause", extend: "Extend", hours: "{n} h", week: "1 week", untilDate: "Until date…",
    profiles: "Heating profiles", newProfile: "New profile", deleteProfile: "Delete profile",
    base: "Base temperature", baseHint: "(outside time blocks)",
    hint: "Drag in the grid = new block · tap a block = edit · drag edges = change time",
    hintTouch: "Swipe = scroll · tap = edit · press and hold, then drag = create or move a block",
    unsaved: "Unsaved changes to profile “{p}”", discard: "Discard", save: "Save",
    rooms: "Rooms & profiles", unreachable: "unreachable", windowOpen: "Window open", next: "from {t} → {v}",
    legend: "<b>Frost protection</b> = {f} °C · <b>Manual</b> = room not controlled · <b>Window open</b> (after {d} s) = {f} °C, then back",
    frost: "Frost protection", manual: "Manual",
    block: "Time block", from: "From", to: "To", alsoFor: "Also apply to:", monFri: "Mon–Fri", weekend: "Sat–Sun", all: "All",
    del: "Delete", cancel: "Cancel", apply: "Apply", copyTo: "Copy {d} to", copyHint: "Blocks of the selected days are replaced.", clearDay: "Clear day", copy: "Copy", copyDay: "Copy day",
    newTitle: "New heating profile", name: "Name", namePh: "e.g. Guests", icon: "Icon", startWith: "Start with", empty: "Empty week", copyOf: "Copy of “{p}”", create: "Create", creating: "Creating…",
    delTitle: "Delete profile “{p}”?", delUsed: "These rooms still use it and will be set to <b>Manual</b>: {r}", delUnused: "No room uses this profile.", delFinal: "The week plan is removed permanently.",
    pauseTitle: "Pause schedule until", dateTime: "Date & time", pauseHint: "The schedule continues automatically afterwards.",
    errFuture: "Please choose a moment in the future", errName: "Please enter a name", errOrder: "“To” must be after “From”",
    saved: "Profile “{p}” saved", created: "Profile “{p}” created – now drag time blocks into the grid", deleted: "Profile “{p}” deleted", failed: "Failed: {e}",
    notLoaded: "HeatManager is not set up. Add the integration under Settings › Devices & services.",
    noRooms: "No rooms yet. Add them under Settings › Devices & services › HeatManager › Configure.",
    noProfiles: "No heating profiles yet – create the first one with “New profile”.",
    adminOnly: "Only administrators can edit profiles.",
    showWeek: "Edit week plan", hideWeek: "Collapse week plan", expand: "Expand", collapse: "Collapse",
    usedBy: "used by {r}", usedByNone: "not used by any room",
    today: "Today", todayOff: "not controlled", editProfile: "Edit", editTitle: "Edit profile", color: "Colour",
    vacation: "Vacation", vacationSub: "until {t} · frost protection in all scheduled rooms", vacationBtn: "Vacation…", vacationTitle: "Vacation until", vacationHint: "Until then frost protection in all rooms with a profile or frost protection, then the schedule continues. Manual rooms stay untouched.", vacationStart: "Start vacation", vacationEnd: "End vacation",
    away: "Nobody home · at most {t} °C", home: "Somebody home",
    probNotAccepting: "{n} ignores its setpoint", probNotResponding: "{n} does not respond", probUnavailable: "{n} unavailable for over 1 h", probHint: "Details under Settings › Repairs",
    override: "Override", overrideTitle: "Override {r}", overrideFor: "For how long?", untilNext: "Until next change", untilNextAt: "Until the change at {t}",
    overrideActive: "{v} until {t}", overrideEnd: "End", overrideHint: "Afterwards the room follows its plan again.", overrideHintManual: "Afterwards the thermostat gets its previous setpoint back.",
  },
};

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pad = (n) => String(n).padStart(2, "0");
const toMin = (s) => { const p = String(s).split(":").map(Number); return p[0] * 60 + (p[1] || 0); };
const hm = (m) => `${pad(Math.floor(m / 60))}:${pad(m % 60)}`;
const snap = (m) => Math.max(0, Math.min(1440, Math.round(m / SNAP) * SNAP));
const tempColor = (t) => { const x = Math.max(0, Math.min(1, (Number(t) - 15) / 8)); return `hsl(${Math.round(205 - 190 * x)}, 72%, 52%)`; };

class HeatManagerCard extends HTMLElement {
  setConfig(config) {
    this._c = Object.assign({ hour_height: 22, default_temp: 20 }, config || {});
    this._drafts = this._drafts || {};
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
  }
  static getStubConfig() { return {}; }
  getCardSize() { return 16; }
  getGridOptions() { return { columns: "full", rows: "auto" }; }

  connectedCallback() {
    this._tick = setInterval(() => this._updateNow(), 60000);
    if (this._hass && !this._unsub) this._subscribe();
  }
  disconnectedCallback() {
    clearInterval(this._tick);
    if (this._unsub) { this._unsub.then((u) => u && u()).catch(() => {}); this._unsub = null; }
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._unsub && this.isConnected) this._subscribe();
    const sig = this._sig();
    if (sig !== this._lastSig) {
      this._lastSig = sig;
      if (this._drag || this._dlg) this._pending = true; else this._render();
    }
  }

  _subscribe() {
    this._unsub = this._hass.connection
      .subscribeMessage((data) => {
        this._data = data; this._err = null;
        if (!this._sel || !data.profiles.find((p) => p.id === this._sel)) this._sel = data.profiles[0] && data.profiles[0].id;
        this._lastSig = this._sig();
        if (this._drag || this._dlg) this._pending = true; else this._render();
      }, { type: "heatmanager/subscribe" })
      .catch((e) => { this._err = this._t("notLoaded"); this._unsub = null; this._render(); console.warn("HeatManager:", e); });
  }

  _t(key, vars = {}) {
    const lang = ((this._hass && (this._hass.locale?.language || this._hass.language)) || "en").split("-")[0];
    const dict = I18N[lang] || I18N.en;
    let s = dict[key] ?? I18N.en[key] ?? key;
    if (typeof s === "string") Object.entries(vars).forEach(([k, v]) => { s = s.replaceAll(`{${k}}`, v); });
    return s;
  }
  _admin() { return !!(this._hass && this._hass.user && this._hass.user.is_admin); }

  _sig() {
    if (!this._hass) return "";
    const ids = [];
    (this._data?.rooms || []).forEach((r) => { ids.push(...r.climates, ...r.windows); });
    return JSON.stringify(ids.map((id) => { const s = this._hass.states[id]; return s ? [s.state, s.attributes.temperature, s.attributes.current_temperature] : null; }));
  }

  _folded() {
    if (!this._fold) { try { this._fold = JSON.parse(localStorage.getItem("heatmanager-card:folded") || "{}"); } catch (_) { this._fold = {}; } }
    return this._fold;
  }
  _toggleFold(key) {
    const f = this._folded(); f[key] = !f[key];
    try { localStorage.setItem("heatmanager-card:folded", JSON.stringify(f)); } catch (_) { /* private mode */ }
    this._render();
  }
  _sec(key, icon, title, body, extra = "") {
    const shut = !!this._folded()[key];
    return `<div class="sec ${shut ? "shut" : ""}"><button class="stitle" data-fold="${key}" aria-expanded="${!shut}"><ha-icon icon="${icon}"></ha-icon><span>${title}</span>${extra}
      <ha-icon class="chev" icon="mdi:chevron-down"></ha-icon></button>${shut ? "" : body}</div>`;
  }

  _profiles() { return this._data?.profiles || []; }
  _cur() { return this._profiles().find((p) => p.id === this._sel); }
  _pcolor(id) {
    const ps = this._profiles(), i = ps.findIndex((p) => p.id === id);
    if (i < 0) return "var(--disabled-text-color)";
    return ps[i].color || PALETTE[i % PALETTE.length];
  }

  _week(p) {
    if (this._drafts[p.id]) return this._drafts[p.id];
    const w = {};
    DAYS.forEach((d) => {
      w[d] = ((p.week || {})[d] || []).map((b) => ({ from: toMin(b.from), to: toMin(b.to) || 1440, t: Number(b.temp) })).sort((a, b) => a.from - b.from);
    });
    return w;
  }
  _draft(p) {
    if (!this._drafts[p.id]) this._drafts[p.id] = JSON.parse(JSON.stringify(this._week(p)));
    return this._drafts[p.id];
  }
  _weekPayload(w) {
    const out = {};
    DAYS.forEach((d) => { out[d] = (w[d] || []).map((b) => ({ from: hm(b.from), to: b.to >= 1440 ? "24:00" : hm(b.to), temp: b.t })); });
    return out;
  }

  async _ws(msg) {
    try { return await this._hass.callWS(msg); }
    catch (e) { this._toast(this._t("failed", { e: e.message || e.code })); throw e; }
  }
  _toast(message) { this.dispatchEvent(new CustomEvent("hass-notification", { detail: { message }, bubbles: true, composed: true })); }
  _fmtT(t) { return (Math.round(Number(t) * 10) / 10).toLocaleString(this._hass?.locale?.language || this._hass?.language, { minimumFractionDigits: 1, maximumFractionDigits: 1 }); }
  _fmtDate(iso, withDay = true) {
    const d = new Date(iso); if (isNaN(d)) return "";
    const loc = this._hass?.locale?.language || undefined;
    const time = d.toLocaleTimeString(loc, { hour: "2-digit", minute: "2-digit" });
    const today = new Date(); const sameDay = d.toDateString() === today.toDateString();
    if (!withDay || sameDay) return time;
    return d.toLocaleDateString(loc, { weekday: "short", day: "2-digit", month: "2-digit" }) + ", " + time;
  }

  /* ---------------- rendering ---------------- */
  _render() {
    if (!this.shadowRoot || !this._hass) return;
    this._pending = false;
    const data = this._data;
    if (!data) {
      this.shadowRoot.innerHTML = `<style>${STYLE}</style><ha-card><div class="${this._err ? "err" : "empty"}">${esc(this._err || "…")}</div></ha-card>`;
      return;
    }
    const h = this._hass, c = this._c, admin = this._admin();
    const paused = data.pause.active, vac = data.vacation && data.vacation.until, pres = data.presence || {};
    const away = pres.configured && pres.away ? `<div class="pt2 away"><ha-icon icon="mdi:home-export-outline"></ha-icon>${this._t("away", { t: this._fmtT(pres.away_temp) })}</div>` : "";
    const pauseHtml = vac ? `
      <div class="pause vac">
        <div class="pstat">
          <div class="picon"><ha-icon icon="mdi:airplane"></ha-icon></div>
          <div class="ptxt"><div class="pt1">${this._t("vacation")}</div><div class="pt2">${this._t("vacationSub", { t: esc(this._fmtDate(vac)) })}</div></div>
          <button class="btn primary" data-act="vac-end"><ha-icon icon="mdi:home"></ha-icon>${this._t("vacationEnd")}</button>
        </div>
      </div>` : `
      <div class="pause ${paused ? "on" : ""}">
        <div class="pstat">
          <div class="picon"><ha-icon icon="${paused ? "mdi:pause" : "mdi:play"}"></ha-icon></div>
          <div class="ptxt"><div class="pt1">${this._t(paused ? "paused" : "active")}</div>
            <div class="pt2">${paused ? (data.pause.until ? this._t("pausedUntil", { t: esc(this._fmtDate(data.pause.until)) }) : this._t("pausedOpen")) : this._t("activeSub")}</div>${away}</div>
          ${paused ? `<button class="btn primary" data-act="resume"><ha-icon icon="mdi:play"></ha-icon>${this._t("resume")}</button>` : ""}
        </div>
        <div class="pchips"><span class="plabel">${this._t(paused ? "extend" : "pause")}:</span>
          ${[2, 8, 24].map((n) => `<button class="chip" data-pause="${n}">${this._t("hours", { n })}</button>`).join("")}
          <button class="chip" data-pause="168">${this._t("week")}</button>
          <button class="chip" data-act="pause-date"><ha-icon icon="mdi:calendar"></ha-icon>${this._t("untilDate")}</button>
          <button class="chip" data-act="vac-date"><ha-icon icon="mdi:airplane"></ha-icon>${this._t("vacationBtn")}</button>
        </div>
      </div>`;

    const tabs = this._profiles().map((q, i) => {
      const n = data.rooms.filter((r) => r.profile === q.id).length;
      return `<button class="tab ${q.id === this._sel ? "sel" : ""}" data-tab="${esc(q.id)}" style="--pc:${this._pcolor(q.id)}">
        <ha-icon icon="${esc(q.icon || "mdi:radiator")}"></ha-icon><span>${esc(q.name)}${this._drafts[q.id] ? " •" : ""}</span><em>${n}</em></button>`;
    }).join("") + (admin ? `<button class="tab add" data-act="new-profile"><ha-icon icon="mdi:plus"></ha-icon><span>${this._t("newProfile")}</span></button>` : "");

    let profHtml = "";
    const p = this._cur();
    if (p) {
      const w = this._week(p), hh = c.hour_height, pxm = hh / 60, dn = this._t("days");
      const axis = Array.from({ length: 13 }, (_, i) => `<div class="hlabel" style="top:${i * 2 * hh}px">${pad(i * 2)}:00</div>`).join("");
      const cols = DAYS.map((d, di) => {
        const blocks = w[d].map((b, i) => {
          const top = b.from * pxm, height = Math.max(6, (b.to - b.from) * pxm);
          return `<div class="blk" data-idx="${i}" style="top:${top}px;height:${height}px;background:${tempColor(b.t)}">
            ${admin ? `<div class="hdl top" data-h="top"></div>` : ""}<div class="bt">${this._fmtT(b.t)}°</div>${height >= 34 ? `<div class="bs">${hm(b.from)}–${hm(b.to)}</div>` : ""}${admin ? `<div class="hdl bot" data-h="bot"></div>` : ""}</div>`;
        }).join("");
        return `<div class="col"><div class="dhead"><span>${dn[di]}</span>${admin ? `<button class="ico" data-copyday="${d}" title="${this._t("copyDay")}"><ha-icon icon="mdi:content-copy"></ha-icon></button>` : ""}</div>
          <div class="track ${admin ? "edit" : ""}" data-day="${d}" style="height:${24 * hh}px;background-size:100% ${hh}px">${blocks}<div class="now" data-nowday="${d}"></div></div></div>`;
      }).join("");
      const used = data.rooms.filter((r) => r.profile === p.id).map((r) => r.name);
      const weekOpen = !!this._weekOpen || !!this._drafts[p.id];
      profHtml = `
        <div class="pcard" style="--pc:${this._pcolor(p.id)}">
          <div class="phead">
            <ha-icon icon="${esc(p.icon || "mdi:radiator")}"></ha-icon>
            <div class="pname"><b>${esc(p.name)}</b><small>${used.length ? this._t("usedBy", { r: used.map(esc).join(", ") }) : this._t("usedByNone")}</small></div>
            ${admin ? `<button class="btn small" data-act="edit-profile"><ha-icon icon="mdi:pencil"></ha-icon><span class="lbl">${this._t("editProfile")}</span></button>
              <button class="btn danger small" data-act="del-profile" title="${this._t("deleteProfile")}"><ha-icon icon="mdi:delete-outline"></ha-icon><span class="lbl">${this._t("deleteProfile")}</span></button>` : ""}
          </div>
          <div class="pbar">
            <div class="base"><span>${this._t("base")} <small>${this._t("baseHint")}</small></span>
              <div class="step">${admin ? `<button class="ico" data-base="-0.5"><ha-icon icon="mdi:minus"></ha-icon></button>` : ""}
                <b style="color:${tempColor(p.base_temp)}">${this._fmtT(p.base_temp)} °C</b>
                ${admin ? `<button class="ico" data-base="0.5"><ha-icon icon="mdi:plus"></ha-icon></button>` : ""}</div></div>
          </div>
          ${weekOpen ? `
          <div class="hint"><ha-icon icon="mdi:gesture-swipe-vertical"></ha-icon>${admin ? this._t(window.matchMedia && matchMedia("(pointer: coarse)").matches ? "hintTouch" : "hint") : this._t("adminOnly")}</div>
          <div class="gridwrap"><div class="grid">
            <div class="axis"><div class="dhead"></div><div class="axtrack" style="height:${24 * hh}px">${axis}</div></div>${cols}
          </div></div>
          <button class="btn small weektoggle" data-act="week-close"><ha-icon icon="mdi:chevron-up"></ha-icon>${this._t("hideWeek")}</button>` : `
          <button class="mini" data-act="week-open" title="${this._t("showWeek")}">${DAYS.map((d, di) => `<div class="mrow"><span>${dn[di]}</span><div class="mbar" style="background:${tempColor(p.base_temp)}55">${w[d].map((b) => `<i style="left:${b.from / 14.4}%;width:${(b.to - b.from) / 14.4}%;background:${tempColor(b.t)}"></i>`).join("")}</div></div>`).join("")}</button>
          <button class="btn small weektoggle" data-act="week-open"><ha-icon icon="mdi:calendar-edit"></ha-icon>${this._t("showWeek")}</button>`}
          ${this._drafts[p.id] ? `<div class="savebar"><ha-icon icon="mdi:content-save-alert"></ha-icon><span>${this._t("unsaved", { p: esc(p.name) })}</span>
            <button class="btn" data-act="discard">${this._t("discard")}</button><button class="btn primary" data-act="save">${this._t("save")}</button></div>` : ""}
        </div>`;
    } else {
      profHtml = `<div class="empty">${this._t("noProfiles")}</div>`;
    }

    const options = [...this._profiles().map((q) => [q.id, q.name]), ["frost", this._t("frost")], ["manual", this._t("manual")]];
    const rooms = data.rooms.length ? data.rooms.map((r) => {
      const cl = h.states[r.climates[0]];
      const cur = cl ? cl.attributes.current_temperature : null, tgt = cl ? cl.attributes.temperature : null;
      const unav = !cl || cl.state === "unavailable";
      const win = r.windows.some((wid) => h.states[wid] && h.states[wid].state === "on");
      const next = r.override
        ? `<small class="ovr"><ha-icon icon="mdi:thermometer-alert"></ha-icon>${this._t("overrideActive", { v: this._fmtT(r.override.temp) + "°", t: r.override.until ? esc(this._fmtDate(r.override.until)) : "…" })}</small>`
        : r.next_change && r.next_temp != null ? `<small class="next">${this._t("next", { t: esc(this._fmtDate(r.next_change)), v: this._fmtT(r.next_temp) + "°" })}</small>` : "";
      const probs = (r.problems || []).map((pr) => {
        const st = h.states[pr.entity_id];
        const n = r.climates.length > 1 ? ((st && st.attributes.friendly_name) || pr.entity_id) : "Thermostat";
        return `<small class="prob" title="${this._t("probHint")}"><ha-icon icon="mdi:alert-circle"></ha-icon>${esc(this._t(pr.kind === "unavailable" ? "probUnavailable" : pr.kind === "not_responding" ? "probNotResponding" : "probNotAccepting", { n }))}</small>`;
      }).join("");
      const flags = `${unav ? `<small class="warn"><ha-icon icon="mdi:wifi-off"></ha-icon>${this._t("unreachable")}</small>` : ""}${win ? `<small class="win"><ha-icon icon="mdi:window-open-variant"></ha-icon>${this._t("windowOpen")}</small>` : ""}${probs}${next}`;
      return `<div class="room ${win ? "open" : ""} ${probs ? "problem" : ""}" style="--pc:${this._pcolor(r.profile)}">
        <div class="rtop">
          <button class="rname" data-more="${esc(r.climates[0])}" title="${esc(r.name)}">${esc(r.name)}</button>
          <div class="rtemp"><span>${cur != null ? this._fmtT(cur) + "°" : "–"}</span><ha-icon icon="mdi:arrow-right-thin"></ha-icon><b style="color:${tgt != null ? tempColor(tgt) : "inherit"}">${tgt != null ? this._fmtT(tgt) + "°" : "–"}</b></div>
        </div>
        <div class="rbot">
          <div class="rflags">${flags}</div>
          <button class="ico ${r.override ? "act" : ""}" data-ovr="${esc(r.id)}" title="${this._t("override")}"><ha-icon icon="mdi:thermometer-chevron-up"></ha-icon></button>
          <select data-room="${esc(r.id)}">${options.map(([v, l]) => `<option value="${esc(v)}" ${v === r.profile ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>
        </div>
      </div>`;
    }).join("") : `<div class="empty">${this._t("noRooms")}</div>`;

    let todayHtml = "";
    if (c.show_today !== false && data.rooms.some((r) => r.today)) {
      const rowsT = data.rooms.map((r) => `<div class="trow"><span class="tname">${esc(r.name)}</span><div class="tbar">${(r.today || []).map(([f, t, v, why]) => {
        const w = (t - f) / 14.4, label = v != null && w > 6 ? `${this._fmtT(v)}°` : "";
        const tip = `${hm(f)}–${hm(t)} · ${v != null ? this._fmtT(v) + " °C" : this._t("todayOff")}`;
        return `<div class="tseg ${v == null ? "off" : ""} ${why === "override" ? "ovr" : ""}" style="left:${f / 14.4}%;width:${w}%;${v != null ? `background:${tempColor(v)}` : ""}" title="${esc(tip)}">${label}</div>`;
      }).join("")}<div class="tnow"></div></div></div>`).join("");
      const ticks = [0, 6, 12, 18, 24].map((x) => `<span style="left:${x * 100 / 24}%">${pad(x)}</span>`).join("");
      todayHtml = this._sec("today", "mdi:chart-timeline", this._t("today"),
        `<div class="today">${rowsT}<div class="trow"><span class="tname"></span><div class="tticks">${ticks}</div></div></div>`);
    }

    this.shadowRoot.innerHTML = `<style>${STYLE}</style>
      <ha-card>
        ${pauseHtml}
        ${todayHtml}
        ${this._sec("profiles", "mdi:calendar-week", this._t("profiles"), `<div class="tabs">${tabs}</div>${profHtml}`)}
        ${this._sec("rooms", "mdi:home-thermometer", this._t("rooms"), `<div class="rooms">${rooms}</div>
          <div class="legend">${this._t("legend", { f: this._fmtT(data.settings.frost_temp), d: data.settings.window_delay })}</div>`,
          data.rooms.some((r) => (r.problems || []).length) ? `<ha-icon class="secwarn" icon="mdi:alert-circle"></ha-icon>` : "")}
        ${this._dlgHtml()}
      </ha-card>`;
    this._bind();
    this._updateNow();
  }

  _updateNow() {
    if (!this.shadowRoot) return;
    const now = new Date(), di = (now.getDay() + 6) % 7, m = now.getHours() * 60 + now.getMinutes();
    this.shadowRoot.querySelectorAll(".tnow").forEach((el) => { el.style.left = (m / 14.4) + "%"; });
    this.shadowRoot.querySelectorAll(".now").forEach((el) => {
      const show = el.dataset.nowday === DAYS[di];
      el.style.display = show ? "block" : "none";
      if (show) el.style.top = (m * this._c.hour_height / 60) + "px";
    });
  }

  /* ---------------- dialogs ---------------- */
  _dlgHtml() {
    const d = this._dlg;
    if (!d) return "";
    const dl = this._t("daysLong"), dn = this._t("days");
    const dayChips = (exclude, sel) => DAYS.map((k, i) => k === exclude ? "" : `<button class="chip day ${sel.includes(k) ? "on" : ""}" data-dday="${k}">${dn[i]}</button>`).join("");
    const stepper = `<div class="drow tstep"><button class="ico big" data-dt="-0.5"><ha-icon icon="mdi:minus"></ha-icon></button>
      <div class="tval" style="color:${tempColor(d.t)}">${this._fmtT(d.t)} °C</div><button class="ico big" data-dt="0.5"><ha-icon icon="mdi:plus"></ha-icon></button></div>`;
    let body = "";
    if (d.kind === "block") {
      body = `<div class="dtitle">${dl[DAYS.indexOf(d.day)]} · ${this._t("block")}</div>
        <div class="drow"><label>${this._t("from")}<input type="time" step="900" id="dfrom" value="${hm(d.from)}"></label>
        <label>${this._t("to")}<input type="time" step="900" id="dto" value="${hm(d.to >= 1440 ? 0 : d.to)}"></label></div>
        ${stepper}
        <div class="dsub">${this._t("alsoFor")}</div>
        <div class="dchips">${dayChips(d.day, d.copy)}<button class="chip mini" data-dset="work">${this._t("monFri")}</button><button class="chip mini" data-dset="all">${this._t("all")}</button></div>
        <div class="dbtns">${d.idx != null ? `<button class="btn danger" data-dact="delete"><ha-icon icon="mdi:delete"></ha-icon>${this._t("del")}</button>` : ""}<span class="sp"></span>
          <button class="btn" data-dact="cancel">${this._t("cancel")}</button><button class="btn primary" data-dact="apply">${this._t("apply")}</button></div>`;
    } else if (d.kind === "copyday") {
      body = `<div class="dtitle">${this._t("copyTo", { d: dl[DAYS.indexOf(d.day)] })}</div>
        <div class="dchips">${dayChips(d.day, d.copy)}<button class="chip mini" data-dset="work">${this._t("monFri")}</button><button class="chip mini" data-dset="weekend">${this._t("weekend")}</button><button class="chip mini" data-dset="all">${this._t("all")}</button></div>
        <div class="dsub">${this._t("copyHint")}</div>
        <div class="dbtns"><button class="btn danger" data-dact="clearday"><ha-icon icon="mdi:eraser"></ha-icon>${this._t("clearDay")}</button><span class="sp"></span>
          <button class="btn" data-dact="cancel">${this._t("cancel")}</button><button class="btn primary" data-dact="apply">${this._t("copy")}</button></div>`;
    } else if (d.kind === "editprofile") {
      body = `<div class="dtitle">${this._t("editTitle")}</div>
        <div class="drow"><label>${this._t("name")}<input type="text" id="dname" maxlength="30" value="${esc(d.name)}"></label></div>
        ${this._lookHtml(d)}
        <div class="dbtns"><span class="sp"></span><button class="btn" data-dact="cancel">${this._t("cancel")}</button><button class="btn primary" data-dact="apply">${this._t("save")}</button></div>`;
    } else if (d.kind === "newprofile") {
      const tpl = this._profiles().map((q) => `<option value="${esc(q.id)}" ${d.template === q.id ? "selected" : ""}>${this._t("copyOf", { p: esc(q.name) })}</option>`).join("");
      body = `<div class="dtitle">${this._t("newTitle")}</div>
        <div class="drow"><label>${this._t("name")}<input type="text" id="dname" maxlength="30" placeholder="${this._t("namePh")}" value="${esc(d.name)}"></label></div>
        ${this._lookHtml(d)}
        <div class="drow"><label>${this._t("startWith")}<select id="dtpl"><option value="">${this._t("empty")}</option>${tpl}</select></label></div>
        <div class="dsub">${this._t("base")} ${this._t("baseHint")}</div>
        ${stepper}
        ${d.busy ? `<div class="dsub">${this._t("creating")}</div>` : ""}
        <div class="dbtns"><span class="sp"></span><button class="btn" data-dact="cancel">${this._t("cancel")}</button><button class="btn primary" data-dact="apply" ${d.busy ? "disabled" : ""}>${this._t("create")}</button></div>`;
    } else if (d.kind === "delprofile") {
      body = `<div class="dtitle">${this._t("delTitle", { p: esc(d.name) })}</div>
        <div class="dsub">${d.used.length ? this._t("delUsed", { r: d.used.map(esc).join(", ") }) : this._t("delUnused")}</div>
        <div class="dsub">${this._t("delFinal")}</div>
        <div class="dbtns"><span class="sp"></span><button class="btn" data-dact="cancel">${this._t("cancel")}</button><button class="btn dangerfill" data-dact="apply">${this._t("del")}</button></div>`;
    } else if (d.kind === "override") {
      const r = (this._data.rooms || []).find((x) => x.id === d.room) || {};
      const opts = [[1, this._t("hours", { n: 1 })], [2, this._t("hours", { n: 2 })], [4, this._t("hours", { n: 4 })]];
      if (r.plan_change) opts.push(["next", this._t("untilNextAt", { t: esc(this._fmtDate(r.plan_change)) })]);
      body = `<div class="dtitle">${this._t("overrideTitle", { r: esc(r.name) })}</div>
        ${stepper}
        <div class="dsub">${this._t("overrideFor")}</div>
        <div class="dchips">${opts.map(([v, l]) => `<button class="chip ${String(d.dur) === String(v) ? "on" : ""}" data-ddur="${v}">${l}</button>`).join("")}</div>
        <div class="dsub">${this._t(r.plan_change ? "overrideHint" : "overrideHintManual")}</div>
        <div class="dbtns">${r.override ? `<button class="btn danger" data-dact="endovr"><ha-icon icon="mdi:close"></ha-icon>${this._t("overrideEnd")}</button>` : ""}<span class="sp"></span>
          <button class="btn" data-dact="cancel">${this._t("cancel")}</button><button class="btn primary" data-dact="apply">${this._t("apply")}</button></div>`;
    } else if (d.kind === "pausedate" || d.kind === "vacdate") {
      const vac = d.kind === "vacdate";
      body = `<div class="dtitle">${this._t(vac ? "vacationTitle" : "pauseTitle")}</div>
        <div class="drow"><label>${this._t("dateTime")}<input type="datetime-local" id="ddt" value="${d.value}"></label></div>
        <div class="dsub">${this._t(vac ? "vacationHint" : "pauseHint")}</div>
        <div class="dbtns"><span class="sp"></span><button class="btn" data-dact="cancel">${this._t("cancel")}</button><button class="btn primary" data-dact="apply">${this._t(vac ? "vacationStart" : "pause")}</button></div>`;
    }
    // a native modal dialog sits in the top layer: always centred in the visible screen, whatever is scrolled
    return `<dialog class="overlay"><div class="dlg" tabindex="-1" autofocus>${body}</div></dialog>`;
  }

  _lookHtml(d) {
    return `<div class="dsub">${this._t("icon")}</div>
      <div class="dchips">${ICONS.map((i) => `<button class="chip icon ${d.icon === i ? "on" : ""}" data-dicon="${i}"><ha-icon icon="${i}"></ha-icon></button>`).join("")}</div>
      <div class="dsub">${this._t("color")}</div>
      <div class="dchips">${PALETTE.map((c) => `<button class="swatch ${d.color === c ? "on" : ""}" data-dcolor="${c}" style="background:${c}"></button>`).join("")}</div>`;
  }

  _closeDlg() { this._dlg = null; this._render(); }

  async _applyDlg() {
    const d = this._dlg, p = this._cur(), r = this.shadowRoot;
    if (d.kind === "pausedate" || d.kind === "vacdate") {
      const v = r.getElementById("ddt").value, dt = new Date(v);
      if (!v || isNaN(dt) || dt <= new Date()) { this._toast(this._t("errFuture")); return; }
      await this._ws({ type: d.kind === "vacdate" ? "heatmanager/vacation" : "heatmanager/pause", until: dt.toISOString() }).catch(() => {});
      this._closeDlg(); return;
    }
    if (d.kind === "override") {
      const msg = { type: "heatmanager/room/override", room_id: d.room, temp: d.t };
      if (d.dur === "next") msg.until_next_change = true; else msg.hours = Number(d.dur);
      await this._ws(msg).catch(() => {});
      this._closeDlg(); return;
    }
    if (d.kind === "editprofile") {
      const name = (r.getElementById("dname").value || "").trim();
      if (!name) { this._toast(this._t("errName")); return; }
      try { await this._ws({ type: "heatmanager/profile/save", profile_id: d.id, name, icon: d.icon, color: d.color }); this._closeDlg(); } catch (e) { /* toast shown */ }
      return;
    }
    if (d.kind === "newprofile") {
      const name = (r.getElementById("dname").value || "").trim();
      const tplId = r.getElementById("dtpl").value;
      if (!name) { this._toast(this._t("errName")); return; }
      const tpl = this._profiles().find((q) => q.id === tplId);
      d.busy = true; d.name = name; d.template = tplId; this._render();
      try {
        const res = await this._ws({ type: "heatmanager/profile/save", name, icon: d.icon, color: d.color, base_temp: d.t, week: tpl ? tpl.week : {} });
        this._sel = res.profile_id; this._weekOpen = true; this._dlg = null; this._toast(this._t("created", { p: name })); this._render();
      } catch (e) { d.busy = false; this._render(); }
      return;
    }
    if (d.kind === "delprofile") {
      try { await this._ws({ type: "heatmanager/profile/delete", profile_id: d.id }); delete this._drafts[d.id]; this._toast(this._t("deleted", { p: d.name })); this._sel = null; } catch (e) { /* toast shown */ }
      this._closeDlg(); return;
    }
    if (!p) return;
    const w = this._draft(p);
    if (d.kind === "copyday") { d.copy.forEach((k) => { w[k] = JSON.parse(JSON.stringify(w[d.day])); }); this._closeDlg(); return; }
    const f = toMin(r.getElementById("dfrom").value || "00:00");
    let t = toMin(r.getElementById("dto").value || "00:00");
    if (t === 0) t = 1440;
    if (t - f < SNAP) { this._toast(this._t("errOrder")); return; }
    const blk = { from: snap(f), to: snap(t), t: d.t };
    this._lastT = d.t;
    if (d.idx != null) w[d.day].splice(d.idx, 1);
    w[d.day] = this._place(w[d.day], blk);
    d.copy.forEach((k) => { w[k] = this._place(w[k], { ...blk }); });
    this._closeDlg();
  }

  _place(list, blk) {
    const out = [];
    list.forEach((b) => {
      if (b.to <= blk.from || b.from >= blk.to) { out.push(b); return; }
      if (b.from < blk.from) out.push({ ...b, to: blk.from });
      if (b.to > blk.to) out.push({ ...b, from: blk.to });
    });
    out.push(blk);
    return out.filter((b) => b.to - b.from >= SNAP).sort((a, b) => a.from - b.from);
  }

  async _save() {
    const p = this._cur(); if (!p || !this._drafts[p.id]) return;
    try {
      await this._ws({ type: "heatmanager/profile/save", profile_id: p.id, name: p.name, week: this._weekPayload(this._drafts[p.id]) });
      delete this._drafts[p.id]; this._toast(this._t("saved", { p: p.name })); this._render();
    } catch (e) { /* toast shown */ }
  }

  _bind() {
    const r = this.shadowRoot;
    const on = (sel, fn) => r.querySelectorAll(sel).forEach((el) => el.addEventListener("click", (e) => fn(el, e)));
    on("[data-pause]", (b) => this._ws({ type: "heatmanager/pause", hours: Number(b.dataset.pause) }).catch(() => {}));
    on("[data-act]", (b) => {
      const a = b.dataset.act;
      if (a === "resume") this._ws({ type: "heatmanager/resume" }).catch(() => {});
      if (a === "save") this._save();
      if (a === "week-open") { this._weekOpen = true; this._render(); }
      if (a === "week-close") { this._weekOpen = false; this._render(); }
      if (a === "discard") { delete this._drafts[this._sel]; this._render(); }
      if (a === "new-profile") { this._dlg = { kind: "newprofile", name: "", icon: ICONS[0], color: PALETTE[this._profiles().length % PALETTE.length], template: "", t: 17 }; this._render(); }
      if (a === "edit-profile") {
        const p = this._cur(); if (!p) return;
        this._dlg = { kind: "editprofile", id: p.id, name: p.name, icon: p.icon || ICONS[0], color: this._pcolor(p.id) }; this._render();
      }
      if (a === "del-profile") {
        const p = this._cur(); if (!p) return;
        this._dlg = { kind: "delprofile", id: p.id, name: p.name, used: this._data.rooms.filter((x) => x.profile === p.id).map((x) => x.name) }; this._render();
      }
      if (a === "vac-end") this._ws({ type: "heatmanager/vacation", end: true }).catch(() => {});
      if (a === "vac-date") {
        const d = new Date(Date.now() + 7 * 86400000); d.setHours(16, 0, 0, 0);
        this._dlg = { kind: "vacdate", value: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T16:00` }; this._render();
      }
      if (a === "pause-date") {
        const d = new Date(Date.now() + 3 * 86400000); d.setHours(16, 0, 0, 0);
        this._dlg = { kind: "pausedate", value: `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T16:00` }; this._render();
      }
    });
    on("[data-tab]", (b) => {
      // choosing a profile opens its week plan; tapping the open one again folds it
      this._weekOpen = b.dataset.tab === this._sel ? !this._weekOpen : true;
      this._sel = b.dataset.tab; this._render();
    });
    on("[data-fold]", (b) => this._toggleFold(b.dataset.fold));
    on("[data-base]", (b) => {
      const p = this._cur(); if (!p) return;
      const v = Math.max(5, Math.min(25, Number(p.base_temp) + Number(b.dataset.base)));
      this._ws({ type: "heatmanager/profile/save", profile_id: p.id, name: p.name, base_temp: v }).catch(() => {});
    });
    on("[data-more]", (b) => this.dispatchEvent(new CustomEvent("hass-more-info", { detail: { entityId: b.dataset.more }, bubbles: true, composed: true })));
    r.querySelectorAll("select[data-room]").forEach((s) => s.addEventListener("change", () => {
      this._ws({ type: "heatmanager/room/set_profile", room_id: s.dataset.room, profile: s.value }).catch(() => {});
    }));
    on("[data-ovr]", (b) => {
      const r = this._data.rooms.find((x) => x.id === b.dataset.ovr); if (!r) return;
      const cl = this._hass.states[r.climates[0]];
      const base = r.override ? r.override.temp : Number((cl && cl.attributes.temperature) ?? r.target ?? 20) + 1;
      this._dlg = { kind: "override", room: r.id, t: Math.max(5, Math.min(28, Math.round(base * 2) / 2)), dur: r.override ? (r.plan_change ? "next" : 2) : 2 };
      this._render();
    });
    on("[data-copyday]", (b, e) => { e.stopPropagation(); this._dlg = { kind: "copyday", day: b.dataset.copyday, copy: [] }; this._render(); });
    r.querySelectorAll(".track.edit").forEach((t) => {
      t.addEventListener("pointerdown", (e) => this._down(e, t));
      // while a held block is dragged, the page must not scroll along
      t.addEventListener("touchmove", (e) => { if (this._drag && this._drag.active) e.preventDefault(); }, { passive: false });
      t.addEventListener("contextmenu", (e) => e.preventDefault());
    });

    const dlg = this._dlg;
    if (!dlg) return;
    const ov = r.querySelector(".overlay");
    if (!ov.open) { try { ov.showModal(); } catch (_) { ov.setAttribute("open", ""); } }
    ov.addEventListener("cancel", (e) => { e.preventDefault(); this._closeDlg(); });
    ov.addEventListener("click", (e) => { if (e.target === ov && Date.now() - (this._dlgAt || 0) > 500) this._closeDlg(); });
    const keep = () => {
      const f = r.getElementById("dfrom"), t = r.getElementById("dto"), n = r.getElementById("dname"), tp = r.getElementById("dtpl");
      if (f) dlg.from = toMin(f.value || "00:00");
      if (t) { const v = toMin(t.value || "00:00"); dlg.to = v === 0 ? 1440 : v; }
      if (n) dlg.name = n.value;
      if (tp) dlg.template = tp.value;
    };
    on("[data-dact]", (b, e) => {
      e.stopPropagation();
      const a = b.dataset.dact;
      if (a === "cancel") this._closeDlg();
      if (a === "apply") this._applyDlg();
      if (a === "delete") { this._draft(this._cur())[dlg.day].splice(dlg.idx, 1); this._closeDlg(); }
      if (a === "endovr") { this._ws({ type: "heatmanager/room/clear_override", room_id: dlg.room }).catch(() => {}); this._closeDlg(); }
      if (a === "clearday") { this._draft(this._cur())[dlg.day] = []; this._closeDlg(); }
    });
    on("[data-ddur]", (b) => { dlg.dur = b.dataset.ddur; this._render(); });
    on("[data-dicon]", (b) => { keep(); dlg.icon = b.dataset.dicon; this._render(); });
    on("[data-dcolor]", (b) => { keep(); dlg.color = b.dataset.dcolor; this._render(); });
    on("[data-dt]", (b) => { keep(); dlg.t = Math.max(5, Math.min(28, Math.round((dlg.t + Number(b.dataset.dt)) * 10) / 10)); this._render(); });
    on("[data-dday]", (b) => { keep(); const k = b.dataset.dday; dlg.copy = dlg.copy.includes(k) ? dlg.copy.filter((x) => x !== k) : [...dlg.copy, k]; this._render(); });
    on("[data-dset]", (b) => {
      keep();
      const set = { work: DAYS.slice(0, 5), weekend: DAYS.slice(5), all: DAYS }[b.dataset.dset].filter((k) => k !== dlg.day);
      dlg.copy = set.every((k) => dlg.copy.includes(k)) ? dlg.copy.filter((k) => !set.includes(k)) : [...new Set([...dlg.copy, ...set])];
      this._render();
    });
    const nameIn = r.getElementById("dname");
    if (nameIn && !dlg.focused) { dlg.focused = true; setTimeout(() => nameIn.focus(), 50); }
  }

  /* ---------------- dragging in the grid ---------------- */
  _down(e, track) {
    if (e.button !== undefined && e.button !== 0) return;
    if (this._drag) return;
    const p = this._cur(); if (!p) return;
    const day = track.dataset.day, pxm = this._c.hour_height / 60, rect = track.getBoundingClientRect();
    const minAt = (ev) => snap((ev.clientY - rect.top) / pxm);
    const list = this._week(p)[day];
    const blkEl = e.target.closest(".blk");
    // Touch: a normal swipe scrolls the page; press and hold first to drag
    const touch = e.pointerType !== "mouse";
    let drag;
    if (blkEl) {
      const idx = Number(blkEl.dataset.idx), b = list[idx];
      const lo = idx > 0 ? list[idx - 1].to : 0, hi = idx < list.length - 1 ? list[idx + 1].from : 1440;
      drag = { mode: e.target.dataset.h || "move", day, idx, lo, hi, from: b.from, to: b.to, t: b.t, origFrom: b.from, origTo: b.to, startMin: minAt(e), el: blkEl };
    } else {
      const m = minAt(e);
      if (list.some((b) => m >= b.from && m < b.to)) return;
      const lo = list.filter((b) => b.to <= m).reduce((a, b) => Math.max(a, b.to), 0);
      const hi = list.filter((b) => b.from >= m).reduce((a, b) => Math.min(a, b.from), 1440);
      drag = { mode: "create", day, lo, hi, start: m, cur: m, el: null };
    }
    Object.assign(drag, { startX: e.clientX, startY: e.clientY, moved: false, active: false, pid: e.pointerId,
      // a finger always wobbles a little: only count it as dragging beyond this distance
      slop: touch ? 12 : 4 });
    this._drag = drag;
    const upd = () => {
      const d = this._drag; if (!d || !d.el) return;
      const f = d.mode === "create" ? Math.min(d.start, d.cur) : d.from, t = d.mode === "create" ? Math.max(d.start, d.cur) : d.to;
      d.el.style.top = f * pxm + "px"; d.el.style.height = Math.max(4, (t - f) * pxm) + "px";
      if (d.mode === "create") d.el.innerHTML = t - f >= SNAP ? `<div class="bs">${hm(f)}–${hm(t)}</div>` : "";
      else { const bs = d.el.querySelector(".bs"); if (bs) bs.textContent = `${hm(f)}–${hm(t)}`; }
    };
    const activate = () => {
      const d = this._drag; if (!d || d.active) return;
      d.active = true; d.timer = null;
      if (d.mode === "create") { d.el = document.createElement("div"); d.el.className = "blk ghost"; track.appendChild(d.el); }
      d.el.classList.add("lift"); track.classList.add("dragging");
      try { track.setPointerCapture(d.pid); } catch (_) { /* ignore */ }
      try { navigator.vibrate && navigator.vibrate(15); } catch (_) { /* ignore */ }
      upd();
    };
    const cleanup = () => {
      track.removeEventListener("pointermove", move); track.removeEventListener("pointerup", up); track.removeEventListener("pointercancel", cancel);
      track.classList.remove("dragging");
      const d = this._drag; this._drag = null;
      if (d && d.timer) clearTimeout(d.timer);
      return d;
    };
    const move = (ev) => {
      const d = this._drag; if (!d || ev.pointerId !== d.pid) return;
      if (!d.active) {
        // finger moved before the hold time: it is a scroll, let the browser have it
        if (Math.hypot(ev.clientX - d.startX, ev.clientY - d.startY) > 10) { cleanup(); if (this._pending) this._render(); }
        return;
      }
      if (Math.abs(ev.clientY - d.startY) > d.slop) d.moved = true;
      if (!d.moved) return;
      const m = minAt(ev);
      if (d.mode === "create") d.cur = Math.max(d.lo, Math.min(d.hi, m));
      else if (d.mode === "top") d.from = Math.max(d.lo, Math.min(d.to - SNAP, m));
      else if (d.mode === "bot") d.to = Math.min(d.hi, Math.max(d.from + SNAP, m));
      else { const len = d.to - d.from; let nf = snap(d.from + (m - d.startMin)); nf = Math.max(d.lo, Math.min(d.hi - len, nf)); d.startMin += nf - d.from; d.to = nf + len; d.from = nf; }
      upd();
    };
    const cancel = (ev) => {
      const d = this._drag; if (!d || ev.pointerId !== d.pid) return;
      cleanup(); this._render();
    };
    const up = (ev) => {
      const d0 = this._drag; if (!d0 || ev.pointerId !== d0.pid) return;
      const d = cleanup();
      if (d.mode === "create") {
        if (d.el) d.el.remove();
        let f = Math.min(d.start, d.cur), t = Math.max(d.start, d.cur);
        if (t - f < SNAP) { f = d.start; t = Math.min(d.hi, f + 60); if (t - f < SNAP) { this._render(); return; } }
        this._dlg = { kind: "block", day: d.day, idx: null, from: f, to: t, t: this._lastT || this._c.default_temp, copy: [] };
      } else if (!d.moved || (d.from === d.origFrom && d.to === d.origTo)) {
        // tap (or a drag that changed nothing): open the block
        this._dlg = { kind: "block", day: d.day, idx: d.idx, from: d.from, to: d.to, t: d.t, copy: [] };
      } else {
        this._draft(p)[d.day][d.idx] = { from: d.from, to: d.to, t: d.t };
      }
      // the click that follows a tap must not land on the new overlay and close it right away
      this._dlgAt = Date.now();
      this._render();
    };
    track.addEventListener("pointermove", move); track.addEventListener("pointerup", up); track.addEventListener("pointercancel", cancel);
    if (touch) {
      drag.timer = setTimeout(activate, HOLD_MS);
    } else {
      e.preventDefault();
      activate();
    }
  }
}

const STYLE = `
:host { display:block; }
ha-card { padding:16px; position:relative; overflow:hidden; }
button { font:inherit; color:inherit; cursor:pointer; }
ha-icon { --mdc-icon-size:18px; }
.pause { display:flex; flex-wrap:wrap; align-items:center; gap:12px 20px; padding:14px 16px; border-radius:16px;
  background:linear-gradient(135deg, rgba(76,175,80,.16), rgba(76,175,80,.04)); border:1px solid rgba(76,175,80,.35); }
.pause.on { background:linear-gradient(135deg, rgba(255,152,0,.20), rgba(255,152,0,.05)); border-color:rgba(255,152,0,.45); }
.pstat { display:flex; align-items:center; gap:12px; flex:1 1 320px; }
.picon { width:42px; height:42px; border-radius:50%; display:grid; place-items:center; background:rgb(76,175,80); color:#fff; flex:none; }
.pause.on .picon { background:rgb(255,152,0); }
.pause.vac { background:linear-gradient(135deg, rgba(3,169,244,.20), rgba(3,169,244,.05)); border-color:rgba(3,169,244,.45); }
.pause.vac .picon { background:rgb(3,169,244); }
.pt2.away { display:flex; align-items:center; gap:4px; color:rgb(3,169,244); } .pt2.away ha-icon { --mdc-icon-size:15px; }
.picon ha-icon { --mdc-icon-size:24px; }
.pt1 { font-size:1.1em; font-weight:600; } .pt2 { color:var(--secondary-text-color); font-size:.9em; }
.pchips { display:flex; flex-wrap:wrap; align-items:center; gap:8px; }
.plabel { color:var(--secondary-text-color); font-size:.9em; margin-right:2px; }
.chip { border:1px solid var(--divider-color); background:var(--card-background-color); border-radius:999px; padding:6px 14px; display:inline-flex; align-items:center; gap:6px; font-size:.9em; transition:background .15s; }
.chip:hover { background:var(--secondary-background-color); }
.chip.on { background:var(--primary-color); color:var(--text-primary-color, #fff); border-color:var(--primary-color); }
.chip.mini { padding:4px 10px; font-size:.8em; opacity:.85; }
.chip.icon { padding:6px 10px; } .chip.icon ha-icon { --mdc-icon-size:20px; }
.chip.day { min-width:44px; justify-content:center; }
.btn { border:none; border-radius:10px; padding:8px 14px; background:var(--secondary-background-color); display:inline-flex; align-items:center; gap:6px; font-weight:500; }
.btn.primary { background:var(--primary-color); color:var(--text-primary-color, #fff); }
.btn.danger { background:transparent; color:var(--error-color, #db4437); }
.btn.dangerfill { background:var(--error-color, #db4437); color:#fff; }
.btn.small { padding:6px 10px; font-size:.85em; }
.btn[disabled] { opacity:.5; pointer-events:none; }
.ico { border:none; background:transparent; width:30px; height:30px; border-radius:50%; display:grid; place-items:center; padding:0; color:var(--secondary-text-color); }
.ico:hover { background:var(--secondary-background-color); }
.ico.big { width:44px; height:44px; background:var(--secondary-background-color); } .ico.big ha-icon { --mdc-icon-size:24px; }
.sec { margin-top:20px; }
.stitle { display:flex; align-items:center; gap:8px; font-size:1.15em; font-weight:500; margin-bottom:10px; width:100%; border:none; background:none; padding:4px 0; text-align:left; }
.stitle span { flex:1; } .stitle .chev { transition:transform .2s; color:var(--secondary-text-color); }
.sec.shut .stitle { margin-bottom:0; } .sec.shut .stitle .chev { transform:rotate(-90deg); }
.stitle .secwarn { color:var(--error-color, #db4437); }
.mini { display:flex; flex-direction:column; gap:3px; width:100%; border:none; background:none; padding:4px 0; margin-bottom:8px; }
.mrow { display:flex; align-items:center; gap:8px; font-size:.75em; color:var(--secondary-text-color); } .mrow span { width:22px; text-align:left; }
.mbar { position:relative; flex:1; height:10px; border-radius:3px; overflow:hidden; }
.mbar i { position:absolute; top:0; bottom:0; }
.weektoggle { margin-top:8px; }
.tabs { display:flex; flex-wrap:wrap; gap:8px; margin-bottom:12px; }
.tab { display:flex; align-items:center; gap:8px; padding:8px 14px; border-radius:12px; border:1px solid var(--divider-color); background:var(--card-background-color); }
.tab ha-icon { color:var(--pc); }
.tab em { font-style:normal; font-size:.75em; min-width:18px; padding:1px 6px; border-radius:999px; background:var(--secondary-background-color); color:var(--secondary-text-color); }
.tab.sel { border-color:var(--pc); background:color-mix(in srgb, var(--pc) 18%, var(--card-background-color)); font-weight:600; }
.tab.add { border-style:dashed; color:var(--secondary-text-color); background:transparent; }
.tab.add:hover { color:var(--primary-text-color); border-color:var(--primary-color); }
.tabs .tab.sel { border-bottom-left-radius:4px; border-bottom-right-radius:4px; }
.pcard { border:1px solid color-mix(in srgb, var(--pc) 55%, transparent); background:color-mix(in srgb, var(--pc) 6%, transparent); border-radius:14px; padding:12px; }
.phead { display:flex; align-items:center; gap:10px; padding-bottom:10px; margin-bottom:10px; border-bottom:1px solid var(--divider-color); }
.phead > ha-icon { --mdc-icon-size:24px; color:var(--pc); flex:none; }
.pname { flex:1; min-width:0; display:flex; flex-direction:column; }
.pname b { font-size:1.1em; } .pname small { color:var(--secondary-text-color); font-size:.8em; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.pbar { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-bottom:8px; }
.base { display:flex; align-items:center; gap:12px; } .base small { color:var(--secondary-text-color); }
.step { display:flex; align-items:center; gap:4px; background:var(--secondary-background-color); border-radius:999px; padding:2px 6px; }
.step b { min-width:64px; text-align:center; }
.hint { color:var(--secondary-text-color); font-size:.8em; display:flex; align-items:center; gap:6px; margin-bottom:8px; }
.gridwrap { overflow-x:auto; }
.grid { display:grid; grid-template-columns:44px repeat(7, minmax(56px, 1fr)); gap:4px; min-width:460px; }
.dhead { height:30px; display:flex; align-items:center; justify-content:center; gap:2px; font-weight:600; }
.dhead .ico { width:24px; height:24px; opacity:.55; } .dhead .ico ha-icon { --mdc-icon-size:14px; }
.axtrack { position:relative; }
.hlabel { position:absolute; right:4px; transform:translateY(-50%); font-size:.7em; color:var(--secondary-text-color); }
.hlabel:first-child { transform:none; }
.track { position:relative; border-radius:10px; background-color:var(--secondary-background-color); background-image:linear-gradient(to bottom, var(--divider-color) 1px, transparent 1px); user-select:none; }
.track.edit { touch-action:pan-x pan-y; cursor:crosshair; -webkit-touch-callout:none; -webkit-user-select:none; }
.track.dragging { touch-action:none; }
.blk { position:absolute; left:3px; right:3px; border-radius:8px; color:#fff; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.35); display:flex; flex-direction:column; align-items:center; justify-content:center; text-shadow:0 1px 2px rgba(0,0,0,.4); }
.track.edit .blk { cursor:grab; }
.blk.lift { box-shadow:0 0 0 2px var(--primary-color), 0 6px 16px rgba(0,0,0,.45); z-index:3; }
.blk.ghost { background:color-mix(in srgb, var(--primary-color) 55%, transparent); border:2px dashed var(--primary-color); box-shadow:none; }
.bt { font-weight:700; font-size:.9em; line-height:1.1; } .bs { font-size:.68em; opacity:.95; line-height:1.1; text-align:center; }
.hdl { position:absolute; left:0; right:0; height:9px; cursor:ns-resize; } .hdl.top { top:0; } .hdl.bot { bottom:0; }
.hdl::after { content:""; position:absolute; left:50%; width:18px; height:3px; margin-left:-9px; border-radius:2px; background:rgba(255,255,255,.7); top:3px; }
.now { position:absolute; left:0; right:0; height:2px; background:var(--error-color, #e53935); z-index:2; pointer-events:none; display:none; }
.now::before { content:""; position:absolute; left:-3px; top:-3px; width:8px; height:8px; border-radius:50%; background:var(--error-color, #e53935); }
.savebar { position:sticky; bottom:0; margin-top:12px; display:flex; flex-wrap:wrap; align-items:center; gap:10px; padding:10px 14px; border-radius:12px; background:color-mix(in srgb, var(--primary-color) 16%, var(--card-background-color)); border:1px solid var(--primary-color); }
.savebar span { flex:1; }
.rooms { display:grid; grid-template-columns:repeat(auto-fill, minmax(min(280px, 100%), 1fr)); gap:8px; }
.room { min-width:0; display:flex; flex-direction:column; gap:6px; padding:10px 12px 10px 14px; border-radius:12px; background:var(--secondary-background-color); border-left:4px solid var(--pc); }
.rtop, .rbot { display:flex; align-items:center; gap:8px; min-width:0; }
.rflags { flex:1; min-width:0; display:flex; flex-wrap:wrap; gap:2px 10px; }
.rflags small { display:inline-flex; align-items:center; gap:3px; font-size:.78em; line-height:1.25; min-width:0; } .rflags small ha-icon { --mdc-icon-size:14px; }
.room.open { box-shadow:inset 0 0 0 1px rgba(79,195,247,.6); }
.rname { border:none; background:none; padding:0; text-align:left; flex:1; font-weight:600; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.rflags small.warn { color:var(--warning-color, #ff9800); }
.rflags small.win { color:#4fc3f7; font-weight:500; }
.rflags small.next { color:var(--secondary-text-color); }
.room.problem { box-shadow:inset 0 0 0 1px color-mix(in srgb, var(--error-color, #db4437) 70%, transparent); }
.rflags small.prob { color:var(--error-color, #db4437); }
.rflags small.ovr { color:var(--warning-color, #ff9800); }
.ico.act { color:var(--warning-color, #ff9800); background:color-mix(in srgb, var(--warning-color, #ff9800) 18%, transparent); }
.rtemp { display:flex; align-items:center; gap:2px; font-size:.95em; color:var(--secondary-text-color); white-space:nowrap; flex:none; } .rtemp b { font-weight:600; }
.rbot select { max-width:130px; flex:none; }
select { font:inherit; color:var(--primary-text-color); background:var(--card-background-color); border:1px solid var(--divider-color); border-radius:8px; padding:6px 8px; max-width:150px; }
.today { display:flex; flex-direction:column; gap:6px; }
.trow { display:flex; align-items:center; gap:10px; }
.tname { width:110px; flex:none; font-size:.85em; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.tbar { position:relative; flex:1; height:22px; border-radius:6px; background:var(--secondary-background-color); overflow:hidden; }
.tseg { position:absolute; top:0; bottom:0; display:flex; align-items:center; justify-content:center; font-size:.7em; font-weight:600; color:#fff; text-shadow:0 1px 2px rgba(0,0,0,.45); border-right:1px solid var(--card-background-color); box-sizing:border-box; overflow:hidden; white-space:nowrap; }
.tseg.off { background:repeating-linear-gradient(45deg, transparent 0 4px, var(--divider-color) 4px 5px); }
.tseg.ovr { box-shadow:inset 0 0 0 2px var(--warning-color, #ff9800); }
.tnow { position:absolute; top:-2px; bottom:-2px; width:2px; margin-left:-1px; background:var(--error-color, #e53935); }
.tticks { position:relative; flex:1; height:14px; font-size:.7em; color:var(--secondary-text-color); }
.tticks span { position:absolute; transform:translateX(-50%); } .tticks span:first-child { transform:none; } .tticks span:last-child { transform:translateX(-100%); }
.swatch { width:30px; height:30px; border-radius:50%; border:2px solid transparent; padding:0; }
.swatch.on { border-color:var(--primary-text-color); box-shadow:0 0 0 2px var(--card-background-color) inset; }
.legend { margin-top:8px; font-size:.8em; color:var(--secondary-text-color); }
.err { padding:14px; border-radius:10px; background:rgba(219,68,55,.12); color:var(--error-color, #db4437); }
.empty { color:var(--secondary-text-color); padding:20px; text-align:center; }
dialog.overlay { padding:16px; margin:0; border:none; background:transparent; width:100%; height:100%; max-width:none; max-height:none; box-sizing:border-box; display:flex; align-items:center; justify-content:center; color:var(--primary-text-color); }
dialog.overlay::backdrop { background:rgba(0,0,0,.5); }
.dlg { max-height:calc(100% - 16px); overflow:auto; outline:none; }
.dlg { background:var(--card-background-color); border-radius:18px; padding:20px; width:min(420px, 92%); box-shadow:0 10px 30px rgba(0,0,0,.5); }
.dtitle { font-size:1.15em; font-weight:600; margin-bottom:14px; }
.drow { display:flex; gap:12px; margin-bottom:14px; }
.drow label { flex:1; display:flex; flex-direction:column; gap:4px; font-size:.85em; color:var(--secondary-text-color); }
.drow input, .drow select { font:inherit; font-size:1.05em; padding:8px; border-radius:8px; border:1px solid var(--divider-color); background:var(--secondary-background-color); color:var(--primary-text-color); color-scheme:dark light; max-width:none; }
.tstep { align-items:center; justify-content:center; gap:18px; }
.tval { font-size:1.8em; font-weight:700; min-width:110px; text-align:center; }
.dsub { font-size:.85em; color:var(--secondary-text-color); margin:6px 0 8px; }
.dchips { display:flex; flex-wrap:wrap; gap:6px; margin-bottom:16px; }
.dbtns { display:flex; gap:8px; align-items:center; } .sp { flex:1; }
@media (max-width:600px) { ha-card { padding:12px; } .phead .lbl { display:none; } .pcard { padding:8px; } .base small { display:none; } .rooms { grid-template-columns:minmax(0, 1fr); } .tname { width:80px; } }
`;

if (!customElements.get("heatmanager-card")) {
  customElements.define("heatmanager-card", HeatManagerCard);
  window.customCards = window.customCards || [];
  window.customCards.push({ type: "heatmanager-card", name: "HeatManager", description: "Weekly heating profiles, room assignment, window detection and pause", preview: false });
  console.info(`%c HEATMANAGER-CARD %c v${VERSION} `, "background:#f4a340;color:#000;font-weight:700", "");
}
