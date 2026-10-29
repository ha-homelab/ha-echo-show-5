/* SPDX-License-Identifier: AGPL-3.0-only */
package org.hahomelab.show5sip;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

/** Android 11 pilot: restore registration only; never replay a call after boot. */
public final class BootReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context context, Intent intent) {
        if (Intent.ACTION_BOOT_COMPLETED.equals(intent.getAction())
            && context.getFileStreamPath("provision.json").isFile()
            && context.getSharedPreferences("phone", 0).getBoolean("enabled", true))
            context.startForegroundService(new Intent(context, SipService.class));
    }
}
