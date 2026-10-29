/* SPDX-License-Identifier: AGPL-3.0-only */
package org.hahomelab.show5sip;

import android.content.ComponentName;
import android.content.Context;
import android.content.Intent;
import android.content.ServiceConnection;
import android.content.SharedPreferences;
import android.os.Bundle;
import android.os.Handler;
import android.os.IBinder;
import android.os.Message;
import android.os.Messenger;
import android.os.RemoteException;
import java.util.UUID;

/** Same-signer local microphone lease. All methods/callbacks run on the main looper. */
final class AudioLeaseClient {
    interface Owner {
        void leaseGranted();
        void leaseLost(String reason);
        void leaseReleased();
        void leaseChanged();
    }
    static final int STATUS = 1, ACQUIRE = 2, RENEW = 3, RELEASE = 4, RESULT = 100, REVOKE = 101;
    private final Context context;
    private final Handler handler;
    private final Owner owner;
    private final SharedPreferences preferences;
    private final Messenger replies;
    private Messenger remote;
    private boolean bound, closed, releasing, acquiring, protocolRejected;
    private String token, request;
    private int operation;
    private boolean held;
    private final Runnable deadline = this::onDeadline;
    private void onDeadline() {
        if (closed) return;
        // A timed out acquire may already have stopped VACA. Retain its token and release it.
        owner.leaseLost("lease_timeout");
    }
    private final Runnable renewal = new Runnable() {
        @Override public void run() {
            if (!closed && held && !releasing) {
                send(RENEW);
            }
        }
    };
    private final ServiceConnection connection = new ServiceConnection() {
        @Override public void onServiceConnected(ComponentName name, IBinder binder) {
            remote = new Messenger(binder);
            if (releasing || (!acquiring && token != null)) send(RELEASE);
            else if (acquiring) send(ACQUIRE);
            else send(STATUS);
        }
        @Override public void onServiceDisconnected(ComponentName name) {
            remote = null; held = false;
            handler.removeCallbacks(renewal);
            owner.leaseLost("lease_disconnected");
        }
        @Override public void onBindingDied(ComponentName name) {
            onServiceDisconnected(name);
            unbind();
            if (!closed) handler.postDelayed(AudioLeaseClient.this::bind, 1000);
        }
        @Override public void onNullBinding(ComponentName name) {
            unbind(); bindFailed("lease_unavailable");
        }
    };
    AudioLeaseClient(Context context, Handler handler, Owner owner) {
        this.context = context; this.handler = handler; this.owner = owner;
        preferences = context.getSharedPreferences("phone", 0);
        token = preferences.getString("audio_lease", null);
        replies = new Messenger(new Handler(handler.getLooper(), this::receive));
    }
    boolean hasToken() { return token != null; }
    boolean isHeld() { return held; }
    void recover() { if (token != null) { releasing = true; bind(); } }
    void acquire() {
        if (token != null || closed) { owner.leaseLost("lease_busy"); return; }
        token = UUID.randomUUID().toString();
        if (!preferences.edit().putString("audio_lease", token).commit()) {
            token = null; owner.leaseLost("lease_journal_failed"); return;
        }
        acquiring = true; releasing = false;
        owner.leaseChanged();
        if (remote != null) send(ACQUIRE); else bind();
        handler.removeCallbacks(deadline); handler.postDelayed(deadline, 15000);
    }
    /** Caller must already have closed all native audio, including early media. */
    void release() {
        acquiring = false; releasing = true; held = false;
        handler.removeCallbacks(renewal); handler.removeCallbacks(deadline);
        if (token == null) { releasing = false; owner.leaseReleased(); return; }
        if (protocolRejected) { owner.leaseChanged(); return; }
        if (remote != null) send(RELEASE); else bind();
        owner.leaseChanged();
    }
    private void bind() {
        if (closed || bound) return;
        Intent intent = new Intent("com.msp1974.vacompanion.AUDIO_LEASE")
            .setComponent(new ComponentName("com.msp1974.vacompanion", "com.msp1974.vacompanion.telephony.AudioLeaseService"));
        try {
            bound = context.bindService(intent, connection, Context.BIND_AUTO_CREATE);
            if (!bound) bindFailed("lease_unavailable");
        } catch (SecurityException error) { bindFailed("lease_permission_denied"); }
    }
    private void bindFailed(String reason) {
        if (releasing) {
            owner.leaseChanged();
            // In particular, do not recursively request release from a failed bind.
            handler.postDelayed(() -> { if (releasing && !closed) bind(); }, 3000);
        } else owner.leaseLost(reason);
    }
    private void send(int what) {
        if (closed || remote == null) return;
        operation = what; request = UUID.randomUUID().toString();
        Message message = Message.obtain(null, what);
        Bundle data = new Bundle();
        data.putString("request_id", request);
        if (token != null) data.putString("lease_id", token);
        data.putLong("ttl_ms", 30000L);
        message.setData(data); message.replyTo = replies;
        try { remote.send(message); }
        catch (RemoteException error) { unbind(); owner.leaseLost("lease_disconnected"); return; }
        handler.removeCallbacks(deadline); handler.postDelayed(deadline, 15000);
    }
    private boolean receive(Message message) {
        Bundle data = message.getData();
        if (message.what != RESULT && message.what != REVOKE) return true;
        if (protocolRejected) return true;
        if (!LeaseReplyMatcher.versionMatches(data.get("protocol"))) {
            protocolRejected = true;
            owner.leaseLost("lease_protocol_mismatch"); return true;
        }
        if (message.what == REVOKE) {
            if (LeaseReplyMatcher.tokenMatches(token, data.getString("lease_id"), false)) {
                held = false; handler.removeCallbacks(renewal);
                owner.leaseLost("lease_revoked");
            }
            return true;
        }
        if (!LeaseReplyMatcher.requestMatches(request, data.getString("request_id"))) return true;
        handler.removeCallbacks(deadline);
        boolean ok = data.getBoolean("ok", false);
        String resultToken = data.getString("lease_id", "");
        if (operation != STATUS && !LeaseReplyMatcher.tokenMatches(token, resultToken, true)) {
            owner.leaseLost("lease_reply_mismatch"); return true;
        }
        if (operation == RELEASE) {
            if (ok && "idle".equals(data.getString("state"))) {
                if (!preferences.edit().remove("audio_lease").commit()) {
                    owner.leaseLost("lease_journal_failed"); return true;
                }
                token = null; held = false; acquiring = false; releasing = false;
                owner.leaseReleased();
            } else {
                // Keep ownership and retry release; never resume calls on an uncertain journal.
                owner.leaseChanged(); handler.postDelayed(() -> { if (releasing) send(RELEASE); }, 3000);
            }
        } else if (operation == ACQUIRE) {
            if (ok && "held".equals(data.getString("state")) && LeaseReplyMatcher.tokenMatches(token, resultToken, false)) {
                acquiring = false; held = true;
                handler.removeCallbacks(renewal); handler.postDelayed(renewal, 10000);
                owner.leaseGranted();
            } else owner.leaseLost("lease_denied");
        } else if (operation == RENEW) {
            if (!ok || !"held".equals(data.getString("state"))) owner.leaseLost("lease_revoked");
            else { handler.removeCallbacks(renewal); handler.postDelayed(renewal, 10000); }
        }
        return true;
    }
    private void unbind() {
        if (bound) { try { context.unbindService(connection); } catch (IllegalArgumentException ignored) { } }
        bound = false; remote = null;
    }
    void close() {
        closed = true; handler.removeCallbacks(renewal); handler.removeCallbacks(deadline); unbind();
        // Never delete the durable token here. A later process must reconcile it.
    }
}
