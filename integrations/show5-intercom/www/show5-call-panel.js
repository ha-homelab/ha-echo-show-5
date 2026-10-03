// A receiver-only HA custom panel. The existing card owns media and room cleanup.
import "./show5-intercom-card.js";

const panelStyles = `
  :host {
    display: block;
    box-sizing: border-box;
    height: 100%;
    overflow: auto;
    padding: 8px;
    color: var(--primary-text-color, #222);
    background: var(--primary-background-color, #fff);
    font-family: var(--paper-font-body1_-_font-family, sans-serif);
  }
  main { max-width: 960px; margin: 0 auto; }
  header { display: flex; align-items: center; gap: 16px; min-height: 32px; }
  h1 { margin: 0; font-size: 16px; font-weight: 500; }
  a { color: var(--primary-color, #03a9f4); padding: 6px; }
  show5-video-call-card { display: block; }
`;

class Show5CallPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  set hass(value) {
    this._hass = value;
    if (this._card) this._card.hass = value;
  }

  get hass() {
    return this._hass;
  }

  connectedCallback() {
    // Retain the child across reattachment; its own lifecycle rejoins the room.
    if (this._card) return;

    const style = document.createElement("style");
    style.textContent = panelStyles;
    const main = document.createElement("main");
    const header = document.createElement("header");
    const home = document.createElement("a");
    home.setAttribute("href", "/echo-show/home");
    home.setAttribute("aria-label", "Return to Echo Show home");
    home.textContent = "← Home";
    const title = document.createElement("h1");
    title.textContent = "Receive a call";
    header.append(home, title);

    this._card = document.createElement("show5-video-call-card");
    this._card.setConfig({ role: "show" });
    if (this._hass) this._card.hass = this._hass;
    main.append(header, this._card);
    this.shadowRoot.append(style, main);
    // No panel disconnect handler: removing this subtree invokes the card's
    // existing cleanup, without a second hangup or a separate media owner.
  }
}

if (!customElements.get("show5-call-panel")) {
  customElements.define("show5-call-panel", Show5CallPanel);
}
