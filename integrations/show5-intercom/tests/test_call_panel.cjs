// Inert custom-panel tests: the imported receiver is a lifecycle fake.
// No HA connection, browser authentication bridge, capture, or network access.
const fs = require("node:fs");
const vm = require("node:vm");
const path = require("node:path");
const assert = require("node:assert/strict");

const source = fs.readFileSync(
  path.join(__dirname, "../www/show5-call-panel.js"), "utf8"
);
const dependency = 'import "./show5-intercom-card.js";';
assert.equal(source.split(dependency).length, 2, "one fixed local module dependency");
// Only this checked import is replaced by the inert receiver below. vm.Script
// rejects any other static import; all active APIs are absent from the sandbox.
const script = new vm.Script(`(() => {\n${source.replace(dependency, "")}\n})();`);

function fixture() {
  const classes = new Map();
  const receivers = [];
  const lifecycle = (node, connected) => {
    if (node.isConnected === connected) return;
    node.isConnected = connected;
    if (connected) node.connectedCallback?.();
    else node.disconnectedCallback?.();
    for (const child of node.children) lifecycle(child, connected);
    if (node.shadowRoot) lifecycle(node.shadowRoot, connected);
  };
  class Element {
    constructor(tag = "") {
      this.localName = tag;
      this.children = [];
      this.attributes = {};
      this.isConnected = false;
    }
    attachShadow() {
      this.shadowRoot = new Element("#shadow-root");
      this.shadowRoot.isConnected = this.isConnected;
      return this.shadowRoot;
    }
    setAttribute(key, value) { this.attributes[key] = value; }
    append(...children) {
      for (const child of children) {
        this.children.push(child);
        if (this.isConnected) lifecycle(child, true);
      }
    }
  }
  class Receiver extends Element {
    constructor() {
      super("show5-video-call-card");
      this.configs = [];
      this.values = [];
      this.connected = 0;
      this.cleaned = 0;
      receivers.push(this);
    }
    setConfig(config) { this.configs.push(config); }
    set hass(value) { this.values.push(value); }
    connectedCallback() { this.connected++; }
    disconnectedCallback() { this.cleaned++; }
  }
  classes.set("show5-video-call-card", Receiver);
  const document = {
    createElement(tag) {
      return classes.has(tag) ? new (classes.get(tag))() : new Element(tag);
    },
  };
  const sandbox = {
    document,
    HTMLElement: Element,
    customElements: {
      get: name => classes.get(name),
      define(name, type) {
        assert.ok(!classes.has(name), "duplicate custom element definition");
        classes.set(name, type);
      },
    },
  };
  vm.createContext(sandbox);
  script.runInContext(sandbox);
  return {
    create: () => new (classes.get("show5-call-panel"))(),
    connect: panel => lifecycle(panel, true),
    disconnect: panel => lifecycle(panel, false),
    evaluateAgain: () => script.runInContext(sandbox),
    receivers,
    classes,
  };
}

let count = 0;
{
  const f = fixture(), panel = f.create();
  const hass = Object.freeze({ callWS() { throw Error("unexpected call"); } });
  panel.hass = hass;
  assert.equal(f.receivers.length, 0, "construction has no room/media side effects");
  f.connect(panel);
  const card = f.receivers[0];
  assert.equal(f.receivers.length, 1);
  assert.equal(card.configs.length, 1);
  assert.equal(card.configs[0].role, "show");
  assert.deepEqual(Object.keys(card.configs[0]), ["role"]);
  assert.equal(card.values[0], hass, "forward the supplied object without a new auth client");
  assert.equal(card.connected, 1);
  count++;
}
{
  const f = fixture(), panel = f.create();
  f.connect(panel);
  const first = {}, second = {};
  panel.hass = first;
  panel.hass = second;
  assert.deepEqual(f.receivers[0].values, [first, second]);
  assert.equal(panel.hass, second);
  assert.equal(f.receivers.length, 1, "state updates must not recreate the receiver");
  count++;
}
{
  const f = fixture(), panel = f.create();
  panel.panel = { config: { role: "caller", module_url: "https://invalid.example/evil.js" } };
  panel.route = { path: "/other" };
  f.connect(panel);
  const main = panel.shadowRoot.children.find(node => node.localName === "main");
  const home = main.children[0].children[0];
  assert.equal(home.attributes.href, "/echo-show/home");
  assert.equal(f.receivers[0].configs[0].role, "show", "panel config cannot select caller role");
  assert.deepEqual(main.children.map(node => node.localName), ["header", "show5-video-call-card"]);
  count++;
}
{
  const f = fixture(), panel = f.create();
  f.connect(panel);
  const card = f.receivers[0];
  f.disconnect(panel);
  assert.equal(card.cleaned, 1, "native subtree removal reaches receiver cleanup once");
  f.connect(panel);
  assert.equal(f.receivers.length, 1);
  assert.equal(card.connected, 2, "reattachment preserves receiver lifecycle");
  assert.equal(card.configs.length, 1, "reattachment must not reset active card configuration");
  f.disconnect(panel);
  assert.equal(card.cleaned, 2);
  count++;
}
{
  const f = fixture(), original = f.classes.get("show5-call-panel");
  f.evaluateAgain();
  assert.equal(f.classes.get("show5-call-panel"), original);
  count++;
}
console.log(`${count} isolated call-panel tests passed; no HA, bridge, media, or network calls`);
