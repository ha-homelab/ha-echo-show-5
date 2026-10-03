// Offline browser lifecycle tests. All media/HA interfaces are inert fakes.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict'),path=require('node:path');
const classes=new Map();
const sandbox={HTMLElement:class{},customElements:{get:n=>classes.get(n),define:(n,c)=>classes.set(n,c)},window:{},document:{addEventListener(){},removeEventListener(){}},navigator:{mediaDevices:{}},isSecureContext:true,console,setTimeout,clearTimeout,Float32Array,Uint8Array,DataView,ArrayBuffer,btoa:s=>Buffer.from(s,'binary').toString('base64'),atob:s=>Buffer.from(s,'base64').toString('binary')};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(path.join(__dirname,'../www/show5-intercom-card.js'),'utf8'),sandbox);
const deferred=()=>{let resolve,reject;const promise=new Promise((r,j)=>{resolve=r;reject=j;});return {promise,resolve,reject};};
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
    sandbox.console={info(){},warn:(...args)=>logs.push(args)};
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
    sandbox.console={info(){},warn:(...args)=>logs.push(args)};
    await card.join();callback({event:'joined',role:'show',peer_id:'b'.repeat(32)});callback({event:'signal',kind:'offer',data:{type:'offer',sdp:'never log this'}});await card.events;
    assert.equal(card.lastFailure.stage,'remote_description');assert.equal(card.lastFailure.code,'OperationError');
    assert.match(status,/remote negotiation \(OperationError\)/);assert.equal(closed,1);
    assert.deepEqual(logs,[['SHOW5_CALL_FAILURE','remote_description','OperationError']]);sandbox.console=console;count++;
  }
  {
    const card=new (classes.get('show5-video-call-card'))(),logs=[];
    sandbox.console={info(){},warn:(...args)=>logs.push(args)};
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
    sandbox.console={info(){},warn:(...args)=>logs.push(args)};
    await card.media();assert.equal(timers[0].delay,45000);await timers[0].fn();
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
    const card=new (classes.get('show5-video-call-card'))(),button={},accepted=deferred();let callback,requests=0,status;
    card.epoch=1;card.isConnected=true;card.config={role:'show'};card.status=text=>status=text;
    card.shadowRoot={getElementById:id=>id==='start'?button:{srcObject:null}};
    card._hass={connection:{subscribeMessage:async cb=>{callback=cb;return ()=>{};}}};card.ws=()=>{requests++;return accepted.promise;};
    await card.join();assert.equal(button.disabled,true);await card.command('accept');assert.equal(requests,0);
    callback({event:'joined',role:'show',peer_id:'a'.repeat(32)});assert.equal(button.disabled,true);
    callback({event:'incoming'});await card.events;assert.equal(button.disabled,false);
    const pending=card.command('accept');assert.equal(button.disabled,true);assert.match(status,/Preparing the Show camera and microphone/);await card.command('accept');assert.equal(requests,1);
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
  {
    // Real subscription queue: an offer/ICE arriving while permission is pending
    // must wait for local media, then negotiate without dropping either event.
    const card=new (classes.get('show5-video-call-card'))(),capture=deferred(),logs=[],steps=[],timers=[],cleared=[];let callback,status;
    card.epoch=1;card.isConnected=true;card.config={role:'show'};card.status=text=>status=text;
    card.shadowRoot={getElementById:()=>({srcObject:null})};
    card._hass={connection:{subscribeMessage:async cb=>{callback=cb;return ()=>{};}}};
    card.ws=async(command,data)=>{assert.equal(command,'signal');assert.equal(data.kind,'answer');steps.push('answer_sent');};
    sandbox.console={info:(...args)=>logs.push(args),warn:(...args)=>logs.push(args)};
    sandbox.setTimeout=(fn,delay)=>{timers.push({fn,delay});return timers.length;};sandbox.clearTimeout=id=>cleared.push(id);
    sandbox.navigator.mediaDevices.getUserMedia=()=>capture.promise;
    sandbox.RTCPeerConnection=class {
      addTrack(){steps.push('track');}
      async setRemoteDescription(data){assert.equal(data.sdp,'private-sdp');this.remoteDescription=data;steps.push('remote');}
      async addIceCandidate(data){assert.equal(data.candidate,'private-candidate');steps.push('candidate');}
      async createAnswer(){steps.push('answer');return {type:'answer',sdp:'private-answer'};}
      async setLocalDescription(){steps.push('local');}
      close(){}
    };
    await card.join();callback({event:'joined',role:'show',peer_id:'b'.repeat(32)});
    callback({event:'ready',call_id:'a'.repeat(32)});
    assert.deepEqual(logs,[['SHOW5_CALL_STAGE','ready_received']],'ready is visible before the event queue runs');
    await tick();assert.match(status,/Preparing camera and microphone/);
    assert.deepEqual(logs.at(-1),['SHOW5_CALL_STAGE','media_requested']);
    callback({event:'signal',kind:'candidate',data:{candidate:'private-candidate'}});
    callback({event:'signal',kind:'offer',data:{type:'offer',sdp:'private-sdp'}});
    await tick();assert.deepEqual(steps,[],'negotiation must wait for getUserMedia');
    capture.resolve({getTracks:()=>[{stop(){}}]});await card.events;
    assert.match(status,/Connecting audio and video/);
    assert.deepEqual(steps,['track','remote','candidate','answer','local','answer_sent']);
    assert.deepEqual(logs,[['SHOW5_CALL_STAGE','ready_received'],['SHOW5_CALL_STAGE','media_requested'],['SHOW5_CALL_STAGE','media_acquired'],['SHOW5_CALL_STAGE','rtc_created'],['SHOW5_CALL_STAGE','answer_sent']]);
    assert.equal(timers[0].delay,45000);
    card.pc.connectionState='connected';card.pc.onconnectionstatechange();
    assert.equal(card.phase,'connected');assert.ok(cleared.includes(1),'connected clears the bounded startup timer');
    assert.deepEqual(logs.at(-1),['SHOW5_CALL_STAGE','connected']);
    card.milestone('private-url');assert.equal(logs.length,6,'milestones are allowlisted');
    assert.ok(!JSON.stringify(logs).includes('private-'));
    card.localStop();sandbox.console=console;sandbox.setTimeout=setTimeout;sandbox.clearTimeout=clearTimeout;count++;
  }
  {
    const card=new (classes.get('show5-video-call-card'))();let attempts=0,status;
    card.epoch=1;card.isConnected=true;card.config={role:'show'};card.status=text=>status=text;
    const buttons={start:{},retry:{}};card.shadowRoot={getElementById:id=>buttons[id]||{srcObject:null}};
    const connection={connected:true,subscribeMessage:async()=>{attempts++;throw {code:'room_unavailable'};}};
    card.hass={connection};await tick();
    for(let i=0;i<100;i++)card.hass={connection,states:{counter:i}};
    await tick();assert.equal(attempts,1,'failed joins must latch across ordinary hass updates');
    assert.equal(card.joinFailed,true);assert.equal(buttons.retry.disabled,false);assert.match(status,/Retry room/);
    card.retryJoin();card.retryJoin();await tick();
    assert.equal(attempts,2,'manual retry grants exactly one attempt, including rapid double clicks');
    assert.equal(card.joinFailed,true);count++;
  }
  {
    const card=new (classes.get('show5-video-call-card'))(),listeners={},callbacks=[],options=[];let attempts=0,stopped=0,ends=0;
    card.epoch=1;card.isConnected=true;card.config={role:'caller'};card.status=()=>{};card.shadowRoot={getElementById:()=>({srcObject:null})};
    card.ws=async()=>{ends++;};
    const connection={connected:true,addEventListener:(name,cb)=>listeners[name]=cb,removeEventListener:name=>delete listeners[name],subscribeMessage:async(cb,msg,opts)=>{attempts++;callbacks.push(cb);options.push(opts);return ()=>{};}};
    card.hass={connection};await tick();callbacks[0]({event:'joined',role:'caller',peer_id:'a'.repeat(32)});
    assert.equal(card.canStart(),true);card.stream={getTracks:()=>[{stop:()=>stopped++}]};
    connection.connected=false;listeners.disconnected();
    assert.equal(card.peerId,null);assert.equal(card.unsubscribe,null);assert.equal(card.canStart(),false);assert.equal(stopped,1);assert.equal(ends,0,'disconnect must not queue an old End on a future socket');
    for(let i=0;i<10;i++)card.hass={connection};await tick();assert.equal(attempts,1);
    connection.connected=true;listeners.ready();await tick();assert.equal(attempts,2);
    assert.equal(card.canStart(),false,'socket readiness alone is not membership');
    callbacks[0]({event:'joined',role:'caller',peer_id:'a'.repeat(32)});assert.equal(card.peerId,null,'obsolete subscription callback is ignored');
    callbacks[1]({event:'joined',role:'caller',peer_id:'b'.repeat(32)});assert.equal(card.peerId,'b'.repeat(32));assert.equal(card.canStart(),true);
    assert.ok(options.every(option=>option.resubscribe===false),'the card owns reconnect attempts, not library auto-resubscription');
    card.isConnected=false;card.disconnectedCallback();await tick();assert.deepEqual(Object.keys(listeners),[]);count++;
  }
  {
    const card=new (classes.get('show5-video-call-card'))(),listeners={},old=deferred(),current=deferred();let attempts=0,callback,oldUnsubscribed=0;
    card.epoch=1;card.isConnected=true;card.config={role:'show'};card.status=()=>{};card.shadowRoot={getElementById:()=>({srcObject:null})};
    const connection={connected:true,addEventListener:(name,cb)=>listeners[name]=cb,subscribeMessage:cb=>{attempts++;if(attempts===1)return old.promise;callback=cb;return current.promise;}};
    card.hass={connection};connection.connected=false;listeners.disconnected();connection.connected=true;listeners.ready();
    old.resolve(()=>oldUnsubscribed++);await tick();
    assert.equal(oldUnsubscribed,0,'an old transport unsubscribe must not target reused command IDs after reconnect');
    assert.equal(card.joining,true,'old completion must not clear the new in-flight attempt');
    callback({event:'joined',role:'show',peer_id:'b'.repeat(32)});current.resolve(()=>{});await tick();
    assert.equal(card.peerId,'b'.repeat(32));assert.equal(card.joinFailed,false);assert.equal(card.joining,false);count++;
  }
  {
    const card=new (classes.get('show5-video-call-card'))(),listeners={},old=deferred();let attempts=0,callback;
    card.epoch=1;card.isConnected=true;card.config={role:'show'};card.status=()=>{};card.shadowRoot={getElementById:()=>({srcObject:null})};
    const connection={connected:true,addEventListener:(name,cb)=>listeners[name]=cb,subscribeMessage:cb=>{attempts++;if(attempts===1)return old.promise;callback=cb;return Promise.resolve(()=>{});}};
    card.hass={connection};connection.connected=false;listeners.disconnected();connection.connected=true;listeners.ready();await tick();
    callback({event:'joined',role:'show',peer_id:'b'.repeat(32)});old.reject({code:'room_unavailable'});await tick();
    assert.equal(card.joinFailed,false,'late failure from the old socket cannot latch the current membership');assert.equal(card.peerId,'b'.repeat(32));count++;
  }
  {
    const card=new (classes.get('show5-video-call-card'))(),old=deferred(),current=deferred();let attempts=0,oldUnsubscribed=0;
    card.epoch=1;card.isConnected=true;card.config={role:'show'};card.status=()=>{};card.shadowRoot={getElementById:()=>({srcObject:null})};
    const connection={connected:true,subscribeMessage:()=>++attempts===1?old.promise:current.promise};
    card.hass={connection};card.isConnected=false;card.disconnectedCallback();card.isConnected=true;card.connectedCallback();
    old.resolve(()=>oldUnsubscribed++);await tick();assert.equal(oldUnsubscribed,1,'late join on the same live socket must still unsubscribe after DOM replacement');
    current.resolve(()=>{});await tick();count++;
  }
  console.log(`${count} frontend cancellation/late-completion tests passed; no real media or HA calls`);
}
run().catch(error=>{console.error(error);process.exitCode=1;});
