/* SPDX-License-Identifier: AGPL-3.0-only */
package org.hahomelab.show5sip;

import org.junit.Test;
import static org.junit.Assert.*;

public class LeaseReplyMatcherTest {
    @Test public void acceptsOnlyActualIntegerProtocolOne() {
        assertTrue(LeaseReplyMatcher.versionMatches(1));
        for (Object invalid : new Object[]{null, 0, 2, "1", 1L, true})
            assertFalse(LeaseReplyMatcher.versionMatches(invalid));
    }
    @Test public void requiresCurrentRequestNotDelayedOrUnsolicitedResponse() {
        assertTrue(LeaseReplyMatcher.requestMatches("new", "new"));
        assertFalse(LeaseReplyMatcher.requestMatches("new", "old"));
        assertFalse(LeaseReplyMatcher.requestMatches(null, null));
        assertFalse(LeaseReplyMatcher.requestMatches("", ""));
    }
    @Test public void grantAndRevokeRequireExactNonemptyToken() {
        assertTrue(LeaseReplyMatcher.tokenMatches("owned", "owned", false));
        assertFalse(LeaseReplyMatcher.tokenMatches("owned", "other", false));
        assertFalse(LeaseReplyMatcher.tokenMatches("owned", "", false));
        assertFalse(LeaseReplyMatcher.tokenMatches(null, null, false));
    }
    @Test public void idleReleaseAckMayOmitTokenButNeverSubstituteAnother() {
        assertTrue(LeaseReplyMatcher.tokenMatches("owned", "", true));
        assertTrue(LeaseReplyMatcher.tokenMatches("owned", "owned", true));
        assertFalse(LeaseReplyMatcher.tokenMatches("owned", "other", true));
    }
}
