/* SPDX-License-Identifier: AGPL-3.0-only */
package org.hahomelab.show5sip;

import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;

public class AudioDiagnosticsTest {
    private static final String FIRST = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
    private static final String SECOND = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb";
    @Test public void absentSamplesAreNullNotFakeZeroTraffic() throws Exception {
        JSONObject json = new JSONObject(new AudioDiagnostics().json(5000));
        assertTrue(json.isNull("call_id")); assertTrue(json.isNull("download_kbps"));
        assertTrue(json.isNull("sample_age_ms")); assertEquals(0, json.getLong("samples"));
    }
    @Test public void realScalarMetadataIncludesAgeAndRtpClock() throws Exception {
        AudioDiagnostics data = new AudioDiagnostics(); data.begin(FIRST);
        data.update(FIRST, "g722", 8000, 1, 80.5, 82.25, "NotActivated", 1000);
        JSONObject json = new JSONObject(data.json(1200));
        assertEquals("G722", json.getString("audio_codec")); assertEquals(8000, json.getInt("clock_rate"));
        assertEquals(80.5, json.getDouble("upload_kbps"), 0.001); assertEquals(200, json.getLong("sample_age_ms"));
        assertFalse(json.getBoolean("retained"));
    }
    @Test public void retainedSampleCannotBeChangedByLateEvents() throws Exception {
        AudioDiagnostics data = new AudioDiagnostics(); data.begin(FIRST);
        data.update(FIRST, "PCMU", 8000, 1, 80, 81, "NotActivated", 1000); data.end(FIRST);
        data.update(FIRST, "PCMU", 8000, 1, 0, 0, "Failed", 2000);
        JSONObject json = new JSONObject(data.json(2200));
        assertTrue(json.getBoolean("retained")); assertEquals(1, json.getLong("samples"));
        assertEquals(80, json.getDouble("upload_kbps"), 0); assertEquals(1200, json.getLong("sample_age_ms"));
    }
    @Test public void nextCallResetsMetadataAndRejectsOldCall() throws Exception {
        AudioDiagnostics data = new AudioDiagnostics(); data.begin(FIRST);
        data.update(FIRST, "PCMU", 8000, 1, 80, 81, "NotActivated", 1000);
        data.begin(SECOND); data.update(FIRST, "PCMU", 8000, 1, 90, 91, "NotActivated", 2000); data.end(FIRST);
        JSONObject json = new JSONObject(data.json(2200));
        assertEquals(SECOND, json.getString("call_id")); assertEquals(0, json.getLong("samples"));
        assertFalse(json.getBoolean("retained")); assertTrue(json.isNull("audio_codec"));
    }
    @Test public void malformedNativeMetadataNeverLeaksTextOrInvalidNumbers() throws Exception {
        AudioDiagnostics data = new AudioDiagnostics(); data.begin(FIRST);
        data.update(FIRST, "sip:secret@example.invalid", -1, 999, Double.NaN, Double.POSITIVE_INFINITY, "secret", 1000);
        JSONObject json = new JSONObject(data.json(2200));
        for (String key : new String[]{"audio_codec", "clock_rate", "channels", "upload_kbps", "download_kbps", "ice_state"}) assertTrue(json.isNull(key));
        assertFalse(json.toString().contains("secret"));
    }
}
