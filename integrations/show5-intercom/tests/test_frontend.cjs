// Offline browser lifecycle tests. All media/HA interfaces are inert fakes.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const classes=new Map();
const sandbox={HTMLElement:class{},customElements:{define:(n,c)=>classes.set(n,c)},window:{},document:{addEventListener(){},removeEventListener(){}},navigator:{mediaDevices:{}},isSecureContext:true,console,setTimeout,clearTimeout,Float32Array,Uint8Array,DataView,ArrayBuffer,btoa:s=>Buffer.from(s,'binary').toString('base64'),atob:s=>Buffer.from(s,'base64').toString('binary')};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(path.join(__dirname,'../www/show5-intercom-card.js'),'utf8'),sandbox);
const deferred=()=>{let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};};
const tick=()=>new Promise(r=>setImmediate(r));
async function run(){
  let count=0;
  {
    const card=new (classes.get('show5-video-call-card'))(),wait=deferred();let cancelled=0;
    card.epoch=1;card.isConnected=true;card.config={role:'show'};card.status=()=>{};
    card._hass={connection:{subscribeMessage:()=>wait.promise}};
    const pending=card.join();card.isConnected=false;card.epoch++;wait.resolve(()=>cancelled++);await pending;
    assert.equal(cancelled,1);assert.equal(card.unsubscribe,undefined);count++;
  }
  {
    const card=new (classes.get('show5-video-call-card'))(),wait=deferred();let stopped=0;
    card.epoch=1;sandbox.navigator.mediaDevices.getUserMedia=()=>wait.promise;
    const pending=card.media();card.epoch++;wait.resolve({getTracks:()=>[{stop:()=>stopped++}]});
    await assert.rejects(pending,/cancelled/);assert.equal(stopped,1);count++;
  }
  {
    const card=new (classes.get('show5-intercom-card'))(),wait=deferred();let stopped=0,requests=0;
    card.epoch=1;card.controls=()=>{};card.status=()=>{};card.ws=()=>{requests++;throw Error('unexpected HA request');};
    sandbox.navigator.mediaDevices.getUserMedia=()=>wait.promise;
    const pending=card.record();await card.cancel();wait.resolve({getTracks:()=>[{stop:()=>stopped++}]});await pending;
    assert.equal(stopped,1);assert.equal(requests,0);count++;
  }
  {
    const card=new (classes.get('show5-intercom-card'))(),wait=deferred();let stopped=0,ended=0;
    card.epoch=1;card.controls=()=>{};card.status=()=>{};
    card.ws=(command)=>command==='begin'?wait.promise:(ended++,Promise.resolve());
    sandbox.navigator.mediaDevices.getUserMedia=()=>Promise.resolve({getTracks:()=>[{stop:()=>stopped++}]});
    const pending=card.record();await tick();await card.cancel();wait.resolve({session:'test'});await pending;
    assert.equal(ended,1);assert.ok(stopped>=1);assert.equal(card.session,null);count++;
  }
  {
    const card=new (classes.get('show5-video-call-card'))(),wait=deferred();let callback,stopped=0;
    card.epoch=1;card.isConnected=true;card.config={role:'show'};card.status=()=>{};
    card.shadowRoot={getElementById:()=>({srcObject:null})};
    card._hass={connection:{subscribeMessage:async cb=>{callback=cb;return ()=>{};}}};
    sandbox.navigator.mediaDevices.getUserMedia=()=>wait.promise;
    await card.join();callback({event:'ready',call_id:'a'.repeat(32)});await tick();
    const priorEpoch=card.epoch;callback({event:'ended'});
    assert.ok(card.epoch>priorEpoch,'ended must invalidate capture before the pending permission promise resolves');
    wait.resolve({getTracks:()=>[{stop:()=>stopped++}]});await tick();
    assert.equal(stopped,1);assert.equal(card.pc,undefined);count++;
  }
  {
    const card=new (classes.get('show5-video-call-card'))(),ack=deferred();let callback,status;
    card.epoch=1;card.isConnected=true;card.config={role:'show'};card.status=text=>status=text;
    // Reproduce the pinned library's async subscribeMessage wrapper: it awaits
    // the result while event callbacks can run in that same received WS batch.
    card._hass={connection:{subscribeMessage:async cb=>{callback=cb;await ack.promise;return ()=>{};}}};
    const joining=card.join();
    ack.resolve();
    callback({event:'incoming'}); // Library delivers message.event, not envelope.
    await joining;await tick();
    assert.match(status,/Incoming private call/,'late subscription resolution must not overwrite ringing with Ready');
    assert.equal(typeof card.unsubscribe,'function');count++;
  }
  {
    const card=new (classes.get('show5-video-call-card'))();let callback,status,ended=0;const logs=[];
    card.epoch=1;card.isConnected=true;card.config={role:'show'};card.status=text=>status=text;
    card.shadowRoot={getElementById:()=>({srcObject:null})};
    card._hass={connection:{subscribeMessage:async cb=>{callback=cb;return ()=>{};}}};
    card.ws=async(command,data)=>{assert.equal(command,'room_action');assert.equal(data.action,'end');ended++;callback({event:'ended'});};
    const error=new Error('private URL/token must never be printed');error.name='NotAllowedError';
    sandbox.navigator.mediaDevices.getUserMedia=()=>Promise.reject(error);
    sandbox.console={warn:(...args)=>logs.push(args)};
    await card.join();callback({event:'joined',role:'show',peer_id:'b'.repeat(32)});callback({event:'ready',call_id:'a'.repeat(32)});await card.events;await tick();
    assert.equal(card.lastFailure.stage,'media');assert.equal(card.lastFailure.code,'NotAllowedError');
    assert.match(status,/camera\/microphone \(NotAllowedError\)/);assert.match(status,/Restoration command completed/);
    assert.equal(ended,1);assert.deepEqual(logs,[['SHOW5_CALL_FAILURE','media','NotAllowedError']]);
    callback({event:'ended'});assert.match(status,/NotAllowedError/,'backend ended must retain the initiating failure');
    assert.ok(!JSON.stringify(logs).includes(error.message));sandbox.console=console;count++;
  }
  {
    const card=new (classes.get('show5-video-call-card'))();let callback,status,closed=0;const logs=[];
    card.epoch=1;card.isConnected=true;card.config={role:'show'};card.status=text=>status=text;
    card.shadowRoot={getElementById:()=>({srcObject:null})};
    card._hass={connection:{subscribeMessage:async cb=>{callback=cb;return ()=>{};}}};card.ws=async()=>{};
    card.pc={setRemoteDescription:async()=>{throw {name:'OperationError',message:'private SDP contents'};},close:()=>closed++};
    sandbox.console={warn:(...args)=>logs.push(args)};
    await card.join();callback({event:'joined',role:'show',peer_id:'b'.repeat(32)});callback({event:'signal',kind:'offer',data:{type:'offer',sdp:'never log this'}});await card.events;
    assert.equal(card.lastFailure.stage,'remote_description');assert.equal(card.lastFailure.code,'OperationError');
    assert.match(status,/remote negotiation \(OperationError\)/);assert.equal(closed,1);
    assert.deepEqual(logs,[['SHOW5_CALL_FAILURE','remote_description','OperationError']]);sandbox.console=console;count++;
  }
  {
    const card=new (classes.get('show5-video-call-card'))(),logs=[];
    sandbox.console={warn:(...args)=>logs.push(args)};
    card.failure('private URL',{name:'secret error',code:'secret code',message:'secret'});
    assert.equal(card.lastFailure.stage,'event');assert.equal(card.lastFailure.code,'UnknownError');
    assert.deepEqual(logs,[['SHOW5_CALL_FAILURE','event','UnknownError']]);sandbox.console=console;count++;
  }
  {
    const card=new (classes.get('show5-video-call-card'))(),timers=[],logs=[];let status,stopped=0,closed=0;
    card.epoch=1;card.peerId='b'.repeat(32);card.status=text=>status=text;card.shadowRoot={getElementById:()=>({srcObject:null})};card.ws=async()=>{};
    sandbox.navigator.mediaDevices.getUserMedia=async()=>({getTracks:()=>[{stop:()=>stopped++}]});
    sandbox.RTCPeerConnection=class{addTrack(){}close(){closed++;}};
    sandbox.setTimeout=(fn,delay)=>{timers.push({fn,delay});return timers.length;};sandbox.clearTimeout=()=>{};
    sandbox.console={warn:(...args)=>logs.push(args)};
    await card.media();assert.equal(timers[0].delay,20000);await timers[0].fn();
    assert.equal(card.lastFailure.stage,'connection');assert.equal(card.lastFailure.code,'connection_timeout');
    assert.match(status,/connection_timeout/);assert.equal(stopped,1);assert.equal(closed,1);
    assert.deepEqual(logs,[['SHOW5_CALL_FAILURE','connection','connection_timeout']]);
    sandbox.setTimeout=setTimeout;sandbox.clearTimeout=clearTimeout;sandbox.console=console;count++;
  }
  {
    const card=new (classes.get('show5-video-call-card'))();let requests=0;
    card.epoch=1;card.status=()=>{};card.shadowRoot={getElementById:()=>({srcObject:null})};card.ws=async()=>{requests++;};
    card.disconnectedCallback();await tick();assert.equal(requests,0,'removing an unjoined card must not end a shared-socket room');count++;
  }
  {
    const card=new (classes.get('show5-video-call-card'))(),wait=deferred();let callback,unsubscribed=0,requests=0;
    card.epoch=1;card.isConnected=true;card.config={role:'show'};card.status=()=>{};card.shadowRoot={getElementById:()=>({srcObject:null})};
    card.ws=async()=>{requests++;};card._hass={connection:{subscribeMessage:cb=>{callback=cb;return wait.promise;}}};
    const pending=card.join();card.isConnected=false;card.disconnectedCallback();
    callback({event:'joined',role:'show',peer_id:'a'.repeat(32)});
    wait.resolve(()=>{unsubscribed++;});await pending;
    assert.equal(card.peerId,null);assert.equal(unsubscribed,1);assert.equal(requests,0);count++;
  }
  {
    const card=new (classes.get('show5-video-call-card'))(),requests=[];
    card.epoch=1;card.peerId='a'.repeat(32);card.status=()=>{};card.shadowRoot={getElementById:()=>({srcObject:null})};
    card.ws=async(command,data)=>{requests.push({command,...data});};card.unsubscribe=()=>{};
    card.disconnectedCallback();card.peerId='b'.repeat(32);await tick();
    assert.equal(requests.length,1);assert.equal(requests[0].peer_id,'a'.repeat(32),'old cleanup must carry its captured membership');count++;
  }
  {
    const card=new (classes.get('show5-video-call-card'))(),button={},accepted=deferred();let callback,requests=0;
    card.epoch=1;card.isConnected=true;card.config={role:'show'};card.status=()=>{};
    card.shadowRoot={getElementById:id=>id==='start'?button:{srcObject:null}};
    card._hass={connection:{subscribeMessage:async cb=>{callback=cb;return ()=>{};}}};card.ws=()=>{requests++;return accepted.promise;};
    await card.join();assert.equal(button.disabled,true);await card.command('accept');assert.equal(requests,0);
    callback({event:'joined',role:'show',peer_id:'a'.repeat(32)});assert.equal(button.disabled,true);
    callback({event:'incoming'});await card.events;assert.equal(button.disabled,false);
    const pending=card.command('accept');assert.equal(button.disabled,true);await card.command('accept');assert.equal(requests,1);
    accepted.resolve();await pending;assert.equal(button.disabled,true);count++;
  }
  {
    const card=new (classes.get('show5-video-call-card'))(),button={},started=deferred();let callback,requests=0;
    card.epoch=1;card.isConnected=true;card.config={role:'caller'};card.status=()=>{};
    card.shadowRoot={getElementById:id=>id==='start'?button:{srcObject:null}};
    card._hass={connection:{subscribeMessage:async cb=>{callback=cb;return ()=>{};}}};card.ws=()=>{requests++;return started.promise;};
    await card.join();assert.equal(button.disabled,true);
    callback({event:'joined',role:'caller',peer_id:'a'.repeat(32)});assert.equal(button.disabled,false);
    const pending=card.command('call');assert.equal(button.disabled,true);await card.command('call');assert.equal(requests,1);
    started.resolve();await pending;assert.equal(button.disabled,true);
    callback({event:'ended'});assert.equal(button.disabled,true,'restoration is still pending');
    callback({event:'restored'});assert.equal(button.disabled,false);count++;
  }
  {
    const card=new (classes.get('show5-video-call-card'))(),ended=deferred();
    card.epoch=1;card.membershipEpoch=1;card.peerId='a'.repeat(32);card.config={role:'caller'};
    card.status=()=>{};card.shadowRoot={getElementById:()=>({srcObject:null})};card.ws=()=>ended.promise;
    const pending=card.hangup();card.membershipEpoch++;card.peerId='b'.repeat(32);card.setPhase('ringing');
    ended.resolve();await pending;assert.equal(card.phase,'ringing','old cleanup acknowledgement must not alter the replacement UI');count++;
  }
  console.log(`${count} frontend cancellation/late-completion tests passed; no real media or HA calls`);
}
run().catch(error=>{console.error(error);process.exitCode=1;});
