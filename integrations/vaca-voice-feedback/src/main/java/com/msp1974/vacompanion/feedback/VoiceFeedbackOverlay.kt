package com.msp1974.vacompanion.feedback

import android.content.Context
import android.database.ContentObserver
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.accessibility.AccessibilityManager
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.PI
import kotlin.math.sin

/** The caller owns foreground/settings visibility. No pointer or focus handler is installed. */
@Composable
fun VoiceFeedbackOverlay(modifier: Modifier = Modifier) {
    val state by VoiceFeedbackRuntime.state.collectAsState()
    if (state.phase == FeedbackPhase.HIDDEN) return
    val reducedMotion = rememberReducedMotion()
    val progress = feedbackProgress(state.phase, !reducedMotion)
    val phase = state.phase
    val blue = Color(0xFF2389FF)
    val cyan = Color(0xFF78F1FF)
    Box(modifier.fillMaxSize()) {
        Box(
            Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(56.dp)
                .testTag("voice-feedback")
                .background(Brush.verticalGradient(listOf(Color.Transparent, Color.Black.copy(alpha = 0.76f))))
                .semantics(mergeDescendants = true) {
                    contentDescription = "Voice assistant"
                    stateDescription = phase.label
                    liveRegion = LiveRegionMode.Polite
                }
        ) {
            Text(
                phase.label,
                color = Color(0xFFE5F9FF), fontSize = 15.sp, fontWeight = FontWeight.Medium,
                modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 16.dp)
                    .clearAndSetSemantics { }
            )
            Canvas(Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(19.dp).clearAndSetSemantics { }) {
                // A stylized phase animation: deliberately unrelated to live microphone energy.
                val pulse = if (reducedMotion) 0.85f else (0.72f + 0.18f * sin(progress * 2f * PI).toFloat())
                val center = if (phase == FeedbackPhase.THINKING && !reducedMotion) progress else 0.5f
                val spread = if (phase == FeedbackPhase.SPEAKING) 0.48f else 0.30f
                val barHeight = 4.dp.toPx()
                drawRect(Brush.verticalGradient(listOf(Color.Transparent, blue.copy(alpha = 0.24f * pulse))))
                drawRect(
                    color = blue.copy(alpha = if (phase == FeedbackPhase.LISTENING) pulse else 0.82f),
                    topLeft = Offset(0f, size.height - barHeight), size = Size(size.width, barHeight)
                )
                drawRect(
                    brush = Brush.horizontalGradient(
                        listOf(Color.Transparent, cyan.copy(alpha = pulse), Color.Transparent),
                        startX = (center - spread) * size.width, endX = (center + spread) * size.width
                    ),
                    topLeft = Offset(0f, size.height - barHeight), size = Size(size.width, barHeight)
                )
            }
        }
    }
}

@Composable
private fun feedbackProgress(phase: FeedbackPhase, enabled: Boolean): Float {
    if (!enabled) return 0.5f
    val transition = rememberInfiniteTransition(label = "voice-phase")
    val progress by transition.animateFloat(
        initialValue = 0f, targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(if (phase == FeedbackPhase.SPEAKING) 2400 else 1800, easing = LinearEasing),
            repeatMode = RepeatMode.Restart
        ),
        label = "voice-phase-position"
    )
    return progress
}

@Composable
private fun rememberReducedMotion(): Boolean {
    val context = LocalContext.current
    val accessibility = remember(context) { context.getSystemService(Context.ACCESSIBILITY_SERVICE) as? AccessibilityManager }
    fun motionDisabled(): Boolean = runCatching {
        Settings.Global.getFloat(context.contentResolver, Settings.Global.ANIMATOR_DURATION_SCALE, 1f) <= 0f
    }.getOrDefault(false)
    var animationsDisabled by remember(context) { mutableStateOf(motionDisabled()) }
    var touchExploration by remember(accessibility) { mutableStateOf(accessibility?.isTouchExplorationEnabled == true) }
    DisposableEffect(context, accessibility) {
        val observer = object : ContentObserver(Handler(Looper.getMainLooper())) {
            override fun onChange(selfChange: Boolean) { animationsDisabled = motionDisabled() }
        }
        val listener = AccessibilityManager.TouchExplorationStateChangeListener { touchExploration = it }
        context.contentResolver.registerContentObserver(
            Settings.Global.getUriFor(Settings.Global.ANIMATOR_DURATION_SCALE), false, observer
        )
        accessibility?.addTouchExplorationStateChangeListener(listener)
        onDispose {
            context.contentResolver.unregisterContentObserver(observer)
            accessibility?.removeTouchExplorationStateChangeListener(listener)
        }
    }
    return animationsDisabled || touchExploration
}
