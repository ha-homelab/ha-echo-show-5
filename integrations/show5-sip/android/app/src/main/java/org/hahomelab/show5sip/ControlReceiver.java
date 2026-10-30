/* SPDX-License-Identifier: AGPL-3.0-only */
package org.hahomelab.show5sip;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Shell/system entry point. Manifest enforces DUMP; never accepts a SIP address. */
public final class ControlReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        if (!"org.hahomelab.show5sip.CONTROL".equals(intent.getAction())) return;
        Intent command = new Intent(context, SipService.class);
        for (String key : new String[]{"command", "request_id", "contact_id", "expected_call_id"})
            command.putExtra(key, intent.getStringExtra(key));
        context.startForegroundService(command);
    }
}
