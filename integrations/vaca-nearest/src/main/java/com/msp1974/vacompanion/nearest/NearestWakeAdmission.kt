// SPDX-License-Identifier: Apache-2.0
package com.msp1974.vacompanion.nearest

/** Disabled arbitration preserves the prior local wake/stop behavior of active Assist. */
internal fun nearestWakeAllowed(enabled: Boolean, canAnswer: () -> Boolean, captureAllowed: () -> Boolean): Boolean =
    if (enabled) canAnswer() else captureAllowed()
