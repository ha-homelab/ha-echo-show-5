/* SPDX-License-Identifier: AGPL-3.0-only */
package org.hahomelab.show5sip;

/** Pure protocol checks shared by the Messenger client and host-side unit tests. */
final class LeaseReplyMatcher {
    static final int PROTOCOL = 1;
    private LeaseReplyMatcher() { }
    static boolean versionMatches(Object protocol) {
        return protocol instanceof Integer && ((Integer) protocol) == PROTOCOL;
    }
    static boolean requestMatches(String expected, String received) {
        return expected != null && !expected.isEmpty() && expected.equals(received);
    }
    static boolean tokenMatches(String expected, String received, boolean emptyAllowed) {
        if (emptyAllowed && (received == null || received.isEmpty())) return true;
        return expected != null && !expected.isEmpty() && expected.equals(received);
    }
}
