/* SPDX-License-Identifier: AGPL-3.0-only */
package org.hahomelab.show5sip;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.*;
import android.util.AtomicFile;
import android.view.Gravity;
import android.widget.*;
import org.json.JSONObject;
import java.nio.charset.StandardCharsets;
import java.util.UUID;

/** Small-screen native UI. Intents cannot select a contact or answer a call. */
public final class MainActivity extends Activity {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private LinearLayout layout;
    private String rendered = "";
    private boolean returnToClock;
    private String observedCall;
    private final Runnable poll = new Runnable() {
        @Override public void run() { render(); handler.postDelayed(this, 500); }
    };
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved); setShowWhenLocked(true); setTurnScreenOn(true);
        returnToClock = saved != null ? saved.getBoolean("return_to_clock") : getIntent().getBooleanExtra("incoming_ui", false);
        observedCall = saved == null ? null : saved.getString("observed_call");
        ScrollView scroll = new ScrollView(this);
        layout = new LinearLayout(this); layout.setOrientation(LinearLayout.VERTICAL);
        layout.setPadding(18, 8, 18, 8); layout.setGravity(Gravity.CENTER_HORIZONTAL);
        scroll.addView(layout); setContentView(scroll);
        if (checkSelfPermission(Manifest.permission.RECORD_AUDIO) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, 1);
        } else startForegroundService(new Intent(this, SipService.class));
        if (Build.VERSION.SDK_INT >= 33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED)
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 2);
    }
    @Override protected void onResume() { super.onResume(); handler.post(poll); }
    @Override protected void onPause() { handler.removeCallbacks(poll); super.onPause(); }
    @Override protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent); setIntent(intent);
        returnToClock = intent.getBooleanExtra("incoming_ui", false); rendered = "";
    }
    @Override protected void onSaveInstanceState(Bundle state) {
        state.putBoolean("return_to_clock", returnToClock); state.putString("observed_call", observedCall);
        super.onSaveInstanceState(state);
    }
    @Override public void onRequestPermissionsResult(int request, String[] permissions, int[] results) {
        super.onRequestPermissionsResult(request, permissions, results);
        if (request == 1 && results.length > 0 && results[0] == PackageManager.PERMISSION_GRANTED)
            startForegroundService(new Intent(this, SipService.class));
    }
    private void render() {
        String raw = SipService.statusJson;
        if (raw.equals(rendered)) return;
        rendered = raw; layout.removeAllViews();
        try {
            JSONObject status = new JSONObject(raw);
            text("Show phone", 24);
            text(status.getString("registration") + " · " + status.getString("state"), 18);
            if (!status.isNull("last_error")) text(status.getString("last_error").replace('_', ' '), 15);
            String state = status.getString("state");
            String callId = status.isNull("call_id") ? null : status.getString("call_id");
            if (callId != null) observedCall = callId;
            else if (returnToClock && observedCall != null && !status.getBoolean("lease_held")
                && ("idle".equals(state) || "error".equals(state))) { goToClock(); return; }
            if ("ringing".equals(state)) {
                button("Answer", "answer", null, callId); button("Decline", "decline", null, callId);
            } else if (callId != null) button("End call", "hangup", null, callId);
            else {
                try {
                    SipConfig config = new SipConfig(new String(new AtomicFile(getFileStreamPath("provision.json")).readFully(), StandardCharsets.UTF_8));
                    if ("registered".equals(status.getString("registration")))
                        for (SipConfig.Contact contact : config.contacts.values()) button(contact.label, "dial", contact.id, null);
                    else button("Connect phone", "start", null, null);
                } catch (Exception ignored) { text("Not configured. Use the private provisioning tool.", 17); }
            }
            Button home = new Button(this); home.setText(callId == null ? "Clock" : "End and clock");
            home.setOnClickListener(view -> {
                if (callId == null) goToClock();
                else { returnToClock = true; send("hangup", null, callId); }
            }); layout.addView(home);
        } catch (Exception ignored) { text("Phone status unavailable", 18); }
    }
    private void text(String label, int size) {
        TextView view = new TextView(this); view.setText(label); view.setTextSize(size);
        view.setGravity(Gravity.CENTER); layout.addView(view);
    }
    private void button(String title, String command, String contactId, String callId) {
        Button button = new Button(this); button.setText(title); button.setTextSize(19);
        button.setOnClickListener(view -> send(command, contactId, callId));
        layout.addView(button);
    }
    private void send(String command, String contactId, String callId) {
        startForegroundService(new Intent(this, SipService.class)
            .putExtra("command", command).putExtra("request_id", UUID.randomUUID().toString())
            .putExtra("contact_id", contactId).putExtra("expected_call_id", callId));
    }
    private void goToClock() {
        returnToClock = false;
        try {
            startActivity(new Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_HOME).setPackage("com.msp1974.vacompanion"));
            finish();
        } catch (android.content.ActivityNotFoundException error) { text("Clock is unavailable", 17); }
    }
}
