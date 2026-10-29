/* SPDX-License-Identifier: AGPL-3.0-only */
package org.hahomelab.show5sip;

import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;
import java.net.URI;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.Arrays;
import java.util.HashSet;

/** Strict private provisioning. No credentials are returned through status or logs. */
public final class SipConfig {
    public static final int MAX_BYTES = 65536;
    public final String endpointId, username, password, domain, transport, displayName;
    public final int maxCallSeconds;
    public final Map<String, Contact> contacts = new LinkedHashMap<>();
    public static final class Contact {
        public final String id, label, address;
        Contact(String id, String label, String address) {
            this.id = id; this.label = label; this.address = address;
        }
    }
    public SipConfig(String raw) throws JSONException {
        if (raw.getBytes(java.nio.charset.StandardCharsets.UTF_8).length > MAX_BYTES) throw new JSONException("config_too_large");
        JSONObject root = new JSONObject(raw);
        exactKeys(root, keys("schema", "endpoint_id", "sip", "contacts", "max_call_seconds"));
        if (integer(root, "schema") != 1) throw new JSONException("unsupported_schema");
        endpointId = identifier(root.getString("endpoint_id"));
        JSONObject sip = root.getJSONObject("sip");
        exactKeys(sip, keys("username", "password", "domain", "transport", "display_name"));
        username = sip.getString("username");
        if (!username.matches("[A-Za-z0-9_.+-]{1,80}")) throw new JSONException("invalid_username");
        password = sip.getString("password");
        if (password.isEmpty() || password.length() > 512 || password.chars().anyMatch(c -> c < 32 || c == 127)) throw new JSONException("invalid_password");
        domain = sip.getString("domain");
        try {
            URI host = new URI("sipcheck://" + domain);
            if (host.getHost() == null || host.getRawUserInfo() != null || !host.getRawPath().isEmpty()
                || host.getRawQuery() != null || host.getRawFragment() != null
                || host.getPort() == 0 || host.getPort() > 65535 || domain.length() > 253)
                throw new Exception();
        } catch (Exception error) { throw new JSONException("invalid_domain"); }
        transport = sip.getString("transport");
        if (!keys("tcp", "udp", "tls").contains(transport)) throw new JSONException("invalid_transport");
        displayName = label(sip.getString("display_name"));
        maxCallSeconds = integer(root, "max_call_seconds");
        if (maxCallSeconds < 10 || maxCallSeconds > 1800) throw new JSONException("invalid_call_limit");
        JSONArray items = root.getJSONArray("contacts");
        if (items.length() == 0 || items.length() > 64) throw new JSONException("invalid_contacts");
        for (int i = 0; i < items.length(); i++) {
            JSONObject item = items.getJSONObject(i);
            exactKeys(item, keys("id", "label", "address"));
            String id = identifier(item.getString("id"));
            String address = item.getString("address");
            // No routing parameters, URI headers or arbitrary externally supplied targets.
            if (!address.matches("sip:[A-Za-z0-9_.+-]{1,80}@" + java.util.regex.Pattern.quote(domain)))
                throw new JSONException("invalid_contact_address");
            if (contacts.put(id, new Contact(id, label(item.getString("label")), address)) != null)
                throw new JSONException("duplicate_contact");
        }
    }
    static String identifier(String value) throws JSONException {
        if (!value.matches("[a-z][a-z0-9_]{0,47}")) throw new JSONException("invalid_identifier");
        return value;
    }
    static String label(String value) throws JSONException {
        if (value.trim().isEmpty() || value.length() > 80 || value.chars().anyMatch(c -> c < 32 || c == 127)) throw new JSONException("invalid_label");
        return value;
    }
    private static void exactKeys(JSONObject object, Set<String> keys) throws JSONException {
        if (object.length() != keys.size()) throw new JSONException("unexpected_fields");
        for (String key : keys) if (!object.has(key) || object.isNull(key)) throw new JSONException("missing_field");
    }
    private static Set<String> keys(String... values) { return new HashSet<>(Arrays.asList(values)); }
    private static int integer(JSONObject object, String key) throws JSONException {
        Object value = object.get(key);
        if (!(value instanceof Integer) && !(value instanceof Long)) throw new JSONException("invalid_integer");
        long result = ((Number) value).longValue();
        if (result < Integer.MIN_VALUE || result > Integer.MAX_VALUE) throw new JSONException("invalid_integer");
        return (int) result;
    }
}
