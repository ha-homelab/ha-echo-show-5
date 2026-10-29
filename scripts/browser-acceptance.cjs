'use strict';
// Real display files; only the native bridge and HA network peer are synthetic.
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {setTimeout: delay} = require('node:timers/promises');
const playwright = require(process.env.CI_PLAYWRIGHT_MODULE);
const diagnostics = process.env.CI_BROWSER_DIAGNOSTICS;
const runtime = JSON.parse(fs.readFileSync(path.join(diagnostics, 'runtime.json'), 'utf8'));
const root = path.resolve(__dirname, '..');
const candidateMode = Boolean(process.env.CI_BROWSER_CANDIDATE_ARTIFACT_ID);
const directory = path.join(root, candidateMode ? '.browser-display' : 'integrations/show5-display');
const names = ['index.html', 'display.css', 'i18n.js', 'stream.js', 'auth.js', 'display.js', 'room.js', 'offline-worker.js', 'blank-video.svg'];
const assets = new Map(names.map(name => {
  const file = path.join(directory, name);
  assert(fs.lstatSync(file).isFile() && !fs.lstatSync(file).isSymbolicLink());
  return ['/' + name, fs.readFileSync(file)];
}));
const candidate = candidateMode ? JSON.parse(fs.readFileSync(path.join(directory, 'candidate.json'))) : null;
if (candidate) for (const key of ['sourceSha', 'runId', 'runAttempt', 'candidateArtifactId']) assert.equal(candidate[key], runtime[key]);
const token = 'synthetic-display-token-not-a-credential';
const image = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+ip1sAAAAASUVORK5CYII=', 'base64');
const mime = {'.html':'text/html', '.css':'text/css', '.js':'text/javascript', '.svg':'image/svg+xml'};
const scenarios = [], unexpected = [], errors = [], snapshots = [], sockets = [];
let selection = {locale:'en-US', hour12:false}, behavior = 'ready', observingBrowser = false;
const server = http.createServer((request, response) => {
  const url = new URL(request.url, 'http://localhost');
  if (request.method !== 'GET') {
    if (observingBrowser) unexpected.push(request.method + ' ' + url.pathname);
    return response.writeHead(405).end();
  }
  if (url.pathname === '/config.js') {
    const config = {...selection, timeZone:'UTC', cameraSeconds:5, cameraMode:'snapshots', cameras:{front:{entityId:'camera.front',motion:{topic:'fixture/front',payload:'motion'}}}};
    response.writeHead(200, {'Content-Type':'text/javascript', 'Cache-Control':'no-store'});
    return response.end('window.SHOW5_DISPLAY_CONFIG=' + JSON.stringify(config) + ';');
  }
  if (url.pathname === '/api/camera_proxy/camera.front') {
    snapshots.push({authorization:request.headers.authorization, url:request.url});
    response.writeHead(200, {'Content-Type':'image/png', 'Cache-Control':'no-store'});
    return response.end(image);
  }
  if (url.pathname === '/favicon.ico') return response.writeHead(204).end();
  const route = url.pathname === '/' ? '/index.html' : url.pathname;
  const content = assets.get(route);
  if (!content) {
    if (observingBrowser) unexpected.push('Unknown asset ' + url.pathname);
    return response.writeHead(404).end();
  }
  response.writeHead(200, {'Content-Type':mime[path.extname(route)], 'Cache-Control':'no-store'});
  response.end(content);
});
async function eventually(read, expected, message) {
  const deadline = Date.now() + 10000;
  while (Date.now() < deadline) {
    if (await read() === expected) return;
    await delay(20);
  }
  assert.equal(await read(), expected, message);
}
async function main() {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  let browser, context, page;
  try {
    assert.deepEqual(await Promise.all(['/.git/config','/config.private.js','/%2e%2e%2fREADME.md'].map(async url => (await fetch(origin + url)).status)), [404,404,404]);
    observingBrowser = true;
    browser = await playwright[runtime.engine].launch({headless:true, ...(runtime.channel ? {channel:runtime.channel} : {})});
    assert.equal(browser.version(), runtime.browserVersion);
    assert.equal(require(path.join(process.env.CI_PLAYWRIGHT_MODULE,'package.json')).version, runtime.playwrightVersion);
    context = await browser.newContext({viewport:{width:960,height:480},locale:'fr-FR',serviceWorkers:'block'});
    context.setDefaultTimeout(10000);
    await context.tracing.start({screenshots:true,snapshots:true});
    await context.route('**/*', route => {
      if (new URL(route.request().url()).origin === origin) return route.continue();
      unexpected.push(route.request().url()); return route.abort();
    });
    await context.routeWebSocket('**/*', ws => {
      if (ws.url() !== origin.replace('http:', 'ws:') + '/api/websocket') {
        unexpected.push(ws.url()); ws.close(); return;
      }
      const connection = {ws, closed:false, subscriptions:[], mode:behavior};
      sockets.push(connection);
      ws.onClose(() => { connection.closed=true; });
      ws.onMessage(raw => {
        const message = JSON.parse(raw);
        if (message.type === 'auth') {
          assert.equal(message.access_token, token);
          ws.send(JSON.stringify({type:connection.mode === 'auth-invalid' ? 'auth_invalid' : 'auth_ok'}));
        } else if (message.type === 'mqtt/subscribe') {
          assert.equal(message.topic,'fixture/front');
          connection.subscriptions.push(message.id);
          const error = connection.mode === 'unknown' ? 'unknown_command' : connection.mode === 'forbidden' ? 'unauthorized' : null;
          ws.send(JSON.stringify({type:'result',id:message.id,success:!error,...(error ? {error:{code:error}} : {})}));
        } else if (message.type === 'ping') ws.send(JSON.stringify({type:'pong',id:message.id}));
        else throw new Error('Unexpected synthetic HA command: ' + message.type);
      });
      ws.send(JSON.stringify({type:'auth_required'}));
    });
    await context.addInitScript(({token}) => {
      window.fixtureNativeRequests=[];
      window.externalApp={getExternalAuth(raw) {
        window.fixtureNativeRequests.push(JSON.parse(raw));
        queueMicrotask(() => window.externalAuthSetToken(true,{access_token:token,expires_in:3600}));
      }};
    }, {token});
    page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.on('response', response => {
      if (response.status() >= 400) unexpected.push(response.status() + ' ' + response.url());
    });
    // pauseAt() installs the clock already paused. A separate ticking install
    // at the same timestamp can advance past the target before this call.
    await page.clock.pauseAt(new Date('2026-10-15T21:34:00Z'));
    const state = () => page.evaluate(() => window.Show5Auth?.status().connection);
    const waitState = value => eventually(state,value,'Actual authentication state');
    const go = async (config={locale:'en-US',hour12:false},mode='ready') => {
      selection=config; behavior=mode;
      await page.clock.setSystemTime(new Date('2026-10-15T21:34:00Z'));
      await page.goto(origin);
      await page.locator('#clock-time').filter({hasText:/\d/}).waitFor();
    };
    const event = connection => connection.ws.send(JSON.stringify({type:'event',id:connection.subscriptions[0],event:{topic:'fixture/front',payload:'motion',retain:false}}));
    async function scenario(name, run) {
      await run(); assert.deepEqual(errors,[]); assert.deepEqual(unexpected,[]);
      scenarios.push(name); console.log('PASS '+name);
    }
    const languages = {'en-US':'Clock','ru-RU':'Часы','de-DE':'Uhr','es-ES':'Reloj'};
    for (const [locale,title] of Object.entries(languages)) {
      for (const hour12 of [false,true]) {
        await scenario(`${locale} ${hour12?'12':'24'}-hour clock renders and advances at both viewport sizes`,async () => {
          await go({locale,hour12}); await waitState('ready');
          assert.equal(await page.title(),title);
          assert.equal(await page.locator('html').getAttribute('lang'),locale);
          assert.equal(await page.locator('html').getAttribute('data-hour-cycle'),hour12?'h12':'h23');
          assert.match(await page.locator('#clock-time').innerText(),hour12 ? /^0?9[:.]/ : /^21[:.]/);
          for (const viewport of [{width:960,height:480},{width:480,height:240}]) {
            await page.setViewportSize(viewport);
            const bounds = await page.evaluate(() => {
              const r=document.querySelector('#clock-time').getBoundingClientRect();
              const d=document.querySelector('#clock-date').getBoundingClientRect();
              return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,dateLeft:d.left,dateRight:d.right,dateTop:d.top,dateBottom:d.bottom,width:innerWidth,height:innerHeight,scroll:document.documentElement.scrollWidth};
            });
            assert(bounds.left>=0 && bounds.right<=bounds.width && bounds.top>=0 && bounds.bottom<=bounds.height && bounds.dateLeft>=0 && bounds.dateRight<=bounds.width && bounds.dateTop>=0 && bounds.dateBottom<=bounds.height && bounds.scroll<=bounds.width,'Clock must fit the tested viewport');
          }
          const before=await page.locator('#clock-time').innerText();
          await page.clock.runFor(60000);
          await eventually(() => page.locator('#clock-time').innerText().then(value => value!==before),true,'DOM clock must advance after real timer callbacks');
          await page.screenshot({path:path.join(diagnostics,`${locale}-${hour12?'12':'24'}.png`)});
        });
      }
    }
    await scenario('unsupported locale falls back to English regardless of browser language',async () => {
      await go({locale:'<script>invalid</script>',hour12:false}); await waitState('ready');
      assert.equal(await page.title(),'Clock');
      assert.equal(await page.locator('html').getAttribute('lang'),'en-US');
    });
    await scenario('authenticated motion displays a real decoded snapshot and expires to the clock',async () => {
      await go(); await waitState('ready');
      event(sockets.at(-1));
      await eventually(() => page.locator('#camera-image').evaluate(image => !image.hidden && image.complete && image.naturalWidth>0),true,'Actual image must decode');
      assert.equal(await page.locator('#camera-view').getAttribute('aria-label'),'Front');
      assert.equal(await page.locator('#clock-view').isVisible(),false);
      await page.clock.runFor(5001);
      await eventually(() => page.locator('#clock-view').isVisible(),true,'Camera lease must return to the clock');
      assert(snapshots.length>0);
      assert(snapshots.every(item=>item.authorization==='Bearer '+token && !item.url.includes(token)));
    });
    await scenario('temporary unknown_command closes the old socket and recovers after the retry timer',async () => {
      await go({locale:'en-US',hour12:false},'unknown'); await waitState('reconnecting');
      const old=sockets.at(-1), count=sockets.length;
      await eventually(()=>old.closed,true,'Unavailable subscription socket must close');
      behavior='ready';
      await page.clock.runFor(999); assert.equal(sockets.length,count);
      await page.clock.runFor(1); await waitState('ready');
      assert.equal(sockets.length,count+1);
      assert.equal(await page.evaluate(()=>Show5Auth.status().lastError),null);
    });
    await scenario('permission rejection stays blocked and cannot activate a camera',async () => {
      const count=snapshots.length;
      await go({locale:'en-US',hour12:false},'forbidden'); await waitState('forbidden');
      const socketCount=sockets.length;
      await page.clock.runFor(31000);
      assert.equal(await state(),'forbidden'); assert.equal(sockets.length,socketCount);
      assert.equal(snapshots.length,count); assert(await page.locator('#clock-view').isVisible());
    });
    await scenario('invalid authentication refreshes credentials but never marks subscriptions ready',async () => {
      const count=snapshots.length;
      await go({locale:'en-US',hour12:false},'auth-invalid'); await waitState('reconnecting');
      await page.clock.runFor(1000); await waitState('reconnecting');
      const requests=await page.evaluate(()=>fixtureNativeRequests);
      assert(requests.some(request=>request.force===true));
      assert.equal(await page.evaluate(()=>Show5Auth.status().authenticated),false);
      assert.equal(snapshots.length,count);
    });
    await scenario('pagehide closes the connection and pageshow reauthenticates without persisted tokens',async () => {
      await go(); await waitState('ready');
      const old=sockets.at(-1);
      await page.evaluate(()=>window.dispatchEvent(new Event('pagehide')));
      await waitState('hidden'); await eventually(()=>old.closed,true,'Hidden page must close transport');
      await page.evaluate(()=>window.dispatchEvent(new Event('pageshow'))); await waitState('ready');
      assert.deepEqual(await page.evaluate(()=>[localStorage.length,sessionStorage.length,document.cookie]),[0,0,'']);
      assert(!(await page.locator('body').innerText()).includes(token));
    });
    assert.equal(scenarios.length,14);
    fs.writeFileSync(process.env.CI_BROWSER_EVIDENCE,JSON.stringify({...runtime,scenarios,testsPassed:scenarios.length,testsFailed:0,
      applicationFiles:Object.fromEntries([...assets].map(([name,bytes])=>[name,crypto.createHash('sha256').update(bytes).digest('hex')])),
      ...(candidate?{candidateArchiveSha256:candidate.archiveSha256}:{})},null,2)+'\n');
  } catch(error) {
    if(page) await page.screenshot({path:path.join(diagnostics,'failure.png'),fullPage:true}).catch(()=>{});
    throw error;
  } finally {
    if(context) await context.tracing.stop({path:path.join(diagnostics,'trace.zip')}).catch(()=>{});
    if(browser) await browser.close();
    server.closeAllConnections();
    await new Promise(resolve=>server.close(resolve));
  }
}
main().catch(error=>{console.error(error);process.exitCode=1;});
