/**
 * Codex-LB Rates Lovelace card — pool + remaining %.
 *
 * Consumes existing remaining-% sensors (pool or account). No new entities.
 *
 * Example:
 *   type: custom:codex-rates-card
 *   title: Codex pool
 *   entity: sensor.codex_lb_pool_all_accounts_5h_remaining
 *   entities:
 *     - sensor.codex_lb_pool_all_accounts_weekly_remaining
 *     - entity: sensor.my_account_5h_remaining
 *       name: Account A
 */
(() => {
  const CARD_TYPE = "codex-rates-card";
  const EDITOR_TYPE = "codex-rates-card-editor";
  // Bump when editor/card surface changes so console + digest cache-bust clearly.
  const CARD_VERSION = "1.2.0";

  /** @param {number} value */
  function clampPercent(value) {
    if (!Number.isFinite(value)) return null;
    return Math.max(0, Math.min(100, value));
  }

  /** @param {unknown} state */
  function parseRemaining(state) {
    if (state === undefined || state === null) return null;
    if (typeof state === "number") return clampPercent(state);
    const text = String(state).trim();
    if (!text || text === "unknown" || text === "unavailable") return null;
    const parsed = Number.parseFloat(text);
    return clampPercent(parsed);
  }

  /**
   * Remaining-% colour bands (plenty / getting low / little left).
   * @param {number | null} value
   * @param {{ green?: number, yellow?: number }} thresholds
   */
  function bandColor(value, thresholds) {
    if (value === null) return "var(--disabled-text-color)";
    const green = thresholds.green ?? 50;
    const yellow = thresholds.yellow ?? 20;
    if (value >= green) return "var(--success-color, #48c9b0)";
    if (value >= yellow) return "var(--warning-color, #f0c14b)";
    return "var(--error-color, #e4572e)";
  }

  /**
   * @param {Record<string, unknown>} config
   * @returns {{ entity: string, name?: string }[]}
   */
  function normalizeEntities(config) {
    /** @type {{ entity: string, name?: string }[]} */
    const rows = [];
    if (config.entity) {
      rows.push({ entity: String(config.entity), name: config.name ? String(config.name) : undefined });
    }
    const list = Array.isArray(config.entities) ? config.entities : [];
    for (const item of list) {
      if (typeof item === "string") {
        rows.push({ entity: item });
        continue;
      }
      if (item && typeof item === "object" && item.entity) {
        rows.push({
          entity: String(item.entity),
          name: item.name ? String(item.name) : undefined,
        });
      }
    }
    return rows;
  }

  /** @param {unknown} value */
  function formatOptionalNumber(value) {
    if (value === undefined || value === null || value === "") return null;
    const num = typeof value === "number" ? value : Number.parseFloat(String(value));
    if (Number.isNaN(num)) return String(value);
    return Number.isInteger(num) ? String(num) : num.toFixed(1);
  }

  /** Format provider timestamps; never infer a reset from the quota percentage. */
  function formatReset(stateObj, mode, hass) {
    if (parseRemaining(stateObj?.state) === null) return "Unavailable";
    const attrs = stateObj.attributes || {};
    const pool = attrs.next_reset_at !== undefined || attrs.reset_sample_count !== undefined;
    const timestamp = pool ? attrs.next_reset_at : attrs.resets_at;
    const reset = typeof timestamp === "string" && timestamp.trim() ? Date.parse(timestamp) : NaN;
    if (!Number.isFinite(reset)) return "Reset time unavailable";
    if (reset <= Date.now()) return pool ? "Next reset due · awaiting update" : "Reset due · awaiting update";
    const prefix = pool ? "Next reset" : "Resets";
    if (mode === "absolute") {
      const locale = hass?.locale;
      const options = {
        weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit",
        timeZone: locale?.time_zone === "local" ? undefined : hass?.config?.time_zone,
      };
      if (locale?.time_format === "24") options.hourCycle = "h23";
      if (locale?.time_format === "12") options.hourCycle = "h12";
      if (locale?.time_format === "system") {
        options.hourCycle = new Intl.DateTimeFormat(undefined, { hour: "numeric" }).resolvedOptions().hourCycle;
      }
      return `${prefix} at ${new Intl.DateTimeFormat(locale?.language || undefined, options).format(reset)}`;
    }
    const minutes = Math.ceil((reset - Date.now()) / 60000);
    const days = Math.floor(minutes / 1440);
    const hours = Math.floor((minutes % 1440) / 60);
    const mins = String(minutes % 60).padStart(2, "0");
    const duration = days ? `${days}d ${String(hours).padStart(2, "0")}h ${mins}m` : `${hours}h ${mins}m`;
    return `${pool ? "Next reset" : "Resets"} in ${duration}`;
  }

  /**
   * Object-form `entities` rows stay YAML-only — the multi entity selector
   * expects string[]. Throwing disables the visual editor for that config.
   * @param {Record<string, unknown> | null | undefined} config
   */
  function assertConfig(config) {
    const list = Array.isArray(config?.entities) ? config.entities : [];
    for (const item of list) {
      if (typeof item !== "string") {
        throw new Error(
          "Object-form entities (including per-row names) are only editable in YAML; use the code editor."
        );
      }
    }
  }

  /** @param {{ name?: string }} schema */
  function computeLabel(schema) {
    switch (schema.name) {
      case "title":
        return "Title";
      case "theme":
        return "Theme";
      case "reset_display":
        return "Reset display";
      case "entity":
        return "Primary remaining entity";
      case "name":
        return "Primary name override";
      case "entities":
        return "Additional remaining entities";
      case "green":
        return "Green threshold (%)";
      case "yellow":
        return "Yellow threshold (%)";
      default:
        return undefined;
    }
  }

  /** @param {{ name?: string }} schema */
  function computeHelper(schema) {
    switch (schema.name) {
      case "entity":
        return "Large remaining-% value and progress bar. At least one of primary or additional entities is required.";
      case "theme":
        return "Optional card theme. Leave empty to use the dashboard theme.";
      case "reset_display":
        return "Countdown (default), reset date/time in Home Assistant's time zone, or hidden. Pools show the next known account reset.";
      case "name":
        return "Optional label for the primary entity only.";
      case "entities":
        return "Extra rows under the primary (entity IDs only). Object-form rows with optional names still need YAML.";
      case "green":
      case "yellow":
        return "Colour bands: ≥ green = plenty; ≥ yellow = getting low; else little left. Defaults 50 / 20.";
      default:
        return undefined;
    }
  }

  const CONFIG_FORM_SCHEMA = [
    { name: "title", selector: { text: {} } },
    { name: "theme", selector: { theme: {} } },
    {
      name: "reset_display",
      selector: { select: { mode: "dropdown", options: [
        { value: "countdown", label: "Countdown" },
        { value: "absolute", label: "Reset date/time" },
        { value: "hidden", label: "Hidden" },
      ] } },
    },
    {
      name: "entity",
      selector: {
        entity: {
          domain: "sensor",
        },
      },
    },
    { name: "name", selector: { text: {} } },
    {
      name: "entities",
      selector: {
        entity: {
          multiple: true,
          domain: "sensor",
        },
      },
    },
    {
      type: "grid",
      name: "",
      flatten: true,
      schema: [
        {
          name: "green",
          selector: { number: { min: 0, max: 100, mode: "box" } },
        },
        {
          name: "yellow",
          selector: { number: { min: 0, max: 100, mode: "box" } },
        },
      ],
    },
  ];

  function getConfigForm() {
    return {
      schema: CONFIG_FORM_SCHEMA,
      computeLabel,
      computeHelper,
      assertConfig,
    };
  }

  /** @param {any} hass */
  function installedThemes(hass) {
    return Object.keys(hass?.themes?.themes || {}).sort((a, b) =>
      a.localeCompare(b, undefined, { sensitivity: "base" })
    );
  }

  // ha-theme-picker snapshots uiContext once and stays empty in this editor.
  // List hass.themes instead — that is the catalog the card applies.
  /** @param {any} hass */
  function editorSchema(hass) {
    const names = installedThemes(hass);
    return {
      key: names.join("\0"),
      schema: CONFIG_FORM_SCHEMA.filter((field) => !["entity", "name", "entities"].includes(field.name)).map((field) =>
        field.name !== "theme"
          ? field
          : {
              name: "theme",
              selector: {
                select: {
                  mode: "dropdown",
                  options: names.map((name) => ({ value: name, label: name })),
                },
              },
            }
      ),
    };
  }

  /** @param {any} hass @param {string} id */
  function selectedChoice(hass, id) {
    if (!id) return [];
    return [{ value: id, label: hass?.states?.[id]?.attributes?.friendly_name || id }];
  }

  // ponytail: cap search hits; raise the cap if 40 matching sensors is too few to find one.
  const SENSOR_SEARCH_CAP = 40;

  /** @param {any} hass @param {string} query */
  function searchChoices(hass, query) {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    /** @type {{ value: string, label: string }[]} */
    const matches = [];
    for (const id of Object.keys(hass?.states || {})) {
      if (!id.startsWith("sensor.")) continue;
      const label = hass.states[id]?.attributes?.friendly_name || id;
      if (!id.toLowerCase().includes(q) && !String(label).toLowerCase().includes(q)) continue;
      matches.push({ value: id, label });
    }
    matches.sort((a, b) => a.label.localeCompare(b.label, undefined, { sensitivity: "base" }));
    return matches.slice(0, SENSOR_SEARCH_CAP);
  }

  /** @param {HTMLSelectElement} select @param {{ value: string, label: string }[]} choices */
  function fillEntitySelect(select, choices) {
    select.replaceChildren();
    const blank = document.createElement("option");
    blank.value = "";
    blank.textContent = "Select entity";
    select.appendChild(blank);
    for (const choice of choices) {
      const option = document.createElement("option");
      option.value = choice.value;
      option.textContent = choice.label;
      select.appendChild(option);
    }
  }

  /** @param {Record<string, unknown> | null | undefined} config */
  function rowsFromConfig(config) {
    /** @type {{ entity: string, name: string }[]} */
    const rows = [];
    const entities = /** @type {unknown[]} */ (Array.isArray(config?.entities) ? config.entities : []);
    if (config?.entity) rows.push({ entity: String(config.entity), name: config.name ? String(config.name) : "" });
    else if (config?.name && entities.length) rows.push({ entity: "", name: String(config.name) });
    for (const item of entities) {
      if (typeof item === "string") rows.push({ entity: item, name: "" });
      else if (item && typeof item === "object" && "entity" in item && item.entity) {
        rows.push({ entity: String(item.entity), name: "name" in item && item.name ? String(item.name) : "" });
      }
    }
    if (!rows.length) rows.push({ entity: "", name: config?.name ? String(config.name) : "" });
    return rows;
  }

  /** @param {{ entity: string, name: string }} row */
  function storedRow(row) {
    if (!row.entity) return null;
    return row.name.trim() ? { entity: row.entity, name: row.name } : row.entity;
  }

  /**
   * @param {Record<string, unknown>} config
   * @param {{ entity: string, name: string }[]} rows
   */
  function applyRows(config, rows) {
    const list = rows.length ? rows : [{ entity: "", name: "" }];
    let [head, ...rest] = list;
    const next = { ...config };
    if (!head.entity && !head.name.trim()) {
      const promoted = rest.find((row) => row.entity);
      if (promoted) {
        rest = rest.filter((row) => row !== promoted);
        head = promoted;
      }
    }
    if (head.entity) next.entity = head.entity;
    else delete next.entity;
    if (head.name.trim()) next.name = head.name;
    else delete next.name;
    const extras = rest.map(storedRow).filter(Boolean);
    if (extras.length) next.entities = extras;
    else delete next.entities;
    return next;
  }

  /** Indexes of rows applyRows will keep, in persisted order. */
  function survivedIndexes(current) {
    const list = current.length ? current : [{ entity: "", name: "" }];
    const [head, ...rest] = list;
    if (!head.entity && !head.name.trim()) {
      const promotedAt = rest.findIndex((row) => row.entity);
      if (promotedAt >= 0) {
        const indexes = [promotedAt + 1];
        rest.forEach((row, index) => {
          if (index !== promotedAt && row.entity) indexes.push(index + 1);
        });
        return indexes;
      }
    }
    const indexes = [0];
    rest.forEach((row, index) => {
      if (row.entity) indexes.push(index + 1);
    });
    return indexes;
  }

  /** Keep extra rows that have no sensor yet, in their place among the rows that were saved. */
  function withDrafts(persisted, current) {
    if (!current.length) return persisted.map((row) => ({ entity: row.entity, name: row.name }));
    const survived = new Set(survivedIndexes(current));
    const rows = [];
    let next = 0;
    current.forEach((row, index) => {
      if (survived.has(index)) {
        const kept = persisted[next++];
        rows.push({ entity: kept.entity, name: kept.name });
        return;
      }
      if (index > 0 && !row.entity) rows.push({ entity: "", name: row.name });
    });
    return rows.length ? rows : persisted.map((row) => ({ entity: row.entity, name: row.name }));
  }

  /** @param {Record<string, unknown>} config @param {{ entity: string, name: string }[]} current */
  function settleRows(config, current) {
    let rows = current.length ? current : [{ entity: "", name: "" }];
    let saved = applyRows(config, rows);
    if (config.type) saved.type = config.type;
    for (let pass = 0; pass < 3; pass++) {
      const persisted = rowsFromConfig(saved);
      const next = withDrafts(persisted, rows);
      if (JSON.stringify(next) === JSON.stringify(rows)) return { config: saved, rows, persisted };
      rows = next;
      saved = applyRows(config, rows);
      if (config.type) saved.type = config.type;
    }
    return { config: saved, rows, persisted: rowsFromConfig(saved) };
  }

  /**
   * Compact visual editor — HA prefers getConfigElement over getConfigForm.
   * Uses frontend ha-form (always present in the card editor dialog).
   */
  class CodexRatesCardEditor extends HTMLElement {
    constructor() {
      super();
      /** @type {Record<string, unknown>} */
      this._config = {};
      /** @type {any} */
      this._hass = undefined;
      /** @type {any} */
      this._form = undefined;
      this._formBottom = undefined;
      this._rowsHost = undefined;
      /** @type {{ entity: string, name: string }[]} */
      this._rows = [];
      /** @type {HTMLSelectElement[]} */
      this._entitySelects = [];
      /** @type {HTMLInputElement[]} */
      this._nameInputs = [];
      /** @type {HTMLButtonElement[]} */
      this._removeButtons = [];
      /** @type {HTMLButtonElement | undefined} */
      this._addButton = undefined;
      this._themeKey = "";
      this._rowsKey = "";
      /** @type {Set<string>} */
      this._sensorSet = new Set();
      this._sensorCount = -1;
    }

    /** @param {Record<string, unknown>} config */
    setConfig(config) {
      this._config = { ...config };
      this._ensureForm();
      const rows = rowsFromConfig(config);
      const key = JSON.stringify(rows);
      // The dashboard echoes config-changed back through setConfig. Rebuilding
      // here would destroy the focused label after every keystroke.
      if (key !== this._rowsKey) {
        this._rowsKey = key;
        this._rows = rows;
        this._renderRows();
      }
      this._setFormData();
    }

    /** @param {any} hass */
    set hass(hass) {
      this._hass = hass;
      if (this._form) {
        this._form.hass = hass;
        this._formBottom.hass = hass;
        this._syncSchema();
      }
      const ids = Object.keys(hass?.states || {}).filter((id) => id.startsWith("sensor."));
      const changed = ids.length !== this._sensorCount || ids.some((id) => !this._sensorSet.has(id));
      if (!changed || this._rowFocused()) return;
      this._sensorSet = new Set(ids);
      this._sensorCount = ids.length;
      this._renderRows();
    }

    _rowFocused() {
      const active = typeof document !== "undefined" ? document.activeElement : null;
      return !!(active && this._rowsHost?.contains?.(active));
    }

    _syncRowsKey() {
      this._rowsKey = JSON.stringify(rowsFromConfig(applyRows(this._config, this._rows)));
    }

    _setFormData() {
      if (this._form) this._form.data = this._config;
      if (this._formBottom) this._formBottom.data = this._config;
    }

    _syncSchema() {
      const next = editorSchema(this._hass);
      if (next.key === this._themeKey) return;
      this._themeKey = next.key;
      this._form.schema = next.schema.filter((field) => ["title", "theme", "reset_display"].includes(field.name));
    }

    connectedCallback() {
      this._ensureForm();
      this._renderRows();
    }

    /** @param {HTMLElement} form */
    _bindForm(form) {
      form.computeLabel = computeLabel;
      form.computeHelper = computeHelper;
      form.data = this._config;
      if (this._hass) form.hass = this._hass;
      form.addEventListener("value-changed", (ev) => {
        ev.stopPropagation();
        const value = ev.detail?.value || {};
        const config = { ...this._config, ...value };
        if (this._config.type) config.type = this._config.type;
        if (!value.theme) delete config.theme;
        this._config = config;
        this._setFormData();
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config }, bubbles: true, composed: true }));
      });
    }

    _ensureForm() {
      if (this._form || !this.isConnected) return;
      const next = editorSchema(this._hass);
      this._themeKey = next.key;
      const top = /** @type {any} */ (document.createElement("ha-form"));
      top.schema = next.schema.filter((field) => ["title", "theme", "reset_display"].includes(field.name));
      this._bindForm(top);
      this._rowsHost = document.createElement("div");
      const bottom = /** @type {any} */ (document.createElement("ha-form"));
      bottom.schema = next.schema.filter((field) => !["title", "theme", "reset_display"].includes(field.name));
      this._bindForm(bottom);
      this._form = top;
      this._formBottom = bottom;
      this.append(top, this._rowsHost, bottom);
    }

    _emitRows() {
      const settled = settleRows(this._config, this._rows);
      this._config = settled.config;
      if (JSON.stringify(settled.rows) !== JSON.stringify(this._rows)) {
        const active = typeof document !== "undefined" ? document.activeElement : null;
        const index = this._entitySelects.indexOf(active);
        this._rows = settled.rows;
        this._renderRows();
        if (index >= 0) this._entitySelects[Math.min(index, this._entitySelects.length - 1)]?.focus?.();
      } else {
        this._rowsKey = JSON.stringify(settled.persisted);
      }
      this._setFormData();
      this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: settled.config }, bubbles: true, composed: true }));
    }

    _renderRows() {
      if (!this._rowsHost || !this._rows) return;
      this._rowsHost.replaceChildren();
      this._entitySelects = [];
      this._entitySearches = [];
      this._nameInputs = [];
      this._removeButtons = [];
      this._rows.forEach((row, index) => {
        const block = document.createElement("div");
        block.style.margin = "12px 0";
        const select = /** @type {HTMLSelectElement} */ (document.createElement("select"));
        const search = /** @type {HTMLInputElement} */ (document.createElement("input"));
        search.placeholder = "Search sensors";
        const showMatches = () => {
          const selected = this._rows[index].entity;
          const matches = searchChoices(this._hass, search.value).filter((choice) => choice.value !== selected);
          fillEntitySelect(select, [...selectedChoice(this._hass, selected), ...matches]);
          select.value = selected;
        };
        fillEntitySelect(select, selectedChoice(this._hass, row.entity));
        select.value = row.entity;
        search.addEventListener("input", (ev) => {
          ev.stopPropagation();
          showMatches();
        });
        select.addEventListener("blur", () => {
          const current = this._rows[index].entity;
          fillEntitySelect(select, selectedChoice(this._hass, current));
          select.value = current;
        });
        select.addEventListener("change", (ev) => {
          ev.stopPropagation();
          this._rows[index].entity = select.value;
          search.value = "";
          fillEntitySelect(select, selectedChoice(this._hass, select.value));
          select.value = this._rows[index].entity;
          this._syncRowsKey();
          this._emitRows();
        });
        const input = /** @type {HTMLInputElement} */ (document.createElement("input"));
        input.value = row.name;
        input.placeholder = this._hass?.states?.[row.entity]?.attributes?.friendly_name || "Entity name";
        input.addEventListener("input", (ev) => {
          ev.stopPropagation();
          this._rows[index].name = input.value;
          this._syncRowsKey();
          if (index === 0 || this._rows[index].entity) this._emitRows();
        });
        input.addEventListener("change", (ev) => {
          ev.stopPropagation();
          input.value = input.value.trim();
          this._rows[index].name = input.value;
          this._syncRowsKey();
          if (index === 0 || this._rows[index].entity) this._emitRows();
        });
        block.append(
          this._field("Search sensors", search),
          this._field(index === 0 ? "Primary entity" : "Additional entity", select),
          this._field("Label", input),
        );
        if (index > 0) {
          const remove = /** @type {HTMLButtonElement} */ (document.createElement("button"));
          remove.type = "button";
          remove.textContent = "Remove";
          remove.addEventListener("click", (ev) => {
            ev.stopPropagation();
            this._rows.splice(index, 1);
            this._renderRows();
            this._emitRows();
          });
          block.appendChild(remove);
          this._removeButtons.push(remove);
        }
        this._entitySelects.push(select);
        this._entitySearches.push(search);
        this._nameInputs.push(input);
        this._rowsHost.appendChild(block);
      });
      const add = /** @type {HTMLButtonElement} */ (document.createElement("button"));
      add.type = "button";
      add.textContent = "Add entity";
      add.addEventListener("click", (ev) => {
        ev.stopPropagation();
        this._rows.push({ entity: "", name: "" });
        this._renderRows();
      });
      this._addButton = add;
      this._rowsHost.appendChild(add);
      this._syncRowsKey();
    }

    /** @param {string} caption @param {HTMLElement} control */
    _field(caption, control) {
      const label = document.createElement("label");
      label.style.display = "flex";
      label.style.flexDirection = "column";
      label.style.gap = "4px";
      label.style.marginBottom = "8px";
      label.append(caption, control);
      control.style.width = "100%";
      control.style.boxSizing = "border-box";
      return label;
    }
  }

  class CodexRatesCard extends HTMLElement {
    constructor() {
      super();
      /** @type {Record<string, unknown> | null} */
      this._config = null;
      /** @type {any} */
      this._hass = null;
      this._root = this.attachShadow({ mode: "open" });
      this._style = this._root.appendChild(document.createElement("style"));
      this._card = this._root.appendChild(document.createElement("ha-card"));
      this._content = this._card.appendChild(document.createElement("div"));
      this._content.className = "content";
      this._themeKeys = [];
      this._timer = undefined;
    }

    static getStubConfig() {
      return {
        type: `custom:${CARD_TYPE}`,
        title: "Codex remaining",
        entity: "sensor.codex_lb_pool_all_accounts_5h_remaining",
        entities: ["sensor.codex_lb_pool_all_accounts_weekly_remaining"],
      };
    }

    /** Built-in ha-form schema (HA ≈2023.5+ fallback if getConfigElement is ignored). */
    static getConfigForm() {
      return getConfigForm();
    }

    /** Preferred Lovelace visual editor hook. */
    static getConfigElement() {
      return document.createElement(EDITOR_TYPE);
    }

    /** @param {Record<string, unknown>} config */
    setConfig(config) {
      if (!config || typeof config !== "object") {
        throw new Error("Invalid configuration");
      }
      const entities = normalizeEntities(config);
      if (!entities.length) {
        throw new Error("Set at least one remaining-% entity");
      }
      if (config.reset_display && !["countdown", "absolute", "hidden"].includes(config.reset_display)) {
        throw new Error("reset_display must be countdown, absolute, or hidden");
      }
      this._config = { ...config, _entities: entities };
      this._applyTheme();
      this._syncTimer();
      this._render();
    }

    /** @param {any} hass */
    set hass(hass) {
      this._hass = hass;
      this._applyTheme();
      this._render();
    }

    connectedCallback() {
      this._syncTimer();
      this._updateResetTimes();
    }

    disconnectedCallback() {
      clearInterval(this._timer);
      this._timer = undefined;
    }

    _syncTimer() {
      this.disconnectedCallback();
      if (this.isConnected && this._config && (this._config.reset_display || "countdown") === "countdown") {
        this._timer = setInterval(() => this._updateResetTimes(), 60000);
      }
    }

    _updateResetTimes() {
      for (const element of this._content.querySelectorAll(".reset[data-entity]")) {
        element.textContent = formatReset(this._hass?.states?.[element.dataset.entity], this._config?.reset_display, this._hass);
      }
    }

    _applyTheme() {
      const theme = this._hass?.themes?.themes?.[this._config?.theme];
      const { modes, ...base } = theme || {};
      const mode = this._hass?.themes?.darkMode ? "dark" : "light";
      const variables = { ...base, ...modes?.[mode] };
      for (const key of this._themeKeys) this.style.removeProperty(`--${key}`);
      this._themeKeys = Object.keys(variables);
      for (const [key, value] of Object.entries(variables)) this.style.setProperty(`--${key}`, String(value));
    }

    _resetHtml(entity, stateObj, index) {
      if (this._config.reset_display === "hidden") return "";
      return `<span id="reset-${index}" class="reset" data-entity="${this._escape(entity)}">${this._escape(formatReset(stateObj, this._config.reset_display, this._hass))}</span>`;
    }

    getCardSize() {
      const entities = /** @type {{ entity: string }[]} */ (this._config?._entities || []);
      return Math.max(2, 1 + entities.length);
    }

    _render() {
      if (!this._config || !this._root) return;

      const entities = /** @type {{ entity: string, name?: string }[]} */ (
        this._config._entities || []
      );
      const primary = entities[0];
      const rest = entities.slice(1);
      const thresholds = {
        green: Number(this._config.green ?? 50),
        yellow: Number(this._config.yellow ?? 20),
      };
      const title =
        (this._config.title && String(this._config.title)) ||
        primary.name ||
        "Codex remaining";

      const primaryState = this._hass?.states?.[primary.entity];
      const primaryValue = parseRemaining(primaryState?.state);
      const primaryName =
        primary.name ||
        primaryState?.attributes?.friendly_name ||
        primary.entity;
      const color = bandColor(primaryValue, thresholds);
      const barWidth = primaryValue === null ? 0 : primaryValue;

      const attrs = primaryState?.attributes || {};
      const metaParts = [];
      const samples = formatOptionalNumber(attrs.sample_count);
      if (samples !== null) metaParts.push(`${samples} measured`);
      const weighting = attrs.weighting_method ? String(attrs.weighting_method) : null;
      if (weighting) metaParts.push(weighting.replaceAll("_", " "));
      if (Number.isFinite(attrs.reset_sample_count) && Number.isFinite(attrs.sample_count) && attrs.reset_sample_count < attrs.sample_count) {
        metaParts.push(`reset times for ${attrs.reset_sample_count}/${attrs.sample_count} accounts`);
      }

      const rowsHtml = rest
        .map((row, index) => {
          const stateObj = this._hass?.states?.[row.entity];
          const value = parseRemaining(stateObj?.state);
          const label =
            row.name || stateObj?.attributes?.friendly_name || row.entity;
          const rowColor = bandColor(value, thresholds);
          const display = value === null ? "—" : `${value.toFixed(value % 1 ? 1 : 0)}%`;
          const unavailable = value === null;
          return `
            <button type="button" class="row${unavailable ? " muted" : ""}" data-entity="${this._escape(row.entity)}"
                    ${this._config.reset_display === "hidden" ? "" : `aria-describedby="reset-${index + 1}"`}
                    aria-label="${this._escape(label)}: ${display}. More info">
              <span class="row-details"><span class="row-name">${this._escape(label)}</span>${this._resetHtml(row.entity, stateObj, index + 1)}</span>
              <span class="row-value" style="color:${rowColor}">${display}</span>
            </button>
          `;
        })
        .join("");

      const primaryDisplay =
        primaryValue === null
          ? "—"
          : `${primaryValue.toFixed(primaryValue % 1 ? 1 : 0)}%`;

      this._style.textContent = `
          :host {
            display: block;
          }
          ha-card {
            --codex-accent: ${color};
            padding: 16px;
            overflow: hidden;
          }
          button {
            width: 100%;
            background: none;
            border: none;
            padding: 0;
            color: inherit;
            font: inherit;
            text-align: start;
            cursor: pointer;
          }
          button:focus-visible {
            outline: 2px solid var(--primary-color);
            outline-offset: 3px;
          }
          .header {
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 12px;
            margin-bottom: 8px;
          }
          .title {
            font-size: 1.05rem;
            font-weight: 500;
            color: var(--ha-card-header-color, var(--primary-text-color));
            line-height: 1.3;
          }
          .subtitle {
            font-size: 0.8rem;
            color: var(--secondary-text-color);
            margin-top: 2px;
            overflow-wrap: anywhere;
          }
          .hero {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 12px;
            margin: 4px 0 12px;
          }
          .pct {
            font-size: 2.4rem;
            font-weight: 600;
            letter-spacing: -0.02em;
            line-height: 1;
            color: var(--codex-accent);
            font-variant-numeric: tabular-nums;
          }
          .pct-label {
            font-size: 0.75rem;
            color: var(--secondary-text-color);
            text-align: right;
            max-width: 45%;
          }
          .bar {
            height: 8px;
            border-radius: 999px;
            background: color-mix(in srgb, var(--divider-color) 70%, transparent);
            overflow: hidden;
            margin-bottom: 10px;
          }
          .bar > span {
            display: block;
            height: 100%;
            width: ${barWidth}%;
            border-radius: inherit;
            background: var(--codex-accent);
            transition: width 0.35s ease;
          }
          .meta {
            font-size: 0.75rem;
            color: var(--secondary-text-color);
            margin-bottom: ${rowsHtml ? "12px" : "0"};
          }
          .reset {
            display: block;
            font-size: 0.75rem;
            line-height: 1.5;
            color: var(--secondary-text-color);
            font-variant-numeric: tabular-nums;
            overflow-wrap: anywhere;
          }
          .primary-reset { margin-bottom: 8px; }
          .rows {
            display: flex;
            flex-direction: column;
            gap: 8px;
            border-top: 1px solid var(--divider-color);
            padding-top: 10px;
          }
          .row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            gap: 12px;
            font-size: 0.92rem;
          }
          .row.muted .row-value {
            color: var(--disabled-text-color) !important;
          }
          .row-name {
            display: block;
            color: var(--primary-text-color);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
          .row-details { min-width: 0; }
          .row-value {
            font-weight: 600;
            font-variant-numeric: tabular-nums;
            flex-shrink: 0;
          }
          .warning {
            color: var(--error-color);
            font-size: 0.85rem;
            margin-top: 8px;
          }
      `;
      const focusedEntity = this._root.activeElement?.dataset?.entity;
      this._content.innerHTML = `
          <div class="header">
            <div>
              <div class="title">${this._escape(title)}</div>
              <div class="subtitle">${this._escape(primaryName)}</div>
            </div>
          </div>
          <button type="button" class="hero" data-entity="${this._escape(primary.entity)}"
                  ${this._config.reset_display === "hidden" ? "" : 'aria-describedby="reset-0"'}
                  aria-label="${this._escape(primaryName)}: ${primaryDisplay}. More info">
            <div class="pct">${primaryDisplay}</div>
            <div class="pct-label">${primaryValue === null ? "Unavailable" : "remaining"}</div>
          </button>
          <div class="bar" role="progressbar" aria-valuemin="0" aria-valuemax="100"
               ${primaryValue === null ? 'aria-valuetext="Unavailable"' : `aria-valuenow="${primaryValue}"`}
               aria-label="${this._escape(primaryName)} remaining">
            <span></span>
          </div>
          ${this._config.reset_display === "hidden" ? "" : `<div class="primary-reset">${this._resetHtml(primary.entity, primaryState, 0)}</div>`}
          ${
            metaParts.length
              ? `<div class="meta">${this._escape(metaParts.join(" · "))}</div>`
              : ""
          }
          ${rowsHtml ? `<div class="rows">${rowsHtml}</div>` : ""}
          ${
            !this._hass
              ? ""
              : !primaryState
                ? `<div class="warning">Entity not found: ${this._escape(primary.entity)}</div>`
                : ""
          }
      `;
      for (const button of this._content.querySelectorAll("button[data-entity]")) {
        if (focusedEntity && button.dataset.entity === focusedEntity) button.focus({ preventScroll: true });
        button.addEventListener("click", () => {
          this.dispatchEvent(new CustomEvent("hass-more-info", {
            detail: { entityId: button.dataset.entity }, bubbles: true, composed: true,
          }));
        });
      }
    }

    /** @param {string} value */
    _escape(value) {
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }
  }

  if (!customElements.get(EDITOR_TYPE)) {
    customElements.define(EDITOR_TYPE, CodexRatesCardEditor);
  }

  if (!customElements.get(CARD_TYPE)) {
    customElements.define(CARD_TYPE, CodexRatesCard);
  }

  // Always re-attach editor hooks on the *live* custom element class.
  // After upgrades, an older bundle may already have registered the tag;
  // customElements.define is then a no-op and HA would keep seeing a class
  // without getConfigForm/getConfigElement ("Visual editor not supported").
  const LiveCard = customElements.get(CARD_TYPE);
  if (LiveCard) {
    LiveCard.getConfigForm = getConfigForm;
    LiveCard.getConfigElement = () => document.createElement(EDITOR_TYPE);
    LiveCard.getStubConfig = CodexRatesCard.getStubConfig;
  }

  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === CARD_TYPE)) {
    window.customCards.push({
      type: CARD_TYPE,
      name: "Codex-LB Rates remaining",
      description: "Pool and account remaining-% at a glance.",
      preview: true,
      documentationURL: "https://github.com/uniskela/codex-lb-rates",
    });
  }

  console.info(
    `%c Codex-LB Rates card %c v${CARD_VERSION} `,
    "background:#0f2830;color:#48c9b0;padding:2px 4px;border-radius:4px 0 0 4px;",
    "background:#48c9b0;color:#0f2830;padding:2px 4px;border-radius:0 4px 4px 0;"
  );
})();
