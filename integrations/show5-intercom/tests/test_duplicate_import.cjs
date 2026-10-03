// Actual ES module evaluation under distinct URLs, with an inert browser registry.
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const source=fs.readFileSync(path.join(__dirname,'../www/show5-intercom-card.js'),'utf8');
const moduleUrl='data:text/javascript;base64,'+Buffer.from(source).toString('base64');
async function run(){
  let count=0;
  for(const order of [['plain','query'],['query','plain']]){
    const classes=new Map(),definitions=[];
    global.HTMLElement=class{};
    global.window={customCards:[{type:'unrelated-card',name:'Keep me'}]};
    global.customElements={
      get:name=>classes.get(name),
      define(name,type){
        assert.ok(!classes.has(name),'browser rejects duplicate custom element definitions');
        classes.set(name,type);definitions.push(name);
      },
    };
    // Fragments give each import a distinct module identity and lexical scope,
    // equivalent to plain and cache-busted resource URLs. No network is used.
    await import(moduleUrl+'#fixture-'+count+'-'+order[0]);
    const first=new Map(classes);
    await import(moduleUrl+'#fixture-'+count+'-'+order[1]);
    assert.equal(definitions.length,3);
    for(const [name,type] of first)assert.equal(classes.get(name),type,'second import preserves the registered constructor');
    assert.equal(window.customCards.length,3,'card picker entries are not duplicated');
    assert.equal(window.customCards[0].name,'Keep me');
    assert.equal(new (classes.get('show5-intercom-card'))().getCardSize(),3);
    assert.equal(new (classes.get('show5-video-call-card'))().getCardSize(),5);
    assert.equal(new (classes.get('show5-readiness-card'))().getCardSize(),0);
    count++;
  }
  console.log(`${count} duplicate ES module import tests passed; no browser, media, HA or network calls`);
}
run().catch(error=>{console.error(error);process.exitCode=1;});
