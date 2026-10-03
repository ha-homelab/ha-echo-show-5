/* Private pilot: HA-authenticated WS only. No credentials or tokens in URLs. */
const TYPE = "show5_intercom/";
const styles = `:host{display:block}ha-card{display:block;padding:12px}h3{font-size:18px;margin:0 0 6px}button{margin:4px;padding:9px;font:inherit;border:1px solid var(--divider-color,#aaa);border-radius:8px;background:var(--card-background-color,#fff);color:var(--primary-text-color,#222)}button:disabled{opacity:.4}p{min-height:2em;margin:6px 0}.video-stage{position:relative;height:clamp(120px,40vh,240px);background:#111}.video-stage video{width:100%;height:100%;object-fit:contain}.video-stage video.local{position:absolute;right:6px;bottom:6px;width:25%;height:30%;background:#111}.row{display:flex;flex-wrap:wrap}`;
function base64(bytes) {
  let s = "";
  for (let i=0;i<bytes.length;i+=8192) s += String.fromCharCode(...bytes.subarray(i,i+8192));
  return btoa(s);
}
function pcmBuffer(value) {
  const s=atob(value), data=new DataView(new ArrayBuffer(s.length));
  for(let i=0;i<s.length;i++) data.setUint8(i,s.charCodeAt(i));
  const samples=new Float32Array(s.length/2);
  for(let i=0;i<samples.length;i++) samples[i]=data.getInt16(i*2,true)/32768;
  return samples;
}

class ShowIntercomCard extends HTMLElement {
  setConfig(config) { this.config=config; if(!this.shadowRoot) this.attachShadow({mode:"open"}); this.render(); }
  set hass(value) { this._hass=value; }
  getCardSize(){return 3;}
  connectedCallback(){this.epoch=(this.epoch||0)+1; this.onHidden=()=>{if(document.hidden)this.cancel();}; document.addEventListener("visibilitychange",this.onHidden);}
  disconnectedCallback(){document.removeEventListener("visibilitychange",this.onHidden); this.cancel();}
  render(){
    this.shadowRoot.innerHTML=`<style>${styles}</style><ha-card><h3>Show intercom</h3><p id="status">Record a short message, then send it to the Show.</p><div class="row"><button id="record">Record · max 10 s</button><button id="send" disabled>Send</button><button id="cancel" disabled>Cancel recording</button><button id="listen">Listen · 5 s</button><button id="check">Status</button><button id="recover">Recover (admin)</button></div></ha-card>`;
    for(const [id,fn] of Object.entries({record:()=>this.record(),send:()=>this.send(),cancel:()=>this.cancel(),listen:()=>this.listen(),check:()=>this.check(),recover:()=>this.recover()})) this.shadowRoot.getElementById(id).onclick=fn;
  }
  status(text){this.shadowRoot.getElementById("status").textContent=text;}
  controls(busy,recording=false){for(const id of ["record","listen"])this.shadowRoot.getElementById(id).disabled=busy;this.shadowRoot.getElementById("send").disabled=!recording;this.shadowRoot.getElementById("cancel").disabled=!recording;}
  ws(command,data={}){return this._hass.callWS({type:TYPE+command,...data});}
  async check(){try{const s=await this.ws("status");this.status(s.needs_recovery?"Restoration failed. Check the device, then Recover as an administrator.":s.recovery_pending?"Startup restoration is running.":s.active?"The Show is in a session.":"Idle. Listening: "+(s.listen_enabled?"enabled":"disabled")+"; video calls: "+(s.video_enabled?"enabled":"disabled")+".");}catch(error){this.status("Intercom status unavailable.");}}
  async recover(){try{await this.ws("recover");await this.check();}catch(error){this.status("Recovery unavailable or failed; requires administrator access and no active session.");}}
  stopCapture(){clearTimeout(this.limit);if(this.processor){this.processor.onaudioprocess=null;this.processor.disconnect();this.processor=null;}this.source?.disconnect();this.gain?.disconnect();this.stream?.getTracks().forEach(t=>t.stop());this.stream=null;const context=this.context;this.context=null;context?.close().catch(()=>{});}
  async cancel(){
    this.epoch++;this.stopCapture();this.frames=[];const session=this.session;this.session=null;
    let restored=true;if(session){try{await this.ws("end",{session});}catch(error){restored=false;}}
    this.controls(false);this.status(restored?"Idle. No new message will be sent.":"Capture stopped locally; Show restoration is unconfirmed. Check Status / Recover.");
  }
  async record(){
    if(this.session||this.starting)return;this.starting=true;const epoch=++this.epoch;this.controls(true);this.status("Allow this browser's microphone. Nothing is saved to disk.");
    try{
      if(!isSecureContext)throw new Error("HTTPS required");
      const stream=await navigator.mediaDevices.getUserMedia({audio:{channelCount:1,echoCancellation:true,noiseSuppression:true,autoGainControl:true}});
      if(epoch!==this.epoch){stream.getTracks().forEach(t=>t.stop());return;}
      this.stream=stream;
      const acquired=await this.ws("begin",{mode:"talk"});
      if(epoch!==this.epoch){stream.getTracks().forEach(t=>t.stop());await this.ws("end",{session:acquired.session});return;}
      this.session=acquired.session;
      this.context=new AudioContext();await this.context.resume();this.rate=this.context.sampleRate;this.frames=[];this.count=0;
      this.source=this.context.createMediaStreamSource(stream);this.processor=this.context.createScriptProcessor(4096,1,1);this.gain=this.context.createGain();this.gain.gain.value=0;
      this.processor.onaudioprocess=event=>{
        const input=event.inputBuffer.getChannelData(0),remaining=this.rate*10-this.count;
        if(remaining>0){const frame=input.slice(0,remaining);this.frames.push(frame);this.count+=frame.length;}
        if(this.count>=this.rate*10)this.send();
      };
      this.source.connect(this.processor);this.processor.connect(this.gain);this.gain.connect(this.context.destination);
      this.controls(true,true);this.status("Recording. Send stops capture; ten seconds sends automatically.");this.limit=setTimeout(()=>this.send(),10000);
    }catch(error){await this.cancel();this.status("Could not start. Check microphone permission, HA status and the Show lease.");}
    finally{this.starting=false;}
  }
  async send(){
    if(!this.session||this.sending)return;this.sending=true;const epoch=this.epoch,session=this.session,rate=this.rate,frames=this.frames||[],count=this.count||0;
    let accepted=false,restored=false;
    this.stopCapture();this.controls(true);this.status("Sending. Already accepted audio may play for up to ten seconds.");
    try{
      if(count<rate*.02)throw new Error("Message too short");
      const target=Math.min(441000,Math.floor(count*44100/rate));
      const offline=new OfflineAudioContext(1,target,44100),input=offline.createBuffer(1,count,rate);
      let offset=0;for(const frame of frames){input.copyToChannel(frame,0,offset);offset+=frame.length;}
      const node=offline.createBufferSource();node.buffer=input;node.connect(offline.destination);node.start();
      const rendered=await offline.startRendering(),samples=rendered.getChannelData(0),bytes=new Uint8Array(target*2),view=new DataView(bytes.buffer);
      for(let i=0;i<samples.length;i++){const s=Math.max(-1,Math.min(1,samples[i]));view.setInt16(i*2,Math.round(s*(s<0?32768:32767)),true);}
      if(epoch!==this.epoch)return;
      await this.ws("upload",{session,pcm:base64(bytes)});accepted=true;
    }catch(error){if(epoch===this.epoch)this.status("Message failed. Check the Show before retrying.");}
    finally{this.frames=[];this.session=null;this.sending=false;try{await this.ws("end",{session});restored=true;}catch(error){}this.controls(false);if(epoch===this.epoch){if(!restored)this.status("Show restoration is unconfirmed. Check Status / Recover before another session.");else if(accepted)this.status("Message accepted; prior VACA mute state restored. Audibility needs a person to confirm.");}}
  }
  async listen(){
    if(this.session||this.starting)return;this.starting=true;this.controls(true);this.status("Listening for five seconds. This mode must be enabled by the operator.");
    const epoch=++this.epoch;let session;
    try{
      const acquired=await this.ws("begin",{mode:"listen"});session=acquired.session;this.session=session;
      if(epoch!==this.epoch)return;
      const result=await this.ws("listen",{session,seconds:5});
      if(epoch!==this.epoch)return;
      const samples=pcmBuffer(result.pcm),context=new AudioContext({sampleRate:44100});await context.resume();
      const buffer=context.createBuffer(1,samples.length,44100);buffer.copyToChannel(samples,0);const source=context.createBufferSource();source.buffer=buffer;source.connect(context.destination);source.onended=()=>context.close();source.start();
      this.status("Playing five seconds from the Show; confirming restoration…");
    }catch(error){if(epoch===this.epoch)this.status("Listening unavailable or failed; it requires verified Android microphone handoff.");}
    finally{let restored=true;if(session){try{await this.ws("end",{session});}catch(error){restored=false;}}this.session=null;this.starting=false;this.controls(false);if(epoch===this.epoch&&session)this.status(restored?"Listening ended; prior VACA mute state restored.":"Show restoration is unconfirmed. Check Status / Recover.");}
  }
}
if(!customElements.get("show5-intercom-card"))customElements.define("show5-intercom-card",ShowIntercomCard);

const callStages = Object.freeze({media:"camera/microphone",rtc_setup:"media setup",offer:"offer creation",answer:"answer creation",local_description:"local negotiation",remote_description:"remote negotiation",ice_candidate:"network candidate",signal:"signaling",connection:"connection",event:"call handling",command:"call request",hangup:"restoration request"});
const callErrorCodes = new Set(["NotAllowedError","NotFoundError","NotReadableError","OverconstrainedError","AbortError","SecurityError","InvalidStateError","OperationError","NotSupportedError","TypeError","TimeoutError","NetworkError","intercom_failed","room_unavailable","unauthorized","invalid_format","connection_failed","connection_timeout","connection_disconnected"]);
const callMilestones = new Set(["ready_received","media_requested","media_acquired","rtc_created","offer_sent","answer_sent","connected"]);
class ShowVideoCallCard extends HTMLElement {
  setConfig(config){if(!["caller","show"].includes(config.role))throw new Error("Set role: caller or show");this.config=config;if(!this.shadowRoot)this.attachShadow({mode:"open"});this.render();}
  set hass(value){this._hass=value;if(this.isConnected){this.watchConnection();this.join();}}
  getCardSize(){return 5;}
  connectedCallback(){this.epoch=(this.epoch||0)+1;this.onHidden=()=>{if(document.hidden)this.hangup();};document.addEventListener("visibilitychange",this.onHidden);if(this._hass){this.watchConnection();this.join();}}
  disconnectedCallback(){document.removeEventListener("visibilitychange",this.onHidden);this.unwatchConnection();this.membershipEpoch=(this.membershipEpoch||0)+1;this.hangup();if(this.unsubscribe)Promise.resolve(this.unsubscribe()).catch(()=>{});this.unsubscribe=null;this.peerId=null;this.joining=false;this.setPhase("joining");}
  render(){this.shadowRoot.innerHTML=`<style>${styles}</style><ha-card><h3>Private Show video call</h3><p id="status">Connecting to the private HA room…</p><div class="video-stage"><video id="remote" autoplay playsinline></video><video class="local" id="local" autoplay playsinline muted></video></div><div class="row"><button id="start" disabled>${this.config.role==="show"?"Answer":"Call Show"}</button><button id="end">End</button><button id="audio">Play received audio</button><button id="retry" disabled>Retry room</button></div></ha-card>`;this.shadowRoot.getElementById("start").onclick=()=>this.command(this.config.role==="show"?"accept":"call");this.shadowRoot.getElementById("end").onclick=()=>this.hangup();this.shadowRoot.getElementById("audio").onclick=()=>this.shadowRoot.getElementById("remote").play().catch(()=>{});this.shadowRoot.getElementById("retry").onclick=()=>this.retryJoin();this.setPhase(this.phase||"joining");}
  status(text){this.shadowRoot.getElementById("status").textContent=text;}
  ws(command,data={}){return this._hass.callWS({type:TYPE+command,...data});}
  roomWS(command,data={},peerId=this.peerId){if(!/^[0-9a-f]{32}$/.test(peerId||""))return Promise.reject({code:"room_unavailable"});return this.ws(command,{...data,peer_id:peerId});}
  canStart(){return this._hass?.connection?.connected!==false&&/^[0-9a-f]{32}$/.test(this.peerId||"")&&(this.config?.role==="show"?this.phase==="incoming":this.phase==="idle");}
  setPhase(phase){this.phase=phase;const button=this.shadowRoot?.getElementById("start");if(button)button.disabled=!this.canStart();const retry=this.shadowRoot?.getElementById("retry");if(retry)retry.disabled=!this.joinFailed||this.joining||this._hass?.connection?.connected===false;}
  unwatchConnection(){const binding=this.connectionBinding;if(binding){binding.connection.removeEventListener?.("disconnected",binding.disconnected);binding.connection.removeEventListener?.("ready",binding.ready);this.connectionBinding=null;}}
  resetMembership(){this.membershipEpoch=(this.membershipEpoch||0)+1;this.joining=false;this.peerId=null;const unsubscribe=this.unsubscribe;this.unsubscribe=null;this.localStop();if(unsubscribe)Promise.resolve(unsubscribe()).catch(()=>{});this.setPhase("joining");}
  watchConnection(){
    const connection=this._hass?.connection;if(!connection||this.connectionBinding?.connection===connection)return;
    if(this.connectionBinding){this.unwatchConnection();this.resetMembership();}
    if(this.transportConnection!==connection){this.transportConnection=connection;this.transportEpoch=(this.transportEpoch||0)+1;}this.joinFailed=false;
    const binding={connection};this.connectionBinding=binding;
    binding.disconnected=()=>{if(this.connectionBinding!==binding)return;this.transportEpoch++;this.resetMembership();this.joinFailed=false;this.status("HA disconnected. Local media stopped; waiting to rejoin the room.");};
    binding.ready=()=>{if(this.connectionBinding!==binding||!this.isConnected)return;this.joinFailed=false;this.join();};
    connection.addEventListener?.("disconnected",binding.disconnected);connection.addEventListener?.("ready",binding.ready);
  }
  retryJoin(){if(!this.joinFailed||this.joining||!this.isConnected||this._hass?.connection?.connected===false)return;this.joinFailed=false;this.join();}
  milestone(name){if(callMilestones.has(name))console.info("SHOW5_CALL_STAGE",name);}
  failure(stage,error){
    if(this.lastFailure)return;
    stage=Object.hasOwn(callStages,stage)?stage:"event";
    const code=callErrorCodes.has(error?.name)?error.name:callErrorCodes.has(error?.code)?error.code:"UnknownError";
    this.lastFailure={stage,code};
    // Never log the exception object/message, media, SDP, candidates or URLs.
    console.warn("SHOW5_CALL_FAILURE",stage,code);
  }
  endStatus(text){const f=this.lastFailure;this.status(f?`Call failed at ${callStages[f.stage]} (${f.code}). ${text}`:text);}
  async step(stage,operation,epoch=this.epoch){
    try{const result=await operation();if(epoch!==this.epoch)throw new Error("Call cancelled");return result;}
    catch(error){if(epoch===this.epoch)this.failure(stage,error);throw error;}
  }
  async failAndHangup(stage,error,epoch=this.epoch){if(epoch!==this.epoch)return;this.failure(stage,error);await this.hangup();}
  async join(){
    if(this.joining||this.unsubscribe||this.joinFailed||!this.config||!this.isConnected||!this._hass?.connection||this._hass.connection.connected===false)return;
    this.watchConnection();const connection=this._hass.connection,transportEpoch=this.transportEpoch;
    this.joining=true;const membershipEpoch=this.membershipEpoch=(this.membershipEpoch||0)+1;let receivedCallEvent=false;
    this.setPhase("joining");
    try{
      this.events=Promise.resolve();
      // home-assistant-js-websocket passes message.event, not the WS envelope.
      const unsubscribe=await connection.subscribeMessage(event=>{
        if(membershipEpoch!==this.membershipEpoch||!this.isConnected)return;
        if(event.event==="joined"){
          if(event.role===this.config.role&&/^[0-9a-f]{32}$/.test(event.peer_id||"")){this.peerId=event.peer_id;this.setPhase("idle");if(!receivedCallEvent)this.status("Ready. Calls require an explicit answer; maximum two minutes.");}
          return;
        }
        if(["incoming","ready","signal","ended","restored"].includes(event.event))receivedCallEvent=true;
        if(event.event==="ready")this.milestone("ready_received");
        if(event.event==="ended"){this.localStop();this.endStatus("Call ended; restoring the Show…");this.events=Promise.resolve();return;}
        if(event.event==="restored"){this.setPhase("idle");this.endStatus("Restoration command completed.");return;}
        const eventEpoch=this.epoch;
        this.events=this.events.then(()=>{if(eventEpoch===this.epoch)return this.event(event);}).catch(error=>this.failAndHangup("event",error,eventEpoch));
      },{type:TYPE+"room_join",role:this.config.role},{resubscribe:false});
      if(membershipEpoch!==this.membershipEpoch||!this.isConnected){if((transportEpoch===this.transportEpoch||connection!==this._hass?.connection)&&connection.connected!==false)Promise.resolve(unsubscribe()).catch(()=>{});return;}
      this.unsubscribe=unsubscribe;
      // The backend can ring immediately after registering this subscription,
      // before the async subscribeMessage promise has finished resolving.
      if(!receivedCallEvent&&!this.peerId)this.status("Waiting for room membership confirmation…");
    }catch(error){if(membershipEpoch!==this.membershipEpoch||!this.isConnected)return;this.joinFailed=true;this.peerId=null;this.setPhase("unavailable");this.status("Video room is disabled or occupied. Check the device, then use Retry room.");}
    finally{if(membershipEpoch===this.membershipEpoch){this.joining=false;this.setPhase(this.phase);}}
  }
  async command(action){if(!this.canStart())return;const peerId=this.peerId,membershipEpoch=this.membershipEpoch;this.lastFailure=null;this.setPhase(action==="call"?"ringing":"answering");this.status(action==="call"?"Opening the receiver on the Show…":"Preparing the Show camera and microphone…");try{await this.roomWS("room_action",{action},peerId);if(peerId!==this.peerId||membershipEpoch!==this.membershipEpoch)return;if(action==="call"&&this.phase==="ringing")this.status("Waiting for an answer on the Show…");}catch(error){if(peerId!==this.peerId||membershipEpoch!==this.membershipEpoch)return;this.setPhase("idle");this.failure("command",error);this.endStatus("Check both room endpoints.");}}
  localStop(){this.epoch++;this.setPhase("ending");this.callId=null;clearTimeout(this.connectTimer);clearTimeout(this.disconnectedTimer);this.stream?.getTracks().forEach(t=>t.stop());this.stream=null;if(this.pc){this.pc.onicecandidate=null;this.pc.onconnectionstatechange=null;this.pc.ontrack=null;this.pc.close();this.pc=null;}for(const id of ["remote","local"])this.shadowRoot.getElementById(id).srcObject=null;this.candidates=[];}
  async hangup(){const peerId=this.peerId,membershipEpoch=this.membershipEpoch;this.localStop();if(!peerId){this.endStatus("Call ended locally; no room membership.");return;}this.endStatus("Call ended; restoring the Show…");try{await this.roomWS("room_action",{action:"end"},peerId);if(peerId!==this.peerId||membershipEpoch!==this.membershipEpoch)return;this.setPhase("idle");this.endStatus("Restoration command completed.");}catch(error){if(peerId!==this.peerId||membershipEpoch!==this.membershipEpoch)return;this.failure("hangup",error);this.endStatus("Restoration is unconfirmed. Check Status / Recover.");}}
  async media(){
    const epoch=this.epoch;let stream;
    this.milestone("media_requested");
    try{stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:{facingMode:"user",width:{ideal:640,max:640},height:{ideal:480,max:480},frameRate:{ideal:15,max:15}}});}
    catch(error){if(epoch===this.epoch)this.failure("media",error);throw error;}
    if(epoch!==this.epoch){stream.getTracks().forEach(t=>t.stop());throw new Error("Call cancelled");}
    this.milestone("media_acquired");this.status("Connecting audio and video…");
    this.stream=stream;this.shadowRoot.getElementById("local").srcObject=stream;this.candidates=[];
    let pc;
    try{pc=this.pc=new RTCPeerConnection({iceServers:[]});stream.getTracks().forEach(track=>pc.addTrack(track,stream));}
    catch(error){this.failure("rtc_setup",error);throw error;}
    this.milestone("rtc_created");
    pc.ontrack=event=>{this.shadowRoot.getElementById("remote").srcObject=event.streams[0];this.shadowRoot.getElementById("remote").play().catch(()=>this.status("Tap Play received audio to enable playback."));};
    pc.onicecandidate=event=>{if(event.candidate&&epoch===this.epoch)this.step("signal",()=>this.roomWS("signal",{call_id:this.callId,kind:"candidate",data:event.candidate.toJSON()}),epoch).catch(error=>this.failAndHangup("signal",error,epoch));};
    pc.onconnectionstatechange=()=>{if(epoch!==this.epoch)return;if(pc.connectionState==="connected"){this.milestone("connected");this.setPhase("connected");clearTimeout(this.connectTimer);clearTimeout(this.disconnectedTimer);this.status("Connected. End returns the Show to its dashboard.");}else if(pc.connectionState==="failed")this.failAndHangup("connection",{code:"connection_failed"},epoch);else if(pc.connectionState==="disconnected"){clearTimeout(this.disconnectedTimer);this.disconnectedTimer=setTimeout(()=>this.failAndHangup("connection",{code:"connection_disconnected"},epoch),8000);}};
    this.connectTimer=setTimeout(()=>this.failAndHangup("connection",{code:"connection_timeout"},epoch),45000);return pc;
  }
  async event(event){
    const epoch=this.epoch;
    if(event.event==="incoming"){this.lastFailure=null;this.setPhase("incoming");this.status("Incoming private call. Tap Answer to release camera/mic to this call.");return;}
    if(event.event==="ended"){this.localStop();this.endStatus("Call ended. Camera and voice assistant are being restored.");return;}
    if(event.event==="ready"){
      this.setPhase("connecting");this.status("Preparing camera and microphone…");
      this.callId=event.call_id;const pc=await this.media();
      if(this.config.role==="caller"){const offer=await this.step("offer",()=>pc.createOffer(),epoch);await this.step("local_description",()=>pc.setLocalDescription(offer),epoch);await this.step("signal",()=>this.roomWS("signal",{call_id:this.callId,kind:"offer",data:{type:offer.type,sdp:offer.sdp}}),epoch);this.milestone("offer_sent");}return;
    }
    if(event.event!=="signal"||!this.pc)return;
    if(event.kind==="candidate"){if(this.pc.remoteDescription)await this.step("ice_candidate",()=>this.pc.addIceCandidate(event.data),epoch);else this.candidates.push(event.data);return;}
    await this.step("remote_description",()=>this.pc.setRemoteDescription(event.data),epoch);for(const candidate of this.candidates)await this.step("ice_candidate",()=>this.pc.addIceCandidate(candidate),epoch);this.candidates=[];
    if(event.kind==="offer"){const answer=await this.step("answer",()=>this.pc.createAnswer(),epoch);await this.step("local_description",()=>this.pc.setLocalDescription(answer),epoch);await this.step("signal",()=>this.roomWS("signal",{call_id:this.callId,kind:"answer",data:{type:answer.type,sdp:answer.sdp}}),epoch);this.milestone("answer_sent");}
  }
}
if(!customElements.get("show5-video-call-card"))customElements.define("show5-video-call-card",ShowVideoCallCard);

// Opt-in, version-scoped recovery of Companion's native loading overlay.
// This repeats the official frontend event only after the real dashboard is ready.
const readinessDocuments = new WeakSet();
class ShowReadinessCard extends HTMLElement {
  setConfig(config){
    this.enabled=config.enabled===true;
    if(!this.shadowRoot)this.attachShadow({mode:"open"});
    this.shadowRoot.innerHTML="<style>:host{display:none!important;width:0;height:0;margin:0;padding:0}</style>";
    this.stop();this.start();
  }
  set hass(value){this._hass=value;}
  getCardSize(){return 0;}
  connectedCallback(){this.start();}
  disconnectedCallback(){this.stop();}
  start(){
    if(!this.enabled||!this.isConnected||this.started||readinessDocuments.has(document))return;
    this.started=true;const epoch=this.epoch=(this.epoch||0)+1;
    this.deadline=setTimeout(()=>this.stop(),30000);
    this.tryReady(epoch);
  }
  stop(){
    this.epoch=(this.epoch||0)+1;
    this.started=false;
    clearTimeout(this.timer);clearTimeout(this.deadline);
    if(this.frame1!==undefined)cancelAnimationFrame(this.frame1);
    if(this.frame2!==undefined)cancelAnimationFrame(this.frame2);
    this.frame1=this.frame2=undefined;
  }
  readyView(epoch){
    const hass=this._hass;
    if(epoch!==this.epoch||!this.enabled||!this.isConnected||window.top!==window||
       readinessDocuments.has(document)||!/^\/echo-show(?:\/|$)/.test(window.location.pathname)||
       hass?.connection?.connected!==true||!hass.user||!hass.config||!hass.states||
       typeof hass.auth?.external?.fireMessage!=="function"||document.getElementById("ha-launch-screen"))return null;
    // Walk the composed tree: the helper itself is intentionally zero-size.
    for(let node=this.parentElement||this.getRootNode()?.host;node;node=node.parentElement||node.getRootNode?.()?.host){
      if(/^hui-(view|masonry-view|sections-view|panel-view)$/.test(node.localName)&&
         node.isConnected&&node.hasUpdated===true&&!node.isUpdatePending&&
         Array.from(node.getClientRects()).some(rect=>rect.width>0&&rect.height>0))return node;
    }
    return null;
  }
  tryReady(epoch){
    if(epoch!==this.epoch||!this.isConnected)return;
    if(readinessDocuments.has(document)){this.stop();return;}
    const view=this.readyView(epoch);
    if(!view){this.timer=setTimeout(()=>this.tryReady(epoch),250);return;}
    this.frame1=requestAnimationFrame(()=>{
      this.frame1=undefined;
      this.frame2=requestAnimationFrame(()=>{
        this.frame2=undefined;
        if(this.readyView(epoch)!==view){this.tryReady(epoch);return;}
        try{
          this._hass.auth.external.fireMessage({type:"frontend/loaded"});
          readinessDocuments.add(document);
          this.stop();
        }catch(error){this.timer=setTimeout(()=>this.tryReady(epoch),250);}
      });
    });
  }
}
if(!customElements.get("show5-readiness-card"))customElements.define("show5-readiness-card",ShowReadinessCard);
window.customCards=window.customCards||[];
for(const card of [{type:"show5-intercom-card",name:"Private Show intercom",description:"HA-authenticated bounded talkback and optional listening"},{type:"show5-video-call-card",name:"Private Show video call",description:"Private HA-signaled call with explicit answer; no configured STUN/TURN"}])if(!window.customCards.some(existing=>existing.type===card.type))window.customCards.push(card);
