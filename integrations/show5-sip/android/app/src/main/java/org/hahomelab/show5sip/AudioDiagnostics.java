/* SPDX-License-Identifier: AGPL-3.0-only */
package org.hahomelab.show5sip;

import org.json.JSONException;
import org.json.JSONObject;
import java.util.Arrays;
import java.util.Locale;

/** Metadata only. No addresses, payload bytes, capture controls or native objects. */
final class AudioDiagnostics {
    private String callId, codec, ice;
    private Integer rate, channels;
    private Double upload, download;
    private long sampledAt, samples;
    private boolean retained;
    synchronized void begin(String id) {
        if (id == null || !id.matches("[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"))
            throw new IllegalArgumentException("invalid_call_id");
        callId = id; codec = null; ice = null; rate = null; channels = null;
        upload = null; download = null; sampledAt = 0; samples = 0; retained = false;
    }
    synchronized void update(String id, String mime, int clockRate, int channelCount,
                             double sentKbps, double receivedKbps, String iceState, long now) {
        if (retained || callId == null || !callId.equals(id)) return;
        String normalized = mime == null ? "" : mime.toUpperCase(Locale.ROOT);
        codec = Arrays.asList("G722", "PCMU", "PCMA").contains(normalized) ? normalized : null;
        rate = clockRate > 0 && clockRate <= 192000 ? clockRate : null;
        channels = channelCount > 0 && channelCount <= 8 ? channelCount : null;
        upload = finiteRate(sentKbps); download = finiteRate(receivedKbps);
        ice = Arrays.asList("NotActivated", "Failed", "InProgress", "HostConnection", "ReflexiveConnection", "RelayConnection").contains(iceState) ? iceState : null;
        sampledAt = Math.max(0, now); samples++;
    }
    synchronized void end(String id) { if (callId != null && callId.equals(id)) retained = true; }
    synchronized String json(long now) {
        JSONObject output = new JSONObject();
        try {
            output.put("schema", 1); output.put("call_id", nullable(callId));
            output.put("audio_codec", nullable(codec)); output.put("clock_rate", nullable(rate));
            output.put("channels", nullable(channels)); output.put("upload_kbps", nullable(upload));
            output.put("download_kbps", nullable(download)); output.put("ice_state", nullable(ice));
            output.put("retained", retained); output.put("samples", samples);
            output.put("sample_age_ms", samples == 0 ? JSONObject.NULL : Math.max(0, now - sampledAt));
        } catch (JSONException impossible) { throw new IllegalStateException(impossible); }
        return output.toString();
    }
    private static Double finiteRate(double value) {
        return !Double.isNaN(value) && !Double.isInfinite(value) && value >= 0 && value <= 1000000 ? value : null;
    }
    private static Object nullable(Object value) { return value == null ? JSONObject.NULL : value; }
}
