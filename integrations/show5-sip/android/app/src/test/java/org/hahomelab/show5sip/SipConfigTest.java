/* SPDX-License-Identifier: AGPL-3.0-only */
package org.hahomelab.show5sip;

import org.json.*;
import org.junit.Test;
import static org.junit.Assert.*;

public class SipConfigTest {
    private JSONObject sample() throws Exception {
        return new JSONObject("{\"schema\":1,\"endpoint_id\":\"show_one\",\"sip\":{\"username\":\"230\",\"password\":\"test-only\",\"domain\":\"pbx.example.invalid:5060\",\"transport\":\"tcp\",\"display_name\":\"Show one\"},\"contacts\":[{\"id\":\"echo\",\"label\":\"Echo test\",\"address\":\"sip:600@pbx.example.invalid:5060\"}],\"max_call_seconds\":120}");
    }
    private void rejects(JSONObject value) {
        assertThrows(JSONException.class, () -> new SipConfig(value.toString()));
    }
    @Test public void validPrivateProvisioningAndOrdering() throws Exception {
        SipConfig config = new SipConfig(sample().toString());
        assertEquals("show_one", config.endpointId); assertEquals(120, config.maxCallSeconds);
        assertEquals("sip:600@pbx.example.invalid:5060", config.contacts.get("echo").address);
    }
    @Test public void rejectsUnexpectedRootFields() throws Exception { rejects(sample().put("auto_answer", true)); }
    @Test public void rejectsUnknownSipTransport() throws Exception {
        JSONObject config = sample(); config.getJSONObject("sip").put("transport", "http"); rejects(config);
    }
    @Test public void rejectsRoutingAndHeadersInContact() throws Exception {
        for (String suffix : new String[]{"?Replaces=x", ";transport=udp", "@evil.invalid", "\r\nVia:x"}) {
            JSONObject config = sample();
            JSONObject item = config.getJSONArray("contacts").getJSONObject(0);
            item.put("address", item.getString("address") + suffix); rejects(config);
        }
    }
    @Test public void rejectsOtherPbxAndDuplicateContact() throws Exception {
        JSONObject config = sample(); config.getJSONArray("contacts").getJSONObject(0).put("address", "sip:600@elsewhere.invalid"); rejects(config);
        config = sample(); config.getJSONArray("contacts").put(config.getJSONArray("contacts").getJSONObject(0)); rejects(config);
    }
    @Test public void rejectsUnsafeHost() throws Exception {
        for (String host : new String[]{"user@host", "host/path", "host?query", "host#fragment", "host:0", "host:65536", "host\nname"}) {
            JSONObject config = sample(); config.getJSONObject("sip").put("domain", host); rejects(config);
        }
    }
    @Test public void requiresBoundedIntegerTimeLimit() throws Exception {
        for (Object seconds : new Object[]{0, 1801, 120.5, "120", true}) rejects(sample().put("max_call_seconds", seconds));
    }
    @Test public void rejectsEmptyAndOversizedContacts() throws Exception {
        JSONObject config = sample(); config.put("contacts", new JSONArray()); rejects(config);
        config = sample(); JSONArray entries = config.getJSONArray("contacts");
        for (int n = 1; n < 65; n++) entries.put(new JSONObject().put("id", "contact_" + n).put("label", "Contact").put("address", "sip:600@pbx.example.invalid:5060"));
        rejects(config);
    }
    @Test public void rejectsCredentialsWithControlCharacters() throws Exception {
        JSONObject config = sample(); config.getJSONObject("sip").put("password", "hello\nworld"); rejects(config);
    }
    @Test public void rejectsArbitraryContactKeys() throws Exception {
        JSONObject config = sample(); config.getJSONArray("contacts").getJSONObject(0).put("id", "../../other"); rejects(config);
    }
}
