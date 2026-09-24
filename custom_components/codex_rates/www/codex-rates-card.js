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
  const CARD_VERSION = "1.1.0";

  /** @param {number} value */
  function clampPercent(value) {
    if (Number.isNaN(value)) return null;
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

  class CodexRatesCard extends HTMLElement {
    constructor() {
      super();
      /** @type {Record<string, unknown> | null} */
      this._config = null;
      /** @type {any} */
      this._hass = null;
      this._root = this.attachShadow({ mode: "open" });
    }

    static getStubConfig() {
      return {
        type: `custom:${CARD_TYPE}`,
        title: "Codex remaining",
        entity: "sensor.codex_lb_pool_all_accounts_5h_remaining",
        entities: ["sensor.codex_lb_pool_all_accounts_weekly_remaining"],
      };
    }

    /**
     * Built-in ha-form visual editor (HA ≈2023.5+).
     * Object-form `entities` rows ({ entity, name? }) stay YAML-only —
     * assertConfig disables the visual tab whenever `entities` is not a
     * plain string list so a GUI save cannot rewrite/strip that shape.
     */
    static getConfigForm() {
      return {
        schema: [
          { name: "title", selector: { text: {} } },
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
        ],
        computeLabel: (schema) => {
          switch (schema.name) {
            case "title":
              return "Title";
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
        },
        computeHelper: (schema) => {
          switch (schema.name) {
            case "entity":
              return "Large remaining-% value and progress bar. At least one of primary or additional entities is required.";
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
        },
        assertConfig: (config) => {
          const list = Array.isArray(config?.entities) ? config.entities : [];
          for (const item of list) {
            if (typeof item !== "string") {
              throw new Error(
                "Object-form entities (including per-row names) are only editable in YAML; use the code editor."
              );
            }
          }
        },
      };
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
      this._config = { ...config, _entities: entities };
      this._render();
    }

    /** @param {any} hass */
    set hass(hass) {
      this._hass = hass;
      this._render();
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
      const min = formatOptionalNumber(attrs.min);
      const max = formatOptionalNumber(attrs.max);
      if (min !== null && max !== null) metaParts.push(`min ${min}% · max ${max}%`);
      const samples = formatOptionalNumber(attrs.sample_count);
      if (samples !== null) metaParts.push(`${samples} measured`);
      const weighting = attrs.weighting_method ? String(attrs.weighting_method) : null;
      if (weighting) metaParts.push(weighting.replaceAll("_", " "));

      const rowsHtml = rest
        .map((row) => {
          const stateObj = this._hass?.states?.[row.entity];
          const value = parseRemaining(stateObj?.state);
          const label =
            row.name || stateObj?.attributes?.friendly_name || row.entity;
          const rowColor = bandColor(value, thresholds);
          const display = value === null ? "—" : `${value.toFixed(value % 1 ? 1 : 0)}%`;
          const unavailable =
            !stateObj ||
            stateObj.state === "unavailable" ||
            stateObj.state === "unknown";
          return `
            <div class="row${unavailable ? " muted" : ""}">
              <span class="row-name">${this._escape(label)}</span>
              <span class="row-value" style="color:${rowColor}">${display}</span>
            </div>
          `;
        })
        .join("");

      const primaryDisplay =
        primaryValue === null
          ? "—"
          : `${primaryValue.toFixed(primaryValue % 1 ? 1 : 0)}%`;

      this._root.innerHTML = `
        <style>
          :host {
            display: block;
          }
          ha-card {
            --codex-accent: ${color};
            padding: 16px;
            overflow: hidden;
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
            color: var(--primary-text-color);
            line-height: 1.3;
          }
          .subtitle {
            font-size: 0.8rem;
            color: var(--secondary-text-color);
            margin-top: 2px;
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
            color: var(--primary-text-color);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }
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
        </style>
        <ha-card>
          <div class="header">
            <div>
              <div class="title">${this._escape(title)}</div>
              <div class="subtitle">${this._escape(primaryName)}</div>
            </div>
          </div>
          <div class="hero">
            <div class="pct">${primaryDisplay}</div>
            <div class="pct-label">remaining</div>
          </div>
          <div class="bar" role="progressbar" aria-valuemin="0" aria-valuemax="100"
               aria-valuenow="${primaryValue === null ? "" : primaryValue}"
               aria-label="${this._escape(primaryName)} remaining">
            <span></span>
          </div>
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
        </ha-card>
      `;
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

  if (!customElements.get(CARD_TYPE)) {
    customElements.define(CARD_TYPE, CodexRatesCard);
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
