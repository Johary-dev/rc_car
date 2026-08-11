package com.tpi.rccamera.ui

import android.graphics.BitmapFactory
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectVerticalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.BiasAlignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.tpi.rccamera.camera.CameraUiState
import com.tpi.rccamera.camera.CameraViewModel
import com.tpi.rccamera.camera.Direction
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlin.math.roundToInt

// ── Design tokens ─────────────────────────────────────────────────────────────

private val ScreenBg           = Color(0xFF0A0B0E)
private val PanelBg            = Color(0xFF12161F)
private val ButtonBg           = Color(0xFF1A2030)
private val ButtonActiveBg     = Color(0xFF0D2550)
private val ButtonBorder       = Color(0xFF252D40)
private val ButtonActiveBorder = Color(0xFF3D7EFF)
private val AccentBlue         = Color(0xFF3D7EFF)
private val AccentGreen        = Color(0xFF34D399)
private val AccentYellow       = Color(0xFFFBBF24)
private val AccentRed          = Color(0xFFFF6B6B)
private val AccentOrange       = Color(0xFFFFB74D)
private val CameraBg           = Color(0xFF050607)
private val TextPrimary        = Color.White
private val TextSecondary      = Color(0xFF7A8899)
private val OverlayBg          = Color(0xBB000000)

// ── Écran principal ───────────────────────────────────────────────────────────

@Composable
fun CameraScreen(viewModel: CameraViewModel) {
    val uiState          by viewModel.uiState.collectAsStateWithLifecycle()
    val autopilotActive  by viewModel.autopilotActive.collectAsStateWithLifecycle()
    val activeDirections by viewModel.activeDirections.collectAsStateWithLifecycle()
    val throttleValue    by viewModel.throttleValue.collectAsStateWithLifecycle()
    val latencyMs        by viewModel.latencyMs.collectAsStateWithLifecycle()
    val batteryPercent   by viewModel.batteryPercent.collectAsStateWithLifecycle()
    val host             by viewModel.host.collectAsStateWithLifecycle()
    val port             by viewModel.port.collectAsStateWithLifecycle()

    val piReachable     = uiState is CameraUiState.Streaming || uiState is CameraUiState.NoCamera
    val controlsEnabled = piReachable && !autopilotActive

    MaterialTheme {
        Surface(modifier = Modifier.fillMaxSize(), color = ScreenBg) {
            Row(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                // ── Panneau gauche : Virage (Gauche / Droite) ─────────────────
                ControlPanel(
                    modifier         = Modifier.width(110.dp).fillMaxHeight(),
                    title            = "Virage",
                    topDirection     = Direction.LEFT,
                    bottomDirection  = Direction.RIGHT,
                    activeDirections = activeDirections,
                    enabled          = controlsEnabled,
                    onPress          = viewModel::pressDirection,
                    onRelease        = viewModel::releaseDirection,
                )

                // ── Centre : Caméra + connexion + autopilote ──────────────────
                Column(
                    modifier             = Modifier.weight(1f).fillMaxHeight(),
                    verticalArrangement  = Arrangement.spacedBy(8.dp),
                ) {
                    ConnectionBar(
                        host           = host,
                        port           = port,
                        uiState        = uiState,
                        latencyMs      = latencyMs,
                        batteryPercent = batteryPercent,
                        onHostChange   = viewModel::updateHost,
                        onPortChange   = viewModel::updatePort,
                        onConnect      = viewModel::connect,
                        onDisconnect   = viewModel::disconnect,
                    )

                    AutopilotBar(
                        isActive = autopilotActive,
                        enabled  = piReachable,
                        onToggle = viewModel::toggleAutopilot,
                    )

                    CameraViewBox(
                        modifier = Modifier.weight(1f).fillMaxWidth(),
                        uiState  = uiState,
                        onRetry  = viewModel::retryAfterError,
                    )
                }

                // ── Panneau droit : Vitesse (slider Avant / Arrière) ──────────
                ThrottleSlider(
                    modifier      = Modifier.width(110.dp).fillMaxHeight(),
                    value         = throttleValue,
                    enabled       = controlsEnabled,
                    onValueChange = viewModel::setThrottle,
                    onRelease     = viewModel::releaseThrottle,
                )
            }
        }
    }
}

// ── Barre autopilote ──────────────────────────────────────────────────────────

@Composable
private fun AutopilotBar(
    isActive: Boolean,
    enabled:  Boolean,
    onToggle: () -> Unit,
) {
    val pulseAlpha = if (isActive) {
        val transition = rememberInfiniteTransition(label = "ap_pulse")
        transition.animateFloat(
            initialValue  = 1f,
            targetValue   = 0.35f,
            animationSpec = infiniteRepeatable(tween(700), RepeatMode.Reverse),
            label         = "ap_alpha",
        ).value
    } else 1f

    val tintColor   = if (isActive) AccentGreen.copy(alpha = pulseAlpha) else TextSecondary
    val borderColor = if (isActive) AccentGreen.copy(alpha = pulseAlpha) else ButtonBorder
    val bgColor     = if (isActive) AccentGreen.copy(alpha = 0.12f * pulseAlpha) else ButtonBg

    OutlinedButton(
        onClick        = onToggle,
        enabled        = enabled,
        modifier       = Modifier.fillMaxWidth().height(36.dp),
        border         = BorderStroke(1.5.dp, if (enabled) borderColor else ButtonBorder.copy(alpha = 0.4f)),
        colors         = ButtonDefaults.outlinedButtonColors(
            containerColor         = bgColor,
            contentColor           = tintColor,
            disabledContainerColor = ButtonBg,
            disabledContentColor   = TextSecondary.copy(alpha = 0.4f),
        ),
        contentPadding = PaddingValues(horizontal = 12.dp),
    ) {
        Icon(
            imageVector        = if (isActive) Icons.Default.Close else Icons.Default.PlayArrow,
            contentDescription = null,
            modifier           = Modifier.size(16.dp),
        )
        Spacer(Modifier.width(8.dp))
        Text(
            text       = if (isActive) "Annuler pilotage automatique" else "Pilotage automatique",
            fontWeight = FontWeight.Bold,
            fontSize   = 12.sp,
        )
    }
}

// ── Panneau de contrôle (gauche ou droite) ────────────────────────────────────

@Composable
private fun ControlPanel(
    modifier:         Modifier,
    title:            String,
    topDirection:     Direction,
    bottomDirection:  Direction,
    activeDirections: Set<Direction>,
    enabled:          Boolean,
    onPress:          (Direction) -> Unit,
    onRelease:        (Direction) -> Unit,
) {
    Column(
        modifier             = modifier
            .clip(RoundedCornerShape(16.dp))
            .background(PanelBg)
            .padding(6.dp),
        verticalArrangement  = Arrangement.spacedBy(6.dp),
        horizontalAlignment  = Alignment.CenterHorizontally,
    ) {
        Text(
            text          = title,
            color         = TextSecondary,
            fontSize      = 10.sp,
            fontWeight    = FontWeight.Medium,
            letterSpacing = 1.sp,
        )

        DirectionButton(
            direction = topDirection,
            isActive  = topDirection in activeDirections,
            enabled   = enabled,
            onPress   = onPress,
            onRelease = onRelease,
            modifier  = Modifier.weight(1f).fillMaxWidth(),
        )

        DirectionButton(
            direction = bottomDirection,
            isActive  = bottomDirection in activeDirections,
            enabled   = enabled,
            onPress   = onPress,
            onRelease = onRelease,
            modifier  = Modifier.weight(1f).fillMaxWidth(),
        )
    }
}

// ── Slider vertical Avant / Arrière (accélérateur proportionnel) ─────────────

@Composable
private fun ThrottleSlider(
    value:         Float,
    enabled:       Boolean,
    onValueChange: (Float) -> Unit,
    onRelease:     () -> Unit,
    modifier:      Modifier = Modifier,
) {
    val trackColor  = if (enabled) ButtonBg else ButtonBg.copy(alpha = 0.4f)
    val borderColor = if (enabled) ButtonBorder else ButtonBorder.copy(alpha = 0.3f)
    val thumbColor by animateColorAsState(
        targetValue = when {
            !enabled       -> TextSecondary.copy(alpha = 0.3f)
            value > 0.03f  -> AccentGreen
            value < -0.03f -> AccentRed
            else           -> AccentBlue
        },
        label = "throttle_thumb_color",
    )
    val percent = (value * 100f).roundToInt()

    Column(
        modifier             = modifier
            .clip(RoundedCornerShape(16.dp))
            .background(PanelBg)
            .padding(6.dp),
        horizontalAlignment  = Alignment.CenterHorizontally,
        verticalArrangement  = Arrangement.spacedBy(4.dp),
    ) {
        Text(
            text          = "Vitesse",
            color         = TextSecondary,
            fontSize      = 10.sp,
            fontWeight    = FontWeight.Medium,
            letterSpacing = 1.sp,
        )

        Icon(
            imageVector        = Icons.Default.KeyboardArrowUp,
            contentDescription = null,
            tint               = if (enabled) TextSecondary else TextSecondary.copy(alpha = 0.3f),
            modifier           = Modifier.size(16.dp),
        )

        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .clip(RoundedCornerShape(20.dp))
                .background(trackColor)
                .border(1.5.dp, borderColor, RoundedCornerShape(20.dp))
                .then(
                    if (enabled) Modifier.pointerInput(Unit) {
                        detectVerticalDragGestures(
                            onDragStart = { offset ->
                                val fraction = (1f - offset.y / size.height.toFloat()).coerceIn(0f, 1f)
                                onValueChange(fraction * 2f - 1f)
                            },
                            onVerticalDrag = { change, _ ->
                                change.consume()
                                val fraction = (1f - change.position.y / size.height.toFloat()).coerceIn(0f, 1f)
                                onValueChange(fraction * 2f - 1f)
                            },
                            onDragEnd    = { onRelease() },
                            onDragCancel = { onRelease() },
                        )
                    } else Modifier
                ),
        ) {
            // Ligne centrale = point neutre (throttle = 0)
            Box(
                modifier = Modifier
                    .align(Alignment.Center)
                    .fillMaxWidth(0.5f)
                    .height(1.dp)
                    .background(borderColor),
            )

            // Curseur — sa position verticale reflète directement value (-1..1)
            Box(
                modifier = Modifier
                    .align(BiasAlignment(horizontalBias = 0f, verticalBias = -value))
                    .padding(vertical = 3.dp)
                    .size(width = 46.dp, height = 30.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(thumbColor),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text       = "$percent",
                    color      = ScreenBg,
                    fontSize   = 12.sp,
                    fontWeight = FontWeight.Bold,
                )
            }
        }

        Icon(
            imageVector        = Icons.Default.KeyboardArrowDown,
            contentDescription = null,
            tint               = if (enabled) TextSecondary else TextSecondary.copy(alpha = 0.3f),
            modifier           = Modifier.size(16.dp),
        )

        Text(
            text     = if (value >= 0f) "Avant" else "Arrière",
            color    = TextSecondary,
            fontSize = 10.sp,
        )
    }
}

// ── Bouton de direction (press-and-hold) ──────────────────────────────────────

@Composable
private fun DirectionButton(
    direction: Direction,
    isActive:  Boolean,
    enabled:   Boolean,
    onPress:   (Direction) -> Unit,
    onRelease: (Direction) -> Unit,
    modifier:  Modifier = Modifier,
) {
    val effectiveActive = isActive && enabled
    val scale by animateFloatAsState(
        targetValue   = if (effectiveActive) 0.92f else 1f,
        animationSpec = spring(stiffness = Spring.StiffnessMediumLow),
        label         = "btn_scale",
    )
    val bgColor by animateColorAsState(
        targetValue = when {
            !enabled        -> ButtonBg.copy(alpha = 0.4f)
            effectiveActive -> ButtonActiveBg
            else            -> ButtonBg
        },
        label = "btn_bg",
    )
    val borderColor by animateColorAsState(
        targetValue = when {
            !enabled        -> ButtonBorder.copy(alpha = 0.3f)
            effectiveActive -> ButtonActiveBorder
            else            -> ButtonBorder
        },
        label = "btn_border",
    )
    val contentColor by animateColorAsState(
        targetValue = when {
            !enabled        -> TextSecondary.copy(alpha = 0.3f)
            effectiveActive -> AccentBlue
            else            -> TextSecondary
        },
        label = "btn_content",
    )

    Box(
        modifier = modifier
            .scale(scale)
            .border(1.5.dp, borderColor, RoundedCornerShape(14.dp))
            .clip(RoundedCornerShape(14.dp))
            .background(bgColor)
            .then(
                if (enabled) Modifier.pointerInput(direction) {
                    detectTapGestures(
                        onPress = {
                            onPress(direction)
                            tryAwaitRelease()
                            onRelease(direction)
                        },
                    )
                } else Modifier
            ),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Icon(
                imageVector        = direction.toIcon(),
                contentDescription = direction.label,
                tint               = contentColor,
                modifier           = Modifier.size(38.dp),
            )
            Text(
                text       = direction.label,
                color      = contentColor,
                fontSize   = 11.sp,
                fontWeight = if (effectiveActive) FontWeight.Bold else FontWeight.Normal,
            )
        }
    }
}

// ── Jauge réseau (3 barres + latence en ms) ───────────────────────────────────

/**
 * Indicateur de qualité réseau basé sur la latence HTTP vers le Pi.
 *   < 80 ms  → excellent  (3 barres vertes)
 *   80–200 ms → correct    (2 barres jaunes)
 *   > 200 ms  → mauvais    (1 barre rouge)
 *   null      → aucun signal (barres grises)
 */
@Composable
private fun SignalBars(latencyMs: Int?) {
    val (bars, barColor, label) = when {
        latencyMs == null    -> Triple(0, TextSecondary, "—")
        latencyMs < 80       -> Triple(3, AccentGreen,   "${latencyMs}ms")
        latencyMs < 200      -> Triple(2, AccentYellow,  "${latencyMs}ms")
        else                 -> Triple(1, AccentRed,     "${latencyMs}ms")
    }

    val heights = listOf(7.dp, 12.dp, 17.dp)

    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Row(
            verticalAlignment     = Alignment.Bottom,
            horizontalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            heights.forEachIndexed { i, h ->
                val filled  = i < bars
                val animate by animateColorAsState(
                    targetValue = if (filled) barColor else ButtonBorder,
                    label       = "bar_$i",
                )
                Box(
                    modifier = Modifier
                        .width(5.dp)
                        .height(h)
                        .clip(RoundedCornerShape(2.dp))
                        .background(animate),
                )
            }
        }
        Text(
            text     = label,
            color    = barColor,
            fontSize = 7.sp,
        )
    }
}

// ── Jauge batterie ────────────────────────────────────────────────────────────

/**
 * Icône batterie horizontale avec remplissage proportionnel au niveau.
 *   >= 50 % → vert
 *   20–49 % → jaune
 *   <  20 % → rouge (alerte)
 *   null    → gris (non disponible)
 */
@Composable
private fun BatteryGauge(percent: Int?) {
    val fillFraction = ((percent ?: 0) / 100f).coerceIn(0f, 1f)
    val fillColor by animateColorAsState(
        targetValue = when {
            percent == null  -> ButtonBorder
            percent >= 50    -> AccentGreen
            percent >= 20    -> AccentYellow
            else             -> AccentRed
        },
        label = "battery_color",
    )
    val label = if (percent != null) "$percent%" else "—"

    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        // Corps de la batterie
        Box(
            modifier = Modifier
                .width(26.dp)
                .height(13.dp),
        ) {
            // Contour
            Box(
                modifier = Modifier
                    .width(23.dp)
                    .fillMaxHeight()
                    .border(1.5.dp, fillColor, RoundedCornerShape(3.dp))
                    .clip(RoundedCornerShape(3.dp)),
            ) {
                // Remplissage
                Box(
                    modifier = Modifier
                        .fillMaxHeight()
                        .fillMaxWidth(fillFraction)
                        .background(fillColor.copy(alpha = 0.85f)),
                )
            }
            // Borne positive (petit rectangle à droite)
            Box(
                modifier = Modifier
                    .align(Alignment.CenterEnd)
                    .width(3.dp)
                    .height(6.dp)
                    .clip(RoundedCornerShape(topEnd = 2.dp, bottomEnd = 2.dp))
                    .background(fillColor),
            )
        }
        // Pourcentage
        Text(
            text     = label,
            color    = fillColor,
            fontSize = 7.sp,
        )
    }
}

// ── Barre de connexion (compacte, mode paysage) ───────────────────────────────

@Composable
private fun ConnectionBar(
    host:           String,
    port:           String,
    uiState:        CameraUiState,
    latencyMs:      Int?,
    batteryPercent: Int?,
    onHostChange:   (String) -> Unit,
    onPortChange:   (String) -> Unit,
    onConnect:      () -> Unit,
    onDisconnect:   () -> Unit,
) {
    val isStreaming  = uiState is CameraUiState.Streaming
    val isNoCamera   = uiState is CameraUiState.NoCamera
    val isConnecting = uiState is CameraUiState.Connecting
    val fieldsEnabled = !isStreaming && !isConnecting && !isNoCamera

    val statusColor = when (uiState) {
        is CameraUiState.Streaming  -> AccentGreen
        is CameraUiState.Connecting -> AccentYellow
        is CameraUiState.Error      -> AccentRed
        is CameraUiState.NoCamera   -> AccentOrange
        else                        -> TextSecondary
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(PanelBg)
            .padding(horizontal = 12.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment     = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .size(8.dp)
                .background(statusColor, CircleShape),
        )

        Text(
            text       = "Voiture RC",
            color      = TextPrimary,
            fontWeight = FontWeight.Bold,
            fontSize   = 13.sp,
        )

        Spacer(Modifier.width(4.dp))
        SignalBars(latencyMs = latencyMs)
        Spacer(Modifier.width(6.dp))
        BatteryGauge(percent = batteryPercent)
        Spacer(Modifier.width(2.dp))

        ConnectionTextField(
            modifier      = Modifier.weight(1f),
            value         = host,
            onValueChange = onHostChange,
            enabled       = fieldsEnabled,
            label         = "IP",
        )

        ConnectionTextField(
            modifier       = Modifier.width(88.dp),
            value          = port,
            onValueChange  = onPortChange,
            enabled        = fieldsEnabled,
            label          = "Port",
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        )

        when {
            isConnecting -> CircularProgressIndicator(
                modifier    = Modifier.size(28.dp),
                color       = AccentBlue,
                strokeWidth = 2.5.dp,
            )
            isStreaming || isNoCamera -> Button(
                onClick        = onDisconnect,
                colors         = ButtonDefaults.buttonColors(containerColor = Color(0xFF7F1D1D)),
                modifier       = Modifier.height(36.dp),
                contentPadding = PaddingValues(horizontal = 14.dp),
            ) {
                Text("Stop", fontSize = 12.sp)
            }
            else -> Button(
                onClick        = onConnect,
                colors         = ButtonDefaults.buttonColors(containerColor = AccentBlue),
                modifier       = Modifier.height(36.dp),
                contentPadding = PaddingValues(horizontal = 14.dp),
            ) {
                Text("Connecter", fontSize = 12.sp, color = ScreenBg)
            }
        }
    }
}

@Composable
private fun ConnectionTextField(
    value:           String,
    onValueChange:   (String) -> Unit,
    label:           String,
    enabled:         Boolean,
    modifier:        Modifier = Modifier,
    keyboardOptions: KeyboardOptions = KeyboardOptions.Default,
) {
    var isFocused by remember { mutableStateOf(false) }

    val borderColor = when {
        !enabled  -> Color(0xFF1A2030)
        isFocused -> AccentBlue
        else      -> ButtonBorder
    }
    val labelColor  = if (isFocused) AccentBlue else TextSecondary
    val textColor   = if (enabled) TextPrimary else TextSecondary

    Box(modifier = modifier) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(42.dp)
                .border(1.dp, borderColor, RoundedCornerShape(8.dp))
                .padding(horizontal = 10.dp),
            contentAlignment = Alignment.CenterStart,
        ) {
            BasicTextField(
                value          = value,
                onValueChange  = onValueChange,
                enabled        = enabled,
                singleLine     = true,
                textStyle      = TextStyle(
                    color      = textColor,
                    fontSize   = 13.sp,
                    lineHeight = 18.sp,
                ),
                keyboardOptions = keyboardOptions,
                cursorBrush    = SolidColor(AccentBlue),
                modifier       = Modifier
                    .fillMaxWidth()
                    .onFocusChanged { isFocused = it.isFocused },
            )
        }

        Text(
            text     = label,
            color    = labelColor,
            fontSize = 9.sp,
            modifier = Modifier
                .align(Alignment.TopStart)
                .padding(start = 10.dp, top = 2.dp),
        )
    }
}

// ── Zone caméra ───────────────────────────────────────────────────────────────

@Composable
private fun CameraViewBox(
    modifier: Modifier,
    uiState:  CameraUiState,
    onRetry:  () -> Unit,
) {
    Box(
        modifier         = modifier
            .clip(RoundedCornerShape(16.dp))
            .background(CameraBg)
            .border(1.dp, ButtonBorder, RoundedCornerShape(16.dp)),
        contentAlignment = Alignment.Center,
    ) {
        when (uiState) {
            CameraUiState.Idle       -> CameraOffOverlay()
            CameraUiState.Connecting -> ConnectingOverlay()
            CameraUiState.NoCamera   -> NoCameraOverlay(onRetry = onRetry)
            is CameraUiState.Streaming -> StreamingView(state = uiState)
            is CameraUiState.Error   -> ErrorOverlay(message = uiState.message, onRetry = onRetry)
        }
    }
}

// ── Overlay : caméra non connectée (état Idle) ────────────────────────────────

@Composable
private fun CameraOffOverlay() {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(10.dp),
        modifier            = Modifier.padding(24.dp),
    ) {
        Box(
            modifier         = Modifier
                .size(72.dp)
                .background(Color(0xFF1A2030), CircleShape)
                .border(2.dp, ButtonBorder, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Box(
                modifier         = Modifier
                    .size(44.dp)
                    .background(Color(0xFF252D40), CircleShape)
                    .border(1.dp, ButtonBorder, CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                Box(
                    modifier = Modifier
                        .size(24.dp)
                        .background(Color(0xFF0A0B0E), CircleShape),
                )
            }
        }

        Text(
            text      = "Caméra non connectée",
            color     = TextSecondary,
            fontSize  = 14.sp,
            fontWeight = FontWeight.Medium,
            textAlign = TextAlign.Center,
        )
        Text(
            text      = "Entrez l'adresse IP du Raspberry Pi\npuis appuyez sur Connecter",
            color     = TextSecondary.copy(alpha = 0.5f),
            fontSize  = 11.sp,
            textAlign = TextAlign.Center,
            lineHeight = 16.sp,
        )
    }
}

// ── Overlay : Pi connecté mais caméra absente (NoCamera) ─────────────────────

@Composable
private fun NoCameraOverlay(onRetry: () -> Unit) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(12.dp),
        modifier            = Modifier.padding(24.dp),
    ) {
        Icon(
            imageVector        = Icons.Default.Warning,
            contentDescription = null,
            tint               = AccentOrange,
            modifier           = Modifier.size(52.dp),
        )
        Text(
            text       = "Caméra non connectée",
            color      = AccentOrange,
            fontWeight = FontWeight.Bold,
            fontSize   = 15.sp,
            textAlign  = TextAlign.Center,
        )
        Text(
            text      = "Le Raspberry Pi est joignable.\nLe pilotage reste disponible.",
            color     = TextSecondary,
            fontSize  = 12.sp,
            textAlign = TextAlign.Center,
        )
        OutlinedButton(
            onClick = onRetry,
            border  = BorderStroke(1.dp, AccentOrange),
        ) {
            Icon(Icons.Default.Refresh, null, tint = AccentOrange, modifier = Modifier.size(16.dp))
            Spacer(Modifier.width(6.dp))
            Text("Réessayer", color = AccentOrange, fontSize = 13.sp)
        }
    }
}

// ── Overlay : connexion en cours ─────────────────────────────────────────────

@Composable
private fun ConnectingOverlay() {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        CircularProgressIndicator(color = AccentBlue)
        Text("Connexion au flux /video…", color = TextSecondary, fontSize = 13.sp)
    }
}

// ── Overlay : erreur ─────────────────────────────────────────────────────────

@Composable
private fun ErrorOverlay(message: String, onRetry: () -> Unit) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(12.dp),
        modifier            = Modifier.padding(24.dp),
    ) {
        Text(
            text       = "Connexion perdue",
            color      = AccentRed,
            fontWeight = FontWeight.Bold,
            fontSize   = 15.sp,
        )
        Text(
            text      = message,
            color     = TextSecondary,
            fontSize  = 12.sp,
            textAlign = TextAlign.Center,
        )
        OutlinedButton(
            onClick = onRetry,
            border  = BorderStroke(1.dp, AccentBlue),
        ) {
            Icon(Icons.Default.Refresh, null, tint = AccentBlue, modifier = Modifier.size(16.dp))
            Spacer(Modifier.width(6.dp))
            Text("Réessayer", color = AccentBlue, fontSize = 13.sp)
        }
    }
}

// ── Vue flux en direct ────────────────────────────────────────────────────────

@Composable
private fun StreamingView(state: CameraUiState.Streaming) {
    val bitmap by produceState<ImageBitmap?>(initialValue = null, state.frame) {
        value = withContext(Dispatchers.Default) {
            BitmapFactory.decodeByteArray(state.frame, 0, state.frame.size)?.asImageBitmap()
        }
    }

    val resolvedBitmap = bitmap ?: return

    Box(modifier = Modifier.fillMaxSize()) {
        Image(
            bitmap             = resolvedBitmap,
            contentDescription = "Flux caméra en direct",
            modifier           = Modifier.fillMaxSize(),
            contentScale       = ContentScale.Fit,
        )
        StreamInfoOverlay(resolution = state.resolution, fps = state.fps)
    }
}

@Composable
private fun StreamInfoOverlay(resolution: String?, fps: Int?) {
    if (resolution == null && fps == null) return

    Box(
        modifier         = Modifier.fillMaxSize().padding(10.dp),
        contentAlignment = Alignment.BottomStart,
    ) {
        Row(
            modifier = Modifier
                .background(OverlayBg, RoundedCornerShape(6.dp))
                .padding(horizontal = 8.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment     = Alignment.CenterVertically,
        ) {
            Box(modifier = Modifier.size(6.dp).background(AccentGreen, CircleShape))
            if (resolution != null) Text(resolution, color = TextPrimary, fontSize = 10.sp)
            if (fps != null) Text("$fps fps", color = AccentGreen, fontSize = 10.sp, fontWeight = FontWeight.Bold)
        }
    }
}

// ── Mapping Direction → icône ─────────────────────────────────────────────────

private fun Direction.toIcon(): ImageVector = when (this) {
    Direction.FORWARD  -> Icons.Default.KeyboardArrowUp
    Direction.BACKWARD -> Icons.Default.KeyboardArrowDown
    Direction.LEFT     -> Icons.AutoMirrored.Filled.KeyboardArrowLeft
    Direction.RIGHT    -> Icons.AutoMirrored.Filled.KeyboardArrowRight
}
