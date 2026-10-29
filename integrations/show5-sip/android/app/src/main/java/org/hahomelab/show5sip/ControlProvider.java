/* SPDX-License-Identifier: AGPL-3.0-only */
package org.hahomelab.show5sip;

import android.content.*;
import android.database.Cursor;
import android.database.MatrixCursor;
import android.net.Uri;
import android.os.ParcelFileDescriptor;
import android.os.SystemClock;
import android.util.AtomicFile;
import org.json.JSONObject;
import java.io.*;
import java.nio.charset.StandardCharsets;

/** DUMP-protected shell API. Config is write-only; query reveals sanitized status only. */
public final class ControlProvider extends ContentProvider {
    @Override public boolean onCreate() {
        try {
            byte[] bytes = new AtomicFile(getContext().getFileStreamPath("provision.json")).readFully();
            SipConfig config = new SipConfig(new String(bytes, StandardCharsets.UTF_8));
            JSONObject status = new JSONObject(SipService.statusJson);
            status.put("configured", true); status.put("config_sha256", SipService.sha256(bytes));
            status.put("endpoint_id", config.endpointId); status.put("last_error", "service_not_running");
            boolean pending = getContext().getSharedPreferences("phone", 0).contains("audio_lease");
            status.put("lease_held", pending); status.put("state", pending ? "ending" : "idle");
            SipService.statusJson = status.toString();
        } catch (FileNotFoundException ignored) { }
        catch (Exception error) { SipService.setImportError("invalid_config"); }
        return true;
    }
    @Override public Cursor query(Uri uri, String[] projection, String selection, String[] args, String sort) {
        if (!("/status".equals(uri.getPath()) || "/diagnostics".equals(uri.getPath()))
            || projection != null || selection != null || args != null || sort != null)
            throw new IllegalArgumentException("Only unfiltered /status and /diagnostics are supported");
        MatrixCursor cursor = new MatrixCursor(new String[]{"json"});
        cursor.addRow(new Object[]{"/diagnostics".equals(uri.getPath())
            ? SipService.diagnostics.json(SystemClock.elapsedRealtime()) : SipService.statusJson}); return cursor;
    }
    @Override public ParcelFileDescriptor openFile(Uri uri, String mode) throws FileNotFoundException {
        if (!"/config".equals(uri.getPath()) || !("w".equals(mode) || "wt".equals(mode)))
            throw new FileNotFoundException("Only write-only /config is supported");
        try {
            ParcelFileDescriptor[] pipe = ParcelFileDescriptor.createReliablePipe();
            Thread reader = new Thread(() -> {
                try (InputStream input = new ParcelFileDescriptor.AutoCloseInputStream(pipe[0]);
                     ByteArrayOutputStream output = new ByteArrayOutputStream()) {
                    byte[] chunk = new byte[4096]; int count;
                    while ((count = input.read(chunk)) != -1) {
                        if (output.size() + count > SipConfig.MAX_BYTES) throw new IOException("config_too_large");
                        output.write(chunk, 0, count);
                    }
                    byte[] bytes = output.toByteArray();
                    new SipConfig(new String(bytes, StandardCharsets.UTF_8));
                    SipService.importConfiguration(getContext().getApplicationContext(), bytes);
                } catch (Exception error) { SipService.setImportError("invalid_config"); }
            }, "private-config-import");
            reader.setDaemon(true); reader.start(); return pipe[1];
        } catch (IOException error) { throw new FileNotFoundException("Configuration pipe unavailable"); }
    }
    @Override public String getType(Uri uri) { return "application/json"; }
    @Override public Uri insert(Uri uri, ContentValues values) { throw new UnsupportedOperationException(); }
    @Override public int delete(Uri uri, String selection, String[] args) { throw new UnsupportedOperationException(); }
    @Override public int update(Uri uri, ContentValues values, String selection, String[] args) { throw new UnsupportedOperationException(); }
}
