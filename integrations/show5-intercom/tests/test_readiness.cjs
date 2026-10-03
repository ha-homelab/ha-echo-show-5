// Inert, deterministic checks: no browser bridge, HA, device or network access.
const fs=require("node:fs"),vm=require("node:vm"),assert=require("node:assert/strict"),path=require("node:path");
const source=fs.readFileSync(path.join(__dirname,"../www/show5-intercom-card.js"),"utf8");
function fixture(){
  let now=0,id=0,sends=0,launch=false;
  const timers=new Map(),frames=new Map(),classes=new Map();
  const document={getElementById:()=>launch?{}:null};
  const window={location:{pathname:"/echo-show/receive"}};window.top=window;
  const sandbox={window,document,console,HTMLElement:class{
    attachShadow(){this.shadowRoot={innerHTML:""};}
    getRootNode(){return {host:null};}
  },customElements:{define:(name,type)=>classes.set(name,type)},
  setTimeout:(fn,delay)=>{timers.set(++id,{fn,at:now+delay});return id;},clearTimeout:key=>timers.delete(key),
  requestAnimationFrame:fn=>{frames.set(++id,fn);return id;},cancelAnimationFrame:key=>frames.delete(key)};
  vm.createContext(sandbox);vm.runInContext(source,sandbox);
  const view={localName:"hui-masonry-view",isConnected:true,hasUpdated:true,isUpdatePending:false,getClientRects:()=>[{width:900,height:300}]};
  const hass={connection:{connected:true},user:{id:"inert"},config:{},states:{},auth:{external:{fireMessage:message=>{assert.equal(message.type,"frontend/loaded");assert.deepEqual(Object.keys(message),["type"]);sends++;}}}};
  const create=(enabled=true)=>{const card=new (classes.get("show5-readiness-card"))();card.isConnected=false;card.parentElement=view;card.setConfig({enabled});card.hass=hass;return card;};
  const connect=card=>{card.isConnected=true;card.connectedCallback();};
  const disconnect=card=>{card.isConnected=false;card.disconnectedCallback();};
  const frame=()=>{const pending=[...frames.values()];frames.clear();pending.forEach(fn=>fn());};
  const advance=ms=>{const end=now+ms;for(;;){const next=[...timers].filter(([,v])=>v.at<=end).sort((a,b)=>a[1].at-b[1].at)[0];if(!next)break;now=next[1].at;timers.delete(next[0]);next[1].fn();}now=end;};
  return {sandbox,hass,view,create,connect,disconnect,frame,advance,timers,frames,get sends(){return sends;},set launch(value){launch=value;}};
}
let count=0;
{
  const f=fixture();f.connect(f.create(false));f.advance(31000);f.frame();f.frame();assert.equal(f.sends,0);assert.equal(f.timers.size,0);count++;
}
for(const change of [f=>f.hass.connection.connected=false,f=>delete f.hass.auth.external,f=>delete f.hass.user,f=>delete f.hass.config,f=>delete f.hass.states,f=>f.launch=true,f=>f.sandbox.window.top={},f=>f.sandbox.window.location.pathname="/other/home",f=>f.view.hasUpdated=false,f=>f.view.isUpdatePending=true,f=>f.view.getClientRects=()=>[]]){
  const f=fixture();change(f);f.connect(f.create());f.advance(31000);f.frame();f.frame();assert.equal(f.sends,0);assert.equal(f.timers.size,0);assert.equal(f.frames.size,0);count++;
}
{
  const f=fixture(),card=f.create();f.connect(card);f.frame();assert.equal(f.sends,0);f.frame();assert.equal(f.sends,1);assert.equal(f.timers.size,0);
  f.connect(f.create());card.hass=f.hass;f.advance(31000);f.frame();f.frame();assert.equal(f.sends,1,"one event across all cards in the document");count++;
}
{
  const f=fixture(),card=f.create();f.connect(card);f.frame();f.disconnect(card);f.frame();f.advance(31000);assert.equal(f.sends,0);assert.equal(f.timers.size,0);assert.equal(f.frames.size,0);count++;
}
{
  const f=fixture(),card=f.create();f.connect(card);f.frame();f.hass.connection.connected=false;f.frame();assert.equal(f.sends,0);f.advance(31000);assert.equal(f.sends,0);assert.equal(f.timers.size,0);count++;
}
{
  const f=fixture(),card=f.create();f.hass.connection.connected=false;f.connect(card);f.advance(500);f.hass.connection.connected=true;f.advance(250);f.frame();f.frame();assert.equal(f.sends,1,"retry only after actual connection");count++;
}
{
  const f=fixture(),card=f.create();f.connect(card);f.disconnect(card);f.connect(card);f.frame();f.frame();assert.equal(f.sends,1,"a reconnected card gets a fresh bounded attempt");count++;
}
console.log(`${count} readiness guard/lifecycle tests passed; no bridge or HA calls`);
