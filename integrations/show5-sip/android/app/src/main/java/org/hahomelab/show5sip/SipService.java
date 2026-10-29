/* SPDX-License-Identifier: AGPL-3.0-only */
package org.hahomelab.show5sip;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.*;
import android.util.AtomicFile;
import org.json.JSONObject;
import org.linphone.core.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;

/** One registered endpoint, one call and one local audio lease. Never auto-answers. */
public final class SipService extends Service implements AudioLeaseClient.Owner {
    static final String CHANNEL = "show-phone", INCOMING = "show-phone-incoming";
    // Linphone CoreService owns ID 1; incoming call notifications own ID 2.
    private static final int STATUS_NOTIFICATION_ID = 3;
    static volatile String statusJson = "{\"schema\":1,\"configured\":false,\"config_sha256\":null,\"config_error\":null,\"endpoint_id\":null,\"registration\":\"unconfigured\",\"state\":\"idle\",\"call_id\":null,\"contact_id\":null,\"lease_held\":false,\"last_error\":null,\"last_command_id\":null,\"last_command_result\":null,\"last_command_error\":null}";
    static SipService instance;
    static final AudioDiagnostics diagnostics = new AudioDiagnostics();
    private final Handler handler = new Handler(Looper.getMainLooper());
    private AudioLeaseClient lease;
    private Core core;
    private Call call;
    private SipConfig config;
    private String state = "idle", registration = "unconfigured", callId, contactId, pendingAction;
    private String lastError, commandId, commandResult, commandError, configHash, configError;
    private boolean closing, stopRequested;
    private final LinkedHashMap<String, String> commands = new LinkedHashMap<>();
    private final Runnable callLimit = () -> endCall("call_limit");
    private final Runnable closeDeadline = () -> {
        // Core.stop synchronously closes SDK media before any microphone restoration.
        stopCore(); call = null; pendingAction = null; finishMedia();
    };
    private final CoreListenerStub listener = new CoreListenerStub() {
        @Override public void onAccountRegistrationStateChanged(Core c, Account account, RegistrationState value, String message) {
            handler.post(() -> {
                if (closing || !isCurrentCore(c)) return;
                registration = value == RegistrationState.Ok ? "registered" : value == RegistrationState.Progress ? "registering" : value == RegistrationState.Failed ? "failed" : "unconfigured";
                if (value == RegistrationState.Failed) lastError = "registration_failed";
                publish();
            });
        }
        @Override public void onCallStateChanged(Core c, Call changed, Call.State value, String message) {
            // Defer renegotiation before leaving the SDK callback. Core.stop must
            // never be reached inside a Liblinphone event notification.
            if (value == Call.State.UpdatedByRemote) changed.deferUpdate();
            handler.post(() -> handleCallState(c, changed, value));
        }
        @Override public void onCallStatsUpdated(Core c, Call changed, CallStats stats) {
            // Copy only scalar audio metadata while the SDK-owned callback object is valid.
            if (!closing && isCurrentCore(c) && sameCall(changed)
                && stats.getType() == StreamType.Audio && !"ending".equals(state))
                recordAudio(changed, stats);
        }
    };
    private boolean isCurrentCore(Core candidate) {
        return core != null && candidate.getNativePointer() == core.getNativePointer();
    }
    private boolean sameCall(Call candidate) {
        return candidate != null && call != null && candidate.getNativePointer() == call.getNativePointer();
    }
    private void recordAudio(Call owned) {
        try { if (owned != null) recordAudio(owned, owned.getAudioStats()); }
        catch (RuntimeException ignored) { /* A diagnostic must never block hangup. */ }
    }
    private void recordAudio(Call owned, CallStats stats) {
        if (!sameCall(owned) || callId == null || stats == null) return;
        try {
            PayloadType payload = owned.getCurrentParams().getUsedAudioPayloadType();
            IceState ice = stats.getIceState();
            diagnostics.update(callId, payload == null ? null : payload.getMimeType(),
                payload == null ? 0 : payload.getClockRate(), payload == null ? 0 : payload.getChannels(),
                stats.getUploadBandwidth(), stats.getDownloadBandwidth(), ice == null ? null : ice.name(), SystemClock.elapsedRealtime());
        } catch (RuntimeException ignored) {
            // Missing native statistics are not zero traffic and never interrupt a call.
        }
    }
    private void handleCallState(Core c, Call changed, Call.State value) {
            if (closing || !isCurrentCore(c)) return;
            if (value == Call.State.IncomingReceived) {
                if (callId != null || lease.hasToken() || stopRequested) { changed.decline(Reason.Busy); return; }
                call = changed; callId = UUID.randomUUID().toString(); contactId = null;
                diagnostics.begin(callId);
                state = "preparing"; pendingAction = "ring"; lastError = null;
                if (config != null) for (SipConfig.Contact entry : config.contacts.values()) {
                    Address expected = Factory.instance().createAddress(entry.address);
                    if (expected != null && expected.weakEqual(changed.getRemoteAddress())) { contactId = entry.id; break; }
                }
                handler.removeCallbacks(callLimit); handler.postDelayed(callLimit, 30000);
                publish(); lease.acquire(); return;
            }
            // Wrappers may differ across JNI callbacks; compare their native call identity.
            if (call == null || changed.getNativePointer() != call.getNativePointer()) return;
            if (value == Call.State.UpdatedByRemote) {
                CallParams params = c.createCallParams(changed);
                if (params == null) { endCall("call_update_failed"); return; }
                params.setVideoEnabled(false);
                if (changed.acceptUpdate(params) != 0) endCall("call_update_failed");
                return;
            }
            if (value == Call.State.StreamsRunning) {
                if (!lease.isHeld()) { endCall("media_without_lease"); return; }
                state = "active"; publish();
            } else if (value == Call.State.OutgoingProgress || value == Call.State.OutgoingRinging || value == Call.State.OutgoingEarlyMedia) {
                state = "dialing"; publish();
            } else if (value == Call.State.End || value == Call.State.Error) {
                getSystemService(NotificationManager.class).cancel(2);
                recordAudio(changed); diagnostics.end(callId);
                if (value == Call.State.Error) lastError = "call_failed";
                pendingAction = null; state = "ending";
                handler.removeCallbacks(callLimit); handler.removeCallbacks(closeDeadline);
                handler.postDelayed(closeDeadline, 10000); publish();
            } else if (value == Call.State.Released) {
                call = null; handler.post(SipService.this::finishMedia);
            }
    }
    @Override public void onCreate() {
        super.onCreate(); instance = this;
        NotificationManager manager = getSystemService(NotificationManager.class);
        manager.createNotificationChannel(new NotificationChannel(CHANNEL, "Phone status", NotificationManager.IMPORTANCE_LOW));
        manager.createNotificationChannel(new NotificationChannel(INCOMING, "Incoming phone calls", NotificationManager.IMPORTANCE_HIGH));
        startForeground(STATUS_NOTIFICATION_ID, notification("Phone starting"));
        lease = new AudioLeaseClient(this, handler, this);
        loadConfig();
        if (lease.hasToken()) { state = "ending"; lease.recover(); }
        else initializeCore();
        publish();
    }
    @Override public IBinder onBind(Intent intent) { return null; }
    @Override public int onStartCommand(Intent intent, int flags, int startId) {
        if (intent != null && intent.hasExtra("command")) handleCommand(intent);
        return START_STICKY;
    }
    private void loadConfig() {
        try {
            byte[] raw = new AtomicFile(getFileStreamPath("provision.json")).readFully();
            config = new SipConfig(new String(raw, StandardCharsets.UTF_8)); configHash = sha256(raw); configError = null;
        } catch (FileNotFoundException error) { config = null; configHash = null; }
        catch (Exception error) { config = null; configHash = null; configError = "invalid_config"; }
    }
    private void initializeCore() {
        if (core != null || config == null || lease.hasToken() || closing || stopRequested
            || !getSharedPreferences("phone", 0).getBoolean("enabled", true)) return;
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            state = "error"; lastError = "microphone_permission_required"; publish(); return;
        }
        try {
            Factory.instance().setDebugMode(false, "ShowPhone");
            core = Factory.instance().createCore(getFileStreamPath("linphonerc").getPath(), null, getApplicationContext());
            core.addListener(listener);
            core.setMaxCalls(1); core.setIncTimeout(30); core.setInCallTimeout(config.maxCallSeconds);
            VideoActivationPolicy video = Factory.instance().createVideoActivationPolicy();
            video.setAutomaticallyAccept(false); video.setAutomaticallyInitiate(false); core.setVideoActivationPolicy(video);
            core.setVideoCaptureEnabled(false); core.setVideoDisplayEnabled(false); core.setVideoPreviewEnabled(false);
            core.setNativeRingingEnabled(false); core.setRing(null); core.setRingback(null);
            core.setEchoCancellationEnabled(true); core.setMicEnabled(true);
            core.setUseRfc2833ForDtmf(true); core.setUseInfoForDtmf(false);
            List<PayloadType> ordered = new ArrayList<>();
            PayloadType[] all = core.getAudioPayloadTypes();
            for (PayloadType codec : all) codec.enable(false);
            for (String name : new String[]{"G722", "PCMU", "PCMA"}) for (PayloadType codec : all)
                if (name.equalsIgnoreCase(codec.getMimeType()) && codec.getChannels() == 1) { codec.enable(true); ordered.add(codec); }
            if (ordered.isEmpty()) throw new IllegalStateException("no_audio_codec");
            core.setAudioPayloadTypes(ordered.toArray(new PayloadType[0]));
            core.clearAccounts(); core.clearAllAuthInfo();
            Address identity = Factory.instance().createAddress("sip:" + config.username + "@" + config.domain);
            Address server = Factory.instance().createAddress("sip:" + config.domain);
            if (identity == null || server == null) throw new IllegalArgumentException("invalid_address");
            identity.setDisplayName(config.displayName);
            TransportType transport = config.transport.equals("tls") ? TransportType.Tls : config.transport.equals("udp") ? TransportType.Udp : TransportType.Tcp;
            server.setTransport(transport);
            AccountParams params = core.createAccountParams();
            params.setIdentityAddress(identity); params.setServerAddress(server); params.setTransport(transport);
            params.setRegisterEnabled(true); params.setExpires(300);
            params.setPushNotificationAllowed(false); params.setRemotePushNotificationAllowed(false);
            core.addAuthInfo(Factory.instance().createAuthInfo(config.username, null, config.password, null, null, identity.getDomain()));
            Account account = core.createAccount(params); core.addAccount(account); core.setDefaultAccount(account);
            if (core.start() != 0) throw new IllegalStateException("core_start_failed");
            for (AudioDevice device : core.getAudioDevices()) if (device.getType() == AudioDevice.Type.Speaker)
                core.setDefaultOutputAudioDevice(device);
            registration = "registering"; state = "idle"; lastError = null;
        } catch (Exception error) { stopCore(); state = "error"; lastError = "sdk_start_failed"; }
        publish();
    }
    private void handleCommand(Intent intent) {
        String id = intent.getStringExtra("request_id"), action = intent.getStringExtra("command");
        if (id == null || !id.matches("[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}")) return;
        if (commands.containsKey(id)) return; // A delayed replay must never start another call.
        commandId = id; commandResult = "rejected"; commandError = "invalid_command";
        if ("start".equals(action)) {
            stopRequested = false; getSharedPreferences("phone", 0).edit().putBoolean("enabled", true).apply();
            initializeCore(); acceptCommand();
        } else if ("stop".equals(action)) {
            stopRequested = true; getSharedPreferences("phone", 0).edit().putBoolean("enabled", false).apply();
            endCall(null); acceptCommand();
        } else if ("dial".equals(action)) {
            String target = intent.getStringExtra("contact_id");
            if (config == null || !config.contacts.containsKey(target)) commandError = "unknown_contact";
            else if (callId != null || lease.hasToken()) commandError = "busy";
            else if (core == null || !"registered".equals(registration)) commandError = "not_registered";
            else {
                callId = UUID.randomUUID().toString(); contactId = target; state = "preparing";
                diagnostics.begin(callId);
                lastError = null; pendingAction = "dial"; acceptCommand(); lease.acquire();
            }
        } else if (Arrays.asList("answer", "decline", "hangup").contains(action)) {
            String expected = intent.getStringExtra("expected_call_id");
            if (callId == null || !callId.equals(expected)) commandError = "stale_call";
            else if ("answer".equals(action)) {
                if (!"ringing".equals(state) || call == null) commandError = "not_ringing";
                else { pendingAction = "answer"; state = "preparing"; acceptCommand();
                    if (lease.isHeld()) leaseGranted(); else lease.acquire(); }
            } else if ("decline".equals(action) && !"ringing".equals(state)) commandError = "not_ringing";
            else { acceptCommand(); endCall(null); }
        }
        commands.put(id, commandResult);
        if (commands.size() > 128) commands.remove(commands.keySet().iterator().next());
        publish();
    }
    private void acceptCommand() { commandResult = "accepted"; commandError = null; }
    @Override public void leaseGranted() {
        if (!"preparing".equals(state) || pendingAction == null || core == null) { finishMedia(); return; }
        try {
            String action = pendingAction; pendingAction = null;
            if ("ring".equals(action)) {
                if (call == null) { finishMedia(); return; }
                state = "ringing"; showIncoming(); publish(); return;
            }
            CallParams params = core.createCallParams("answer".equals(action) ? call : null);
            if (params == null) throw new IllegalStateException();
            params.setAudioEnabled(true); params.setVideoEnabled(false);
            if ("answer".equals(action)) {
                if (call == null || call.acceptWithParams(params) != 0) throw new IllegalStateException();
            } else {
                Address address = Factory.instance().createAddress(config.contacts.get(contactId).address);
                call = core.inviteAddressWithParams(address, params);
                if (call == null) throw new IllegalStateException();
                state = "dialing";
            }
            handler.removeCallbacks(callLimit); handler.postDelayed(callLimit, config.maxCallSeconds * 1000L);
            getSystemService(NotificationManager.class).cancel(2);
        } catch (Exception error) { endCall("call_start_failed"); }
        publish();
    }
    @Override public void leaseLost(String reason) { endCall(reason); }
    @Override public void leaseChanged() { publish(); }
    @Override public void leaseReleased() {
        handler.removeCallbacks(closeDeadline); handler.removeCallbacks(callLimit);
        getSystemService(NotificationManager.class).cancel(2);
        diagnostics.end(callId); callId = null; contactId = null; pendingAction = null;
        state = lastError == null ? "idle" : "error";
        if (stopRequested) { stopCore(); publish(); stopSelf(); }
        else { initializeCore(); publish(); }
    }
    private void endCall(String reason) {
        if (closing) return;
        if (reason != null) lastError = reason;
        recordAudio(call);
        pendingAction = null; state = "ending";
        handler.removeCallbacks(callLimit);
        getSystemService(NotificationManager.class).cancel(2);
        if (call != null) {
            try { call.terminate(); } catch (Exception error) { stopCore(); call = null; }
        }
        if (call == null) finishMedia();
        else { handler.removeCallbacks(closeDeadline); handler.postDelayed(closeDeadline, 10000); }
        publish();
    }
    private void finishMedia() {
        if (closing) return;
        if (core != null && core.getCalls().length != 0) return;
        handler.removeCallbacks(closeDeadline); handler.removeCallbacks(callLimit);
        call = null; pendingAction = null; state = "ending";
        if (lease.hasToken()) lease.release(); else leaseReleased();
    }
    private void stopCore() {
        recordAudio(call);
        diagnostics.end(callId);
        Core previous = core; core = null;
        if (previous != null) {
            previous.removeListener(listener);
            if (previous.getGlobalState() == GlobalState.On) previous.stop();
        }
        registration = "unconfigured";
    }
    static void importConfiguration(Context context, byte[] bytes) {
        new Handler(Looper.getMainLooper()).post(() -> {
            SipService service = instance;
            try {
                new SipConfig(new String(bytes, StandardCharsets.UTF_8));
                if (service != null && (service.callId != null || service.lease.hasToken())) throw new IllegalStateException("busy");
                AtomicFile file = new AtomicFile(context.getFileStreamPath("provision.json"));
                FileOutputStream output = null;
                try { output = file.startWrite(); output.write(bytes); file.finishWrite(output); }
                catch (Exception error) { if (output != null) file.failWrite(output); throw error; }
                if (service != null) { service.stopCore(); service.loadConfig(); service.initializeCore(); service.publish(); }
                else context.startForegroundService(new Intent(context, SipService.class));
            } catch (Exception error) {
                String code = error instanceof IllegalStateException ? "config_busy" : "invalid_config";
                if (service != null) { service.configError = code; service.publish(); }
                else setImportError(code);
            }
        });
    }
    static void setImportError(String code) {
        new Handler(Looper.getMainLooper()).post(() -> {
            if (instance != null) { instance.configError = code; instance.publish(); return; }
            try { JSONObject status = new JSONObject(statusJson); status.put("config_error", code); statusJson = status.toString(); }
            catch (Exception ignored) { }
        });
    }
    static String sha256(byte[] bytes) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes);
        StringBuilder text = new StringBuilder(); for (byte value : digest) text.append(String.format(Locale.ROOT, "%02x", value & 255));
        return text.toString();
    }
    private void publish() {
        try {
            JSONObject status = new JSONObject(); status.put("schema", 1);
            status.put("configured", config != null); status.put("config_sha256", nullable(configHash)); status.put("config_error", nullable(configError));
            status.put("endpoint_id", nullable(config == null ? null : config.endpointId));
            status.put("registration", registration); status.put("state", state);
            status.put("call_id", nullable(callId)); status.put("contact_id", nullable(contactId));
            status.put("lease_held", lease != null && lease.hasToken()); status.put("last_error", nullable(lastError));
            status.put("last_command_id", nullable(commandId)); status.put("last_command_result", nullable(commandResult)); status.put("last_command_error", nullable(commandError));
            statusJson = status.toString();
            getSystemService(NotificationManager.class).notify(STATUS_NOTIFICATION_ID, notification("Phone: " + state + " · " + registration));
        } catch (Exception ignored) { }
    }
    private static Object nullable(String value) { return value == null ? JSONObject.NULL : value; }
    private PendingIntent openPhone(boolean incoming) {
        return PendingIntent.getActivity(this, incoming ? 2 : 0, new Intent(this, MainActivity.class).putExtra("incoming_ui", incoming), PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);
    }
    private Notification notification(String text) {
        return new Notification.Builder(this, CHANNEL).setSmallIcon(android.R.drawable.sym_call_incoming)
            .setContentTitle("Show phone").setContentText(text).setContentIntent(openPhone(false)).setOngoing(true).build();
    }
    private void showIncoming() {
        getSystemService(NotificationManager.class).notify(2, new Notification.Builder(this, INCOMING)
            .setSmallIcon(android.R.drawable.sym_call_incoming).setContentTitle("Incoming call")
            .setContentText("Tap to answer or decline").setCategory(Notification.CATEGORY_CALL)
            .setFullScreenIntent(openPhone(true), true).setContentIntent(openPhone(true)).setAutoCancel(false).build());
    }
    @Override public void onDestroy() {
        closing = true; handler.removeCallbacksAndMessages(null);
        stopCore(); // Mandatory ordering: native media closed before Binder death/release.
        if (lease != null) { lease.release(); lease.close(); }
        getSystemService(NotificationManager.class).cancel(2);
        instance = null; super.onDestroy();
    }
}
