const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
process.env.TZ = "UTC";

const bundle = fs.readFileSync(path.join(__dirname, "../custom_components/codex_rates/www/codex-rates-card.js"), "utf8");
const NOW = Date.parse("2026-10-12T09:00:00Z");

function setup(config = {}) {
  let now = NOW;
  const elements = new Map();
  const timers = new Map();
  let nextTimerId = 0;
  class Element {
    constructor() {
      this.style = {
        values: {},
        setProperty(key, value) { this.values[key] = String(value); },
        removeProperty(key) { delete this.values[key]; },
      };
      this.children = [];
      this.innerHTML = "";
      this.isConnected = true;
    }
    attachShadow() { return new Element(); }
    appendChild(child) { this.children.push(child); return child; }
    append(...nodes) {
      for (const node of nodes) {
        if (node instanceof Element) this.appendChild(node);
        else this.textContent = `${this.textContent || ""}${node}`;
      }
    }
    replaceChildren(...nodes) {
      this.children = [];
      this.append(...nodes);
    }
    querySelector(selector) {
      return this.children.find((child) => child.tagName === selector || `.${child.className}` === selector) || null;
    }
    querySelectorAll() { return []; }
    addEventListener(type, fn) { (this._listeners ||= new Map()).set(type, fn); }
    dispatchEvent(event) {
      this.event = event;
      this._listeners?.get(event.type)?.(event);
      return true;
    }
  }
  vm.runInNewContext(bundle, {
    HTMLElement: Element,
    customElements: { get: (name) => elements.get(name), define: (name, cls) => elements.set(name, cls) },
    document: {
      createElement: (tagName) => {
        const Cls = elements.get(tagName);
        const el = Cls ? new Cls() : new Element();
        el.tagName = tagName;
        return el;
      },
    },
    window: {}, console: { info() {} },
    Date: class extends Date { static now() { return now; } },
    Intl,
    CustomEvent: class { constructor(type, options) { this.type = type; Object.assign(this, options); } },
    setInterval: (fn, delay) => {
      const id = ++nextTimerId;
      timers.set(id, { fn, delay });
      return id;
    },
    clearInterval: (id) => timers.delete(id),
  });
  const Card = elements.get("codex-rates-card");
  const card = new Card();
  card.setConfig({ entity: "sensor.primary", entities: ["sensor.weekly"], ...config });
  const hass = {
    locale: { language: "en", time_format: "24" }, config: { time_zone: "Australia/Sydney" },
    states: {
      "sensor.primary": { state: "100", attributes: { friendly_name: "Primary", next_reset_at: "2026-10-12T13:07:00Z", min: 80, max: 100 } },
      "sensor.weekly": { state: "76", attributes: { friendly_name: "Weekly", next_reset_at: "2026-10-15T11:05:00Z" } },
    },
    themes: { darkMode: true, themes: {
      Frosted: { "ha-card-background": "rgba(20,24,30,.6)", "ha-card-border-radius": "18px", modes: {
        dark: { "primary-text-color": "#fff" }, light: { "primary-text-color": "#111" },
      } }, Other: { "primary-text-color": "#abc" },
    } },
  };
  card.hass = hass;
  return { card, hass, timers, Card, setNow: (value) => { now = value; } };
}

const html = (card) => card._root.querySelector("ha-card")?.querySelector(".content")?.innerHTML ?? card._root.innerHTML;

test("primary and weekly rows show countdowns instead of pool min/max", () => {
  const { card } = setup();
  assert.match(html(card), /Next reset in 4h 07m/);
  assert.match(html(card), /Next reset in 3d 02h 05m/);
  assert.doesNotMatch(html(card), /min 80%/);
});

test("account reset, sub-minute, due, missing and unavailable states stay honest", () => {
  const { card, hass } = setup();
  const attrs = hass.states["sensor.primary"].attributes;
  delete attrs.next_reset_at;
  attrs.resets_at = "2026-10-12T09:00:01Z";
  card.hass = hass;
  assert.match(html(card), /Resets in 0h 01m/);
  attrs.resets_at = "2026-10-12T09:00:00Z";
  card.hass = hass;
  assert.match(html(card), /Reset due/);
  for (const invalid of [undefined, null, "", "invalid"]) {
    attrs.resets_at = invalid;
    card.hass = hass;
    assert.match(html(card), /Reset time unavailable/);
  }
  hass.states["sensor.primary"].state = "unavailable";
  attrs.resets_at = "2099-01-01T00:00:00Z";
  card.hass = hass;
  assert.match(html(card), /Unavailable/);
  assert.doesNotMatch(html(card), /aria-valuenow=""/);
  assert.doesNotMatch(html(card), /Resets in/);
});

test("absolute display uses HA timezone and offers a hidden mode", () => {
  const { card } = setup({ reset_display: "absolute" });
  assert.match(html(card), /Next reset at/);
  assert.match(html(card), /00:07/); // 13:07 UTC is midnight next day in Sydney (UTC+11).
  assert.doesNotMatch(html(card), /Next reset in/);
  card.setConfig({ entity: "sensor.primary", reset_display: "hidden" });
  assert.doesNotMatch(html(card), /Next reset|Reset time/);
});

test("absolute time respects local timezone and 12-hour preference", () => {
  const { card, hass } = setup({ reset_display: "absolute" });
  hass.locale.time_zone = "local";
  card.hass = hass;
  assert.match(html(card), /13:07/);
  hass.locale.time_format = "12";
  card.hass = hass;
  assert.match(html(card), /1:07 PM/);
});

test("theme selection follows dark mode and clears obsolete variables", () => {
  const { card, hass } = setup({ theme: "Frosted" });
  assert.equal(card.style.values["--ha-card-background"], "rgba(20,24,30,.6)");
  assert.equal(card.style.values["--primary-text-color"], "#fff");
  hass.themes.darkMode = false;
  card.hass = hass;
  assert.equal(card.style.values["--primary-text-color"], "#111");
  card.setConfig({ entity: "sensor.primary", theme: "Other" });
  assert.equal(card.style.values["--ha-card-background"], undefined);
  assert.equal(card.style.values["--primary-text-color"], "#abc");
  card.setConfig({ entity: "sensor.primary" });
  assert.equal(card.style.values["--primary-text-color"], undefined);
});

test("quota updates preserve the ha-card container for card_mod", () => {
  const { card, hass } = setup();
  const container = card._root.querySelector("ha-card");
  container.style.setProperty("background", "glass");
  hass.states["sensor.primary"].state = "25";
  card.hass = hass;
  assert.equal(card._root.querySelector("ha-card"), container);
  assert.equal(container.style.values.background, "glass");
  assert.match(html(card), /25%/);
});

test("quota updates restore the focused button and describe reset timing", () => {
  const { card, hass } = setup();
  let focused = false;
  const button = { dataset: { entity: "sensor.weekly" }, focus() { focused = true; }, addEventListener() {} };
  card._root.activeElement = { dataset: { entity: "sensor.weekly" } };
  card._content.querySelectorAll = () => [button];
  card.hass = hass;
  assert.equal(focused, true);
  assert.match(html(card), /aria-describedby="reset-0"/);
  assert.match(html(card), /aria-describedby="reset-1"/);
  assert.match(html(card), /id="reset-1"[^>]*>Next reset in 3d 02h 05m/);
});

test("countdown timer is started once and released on disconnect or mode change", () => {
  const { card, timers } = setup();
  card.connectedCallback();
  card.connectedCallback();
  assert.equal(timers.size, 1);
  assert.equal(timers.values().next().value.delay, 60000);
  card.disconnectedCallback();
  assert.equal(timers.size, 0);
  card.connectedCallback();
  card.setConfig({ entity: "sensor.primary", reset_display: "absolute" });
  assert.equal(timers.size, 0);
});

test("timer refreshes displayed countdown without replacing the card contents", () => {
  const { card, timers, setNow } = setup();
  const element = { dataset: { entity: "sensor.primary" }, textContent: "old" };
  card._content.querySelectorAll = () => [element];
  const originalHtml = html(card);
  setNow(NOW + 60000);
  timers.values().next().value.fn();
  assert.equal(element.textContent, "Next reset in 4h 06m");
  assert.equal(html(card), originalHtml);
});

test("non-finite quotas are unavailable and sensor labels are escaped", () => {
  const { card, hass } = setup();
  for (const value of ["Infinity", "-Infinity", Infinity, NaN]) {
    hass.states["sensor.primary"].state = value;
    card.hass = hass;
    assert.match(html(card), /Unavailable/);
    assert.doesNotMatch(html(card), /aria-valuenow=/);
  }
  hass.states["sensor.primary"].attributes.friendly_name = '<img src=x onerror="boom">';
  card.hass = hass;
  assert.doesNotMatch(html(card), /<img/);
  assert.match(html(card), /&lt;img/);
});

test("editor exposes native theme picker and reset display choices", () => {
  const { Card } = setup();
  const form = Card.getConfigForm();
  assert.ok(form.schema.find((field) => field.name === "theme").selector.theme);
  assert.deepEqual(Array.from(form.schema.find((field) => field.name === "reset_display").selector.select.options, (item) => item.value),
    ["countdown", "absolute", "hidden"]);
});

test("editor theme dropdown lists installed themes and can clear", () => {
  const { hass, Card } = setup();
  const editor = Card.getConfigElement();
  editor.setConfig({ entity: "sensor.primary", theme: "Frosted" });
  editor.hass = hass;
  const labels = () => Array.from(
    editor._form.schema.find((field) => field.name === "theme").selector.select.options,
    (item) => item.label
  );
  assert.deepEqual(labels(), ["Frosted", "Other"]);
  hass.themes.themes = { ...hass.themes.themes, Graphite: { "primary-text-color": "#888" } };
  editor.hass = hass;
  assert.deepEqual(labels(), ["Frosted", "Graphite", "Other"]);
  editor._form.dispatchEvent({
    type: "value-changed",
    detail: { value: { entity: "sensor.primary", theme: "" } },
    stopPropagation() {},
  });
  assert.equal(editor.event.detail.config.theme, undefined);
  assert.equal(editor.event.detail.config.entity, "sensor.primary");
});

test("editor sets entity labels for the primary and extra rows", () => {
  const { hass, Card } = setup();
  const editor = Card.getConfigElement();
  editor.hass = hass;
  editor.setConfig({ entity: "sensor.primary", entities: ["sensor.weekly"] });
  const plain = (value) => JSON.parse(JSON.stringify(value));
  assert.deepEqual(plain(editor._rows), [
    { entity: "sensor.primary", name: "" },
    { entity: "sensor.weekly", name: "" },
  ]);
  assert.deepEqual(Array.from(editor._entitySelects[0].children, (option) => option.value), ["", "sensor.primary"]);
  editor._entitySelects[0].dispatchEvent({ type: "focus", stopPropagation() {} });
  assert.deepEqual(Array.from(editor._entitySelects[0].children, (option) => option.value), ["", "sensor.primary", "sensor.weekly"]);
  editor._entitySelects[0].dispatchEvent({ type: "blur", stopPropagation() {} });
  assert.deepEqual(Array.from(editor._entitySelects[0].children, (option) => option.value), ["", "sensor.primary"]);
  assert.equal(editor._nameInputs[0].placeholder, "Primary");
  const label = editor._nameInputs[0];
  label.value = "5";
  label.dispatchEvent({ type: "input", stopPropagation() {} });
  editor.setConfig(editor.event.detail.config);
  assert.equal(editor._nameInputs[0], label);
  label.value = "5h pool";
  editor._nameInputs[0].dispatchEvent({ type: "input", stopPropagation() {} });
  assert.equal(editor.event.detail.config.name, "5h pool");
  assert.equal(editor.event.detail.config.entity, "sensor.primary");
  editor._nameInputs[1].value = "Weekly pool";
  editor._nameInputs[1].dispatchEvent({ type: "input", stopPropagation() {} });
  assert.deepEqual(plain(editor.event.detail.config.entities), [{ entity: "sensor.weekly", name: "Weekly pool" }]);
  editor._nameInputs[1].value = "  ";
  editor._nameInputs[1].dispatchEvent({ type: "input", stopPropagation() {} });
  assert.deepEqual(plain(editor.event.detail.config.entities), ["sensor.weekly"]);
  editor.setConfig({
    entity: "sensor.primary",
    name: "5h pool",
    entities: [{ entity: "sensor.weekly", name: "Weekly pool" }],
  });
  assert.equal(editor._nameInputs[0].value, "5h pool");
  assert.equal(editor._nameInputs[1].value, "Weekly pool");
  editor._addButton.dispatchEvent({ type: "click", stopPropagation() {} });
  assert.equal(editor._rows.length, 3);
  editor._removeButtons[0].dispatchEvent({ type: "click", stopPropagation() {} });
  assert.equal(editor.event.detail.config.entities, undefined);
  assert.equal(editor.event.detail.config.name, "5h pool");
});

test("clearing the only entity saves and survives the editor echo", () => {
  const { hass, Card } = setup();
  const editor = Card.getConfigElement();
  editor.hass = hass;
  editor.setConfig({ entity: "sensor.primary", name: "5h pool" });
  const select = editor._entitySelects[0];
  const label = editor._nameInputs[0];
  select.value = "";
  select.dispatchEvent({ type: "change", stopPropagation() {} });
  assert.equal(editor.event.detail.config.entity, undefined);
  assert.equal(editor.event.detail.config.name, "5h pool");
  editor.setConfig(editor.event.detail.config);
  assert.equal(editor._entitySelects[0], select);
  assert.equal(select.value, "");
  assert.equal(editor._nameInputs[0], label);
  assert.equal(label.value, "5h pool");
  label.value = "5h pool renamed";
  label.dispatchEvent({ type: "input", stopPropagation() {} });
  assert.equal(editor.event.detail.config.entity, undefined);
  assert.equal(editor.event.detail.config.name, "5h pool renamed");
  editor.setConfig(editor.event.detail.config);
  assert.equal(editor._nameInputs[0], label);
  assert.equal(label.value, "5h pool renamed");
});

test("clearing the primary entity keeps its label when another row remains", () => {
  const { hass, Card } = setup();
  const editor = Card.getConfigElement();
  editor.hass = hass;
  editor.setConfig({
    entity: "sensor.primary",
    name: "Pool",
    entities: [{ entity: "sensor.weekly", name: "Weekly" }],
  });
  const select = editor._entitySelects[0];
  select.value = "";
  select.dispatchEvent({ type: "change", stopPropagation() {} });
  const plain = (value) => JSON.parse(JSON.stringify(value));
  assert.equal(editor.event.detail.config.entity, undefined);
  assert.equal(editor.event.detail.config.name, "Pool");
  assert.deepEqual(plain(editor.event.detail.config.entities), [{ entity: "sensor.weekly", name: "Weekly" }]);
  editor.setConfig(editor.event.detail.config);
  assert.equal(editor._entitySelects[0], select);
  assert.equal(select.value, "");
  assert.deepEqual(plain(editor._rows), [
    { entity: "", name: "Pool" },
    { entity: "sensor.weekly", name: "Weekly" },
  ]);
});

test("clearing a nameless primary promotes the next row once", () => {
  const { hass, Card } = setup();
  const editor = Card.getConfigElement();
  editor.hass = hass;
  editor.setConfig({ entity: "sensor.primary", entities: ["sensor.weekly"] });
  const select = editor._entitySelects[0];
  select.value = "";
  select.dispatchEvent({ type: "change", stopPropagation() {} });
  assert.equal(editor.event.detail.config.entity, "sensor.weekly");
  assert.equal(editor.event.detail.config.entities, undefined);
  const promoted = editor._entitySelects[0];
  assert.equal(promoted.value, "sensor.weekly");
  editor.setConfig(editor.event.detail.config);
  assert.equal(editor._entitySelects[0], promoted);
});

test("a label on an extra row waits for an entity before it is saved", () => {
  const { hass, Card } = setup();
  const editor = Card.getConfigElement();
  editor.hass = hass;
  editor.setConfig({ entity: "sensor.primary" });
  editor._addButton.dispatchEvent({ type: "click", stopPropagation() {} });
  const label = editor._nameInputs[1];
  label.value = "later";
  label.dispatchEvent({ type: "input", stopPropagation() {} });
  assert.equal(editor._nameInputs[1], label);
  assert.equal(label.value, "later");
  assert.equal(editor._config.entities, undefined);
  editor._entitySelects[1].value = "sensor.weekly";
  editor._entitySelects[1].dispatchEvent({ type: "change", stopPropagation() {} });
  assert.deepEqual(JSON.parse(JSON.stringify(editor.event.detail.config.entities)), [{ entity: "sensor.weekly", name: "later" }]);
});

test("row labels replace entity names on the card", () => {
  const { card } = setup({
    name: "5h pool",
    entities: [{ entity: "sensor.weekly", name: "Weekly pool" }],
  });
  const text = html(card);
  assert.match(text, /5h pool/);
  assert.match(text, /Weekly pool/);
  assert.doesNotMatch(text, />Primary</);
});

test("reject unsupported reset modes", () => {
  const { card } = setup();
  assert.throws(() => card.setConfig({ entity: "sensor.primary", reset_display: "nonsense" }), /reset_display/);
});
