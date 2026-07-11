package com.tpi.mobile.ui

import android.graphics.BitmapFactory
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.gestures.detectTapGestures
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
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowLeft
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
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
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.focus.onFocusChanged
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.tpi.mobile.camera.CameraUiState
import com.tpi.mobile.camera.CameraViewModel
import com.tpi.mobile.camera.Direction
import com.tpi.mobile.camera.TurnSignal
import com.tpi.mobile.ui.theme.MobileTheme
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

// ── Design tokens ────────────────────────────────────────────────────────────

private val ScreenBg = Color(0xFF0A0B0E)
private val PanelBg = Color(0xFF12161F)
private val ButtonBg = Color(0xFF1A2030)
private val ButtonActiveBg = Color(0xFF0D2550)
private val ButtonBorder = Color(0xFF252D40)
private val ButtonActiveBorder = Color(0xFF3D7EFF)
private val AccentBlue = Color(0xFF3D7EFF)
private val AccentGreen = Color(0xFF34D399)
private val AccentYellow = Color(0xFFFBBF24)
private val AccentRed = Color(0xFFFF6B6B)
private val CameraBg = Color(0xFF050607)
private val TextPrimary = Color.White
private val TextSecondary = Color(0xFF7A8899)
private val OverlayBg = Color(0xBB000000)

// ── Root screen ──────────────────────────────────────────────────────────────

@Composable
fun RcCameraScreen(viewModel: CameraViewModel) {
    val cameraState by viewModel.cameraState.collectAsStateWithLifecycle()
    val activeDirections by viewModel.activeDirections.collectAsStateWithLifecycle()
    val activeTurnSignal by viewModel.activeTurnSignal.collectAsStateWithLifecycle()
    val host by viewModel.host.collectAsStateWithLifecycle()
    val port by viewModel.port.collectAsStateWithLifecycle()

    MobileTheme(darkTheme = true, dynamicColor = false) {
        Surface(
            modifier = Modifier.fillMaxSize(),
            color = ScreenBg,
        ) {
            Row(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                // ── Panneau gauche : Virage (Gauche / Droite) ────────────────
                ControlPanel(
                    modifier = Modifier
                        .width(110.dp)
                        .fillMaxHeight(),
                    title = "Virage",
                    topDirection = Direction.LEFT,
                    bottomDirection = Direction.RIGHT,
                    activeDirections = activeDirections,
                    onPress = viewModel::pressDirection,
                    onRelease = viewModel::releaseDirection,
                )

                // ── Centre : Caméra + barre de connexion ─────────────────────
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .fillMaxHeight(),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    ConnectionBar(
                        host = host,
                        port = port,
                        cameraState = cameraState,
                        onHostChange = viewModel::updateHost,
                        onPortChange = viewModel::updatePort,
                        onConnect = viewModel::connect,
                        onDisconnect = viewModel::disconnect,
                    )

                    BlinkerBar(
                        activeTurnSignal = activeTurnSignal,
                        onToggle = viewModel::toggleTurnSignal,
                    )

                    CameraViewBox(
                        modifier = Modifier
                            .weight(1f)
                            .fillMaxWidth(),
                        cameraState = cameraState,
                        onRetry = viewModel::retryAfterError,
                    )
                }

                // ── Panneau droit : Vitesse (Avant / Arrière) ────────────────
                ControlPanel(
                    modifier = Modifier
                        .width(110.dp)
                        .fillMaxHeight(),
                    title = "Vitesse",
                    topDirection = Direction.FORWARD,
                    bottomDirection = Direction.BACKWARD,
                    activeDirections = activeDirections,
                    onPress = viewModel::pressDirection,
                    onRelease = viewModel::releaseDirection,
                )
            }
        }
    }
}

// ── Barre clignotants (sous le header connexion) ────────────────────────────

@Composable
private fun BlinkerBar(
    activeTurnSignal: TurnSignal?,
    onToggle: (TurnSignal) -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        BlinkerButton(
            signal = TurnSignal.LEFT,
            isActive = activeTurnSignal == TurnSignal.LEFT,
            onClick = { onToggle(TurnSignal.LEFT) },
        )
        BlinkerButton(
            signal = TurnSignal.RIGHT,
            isActive = activeTurnSignal == TurnSignal.RIGHT,
            onClick = { onToggle(TurnSignal.RIGHT) },
        )
    }
}

@Composable
private fun BlinkerButton(
    signal: TurnSignal,
    isActive: Boolean,
    onClick: () -> Unit,
) {
    val blinkAlpha = if (isActive) {
        val transition = rememberInfiniteTransition(label = "blinker_alpha")
        transition.animateFloat(
            initialValue = 1f,
            targetValue = 0.25f,
            animationSpec = infiniteRepeatable(
                animation = tween(durationMillis = 500),
                repeatMode = RepeatMode.Reverse,
            ),
            label = "blinker_blink",
        ).value
    } else {
        1f
    }

    val bgColor = if (isActive) AccentYellow.copy(alpha = 0.18f * blinkAlpha + 0.08f) else ButtonBg
    val borderColor = if (isActive) AccentYellow.copy(alpha = blinkAlpha) else ButtonBorder
    val contentColor = if (isActive) AccentYellow.copy(alpha = blinkAlpha) else TextSecondary

    OutlinedButton(
        onClick = onClick,
        modifier = Modifier.height(34.dp),
        border = BorderStroke(1.5.dp, borderColor),
        colors = ButtonDefaults.outlinedButtonColors(
            containerColor = bgColor,
            contentColor = contentColor,
        ),
        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 0.dp),
    ) {
        Icon(
            imageVector = signal.toIcon(),
            contentDescription = signal.label,
            tint = contentColor,
            modifier = Modifier.size(18.dp),
        )
        Spacer(Modifier.width(6.dp))
        Text(
            text = if (signal == TurnSignal.LEFT) "Clign. G" else "Clign. D",
            fontSize = 11.sp,
            fontWeight = if (isActive) FontWeight.Bold else FontWeight.Normal,
        )
    }
}

// ── Panneau de contrôle (gauche ou droite) ────────────────────────────────────

@Composable
private fun ControlPanel(
    modifier: Modifier,
    title: String,
    topDirection: Direction,
    bottomDirection: Direction,
    activeDirections: Set<Direction>,
    onPress: (Direction) -> Unit,
    onRelease: (Direction) -> Unit,
) {
    Column(
        modifier = modifier
            .clip(RoundedCornerShape(16.dp))
            .background(PanelBg)
            .padding(6.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text(
            text = title,
            color = TextSecondary,
            fontSize = 10.sp,
            fontWeight = FontWeight.Medium,
            letterSpacing = 1.sp,
        )

        DirectionButton(
            direction = topDirection,
            isActive = topDirection in activeDirections,
            onPress = onPress,
            onRelease = onRelease,
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
        )

        DirectionButton(
            direction = bottomDirection,
            isActive = bottomDirection in activeDirections,
            onPress = onPress,
            onRelease = onRelease,
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth(),
        )
    }
}

// ── Bouton de direction (press-and-hold) ─────────────────────────────────────

@Composable
private fun DirectionButton(
    direction: Direction,
    isActive: Boolean,
    onPress: (Direction) -> Unit,
    onRelease: (Direction) -> Unit,
    modifier: Modifier = Modifier,
) {
    val scale by animateFloatAsState(
        targetValue = if (isActive) 0.92f else 1f,
        animationSpec = spring(stiffness = Spring.StiffnessMediumLow),
        label = "button_scale",
    )
    val bgColor by animateColorAsState(
        targetValue = if (isActive) ButtonActiveBg else ButtonBg,
        label = "button_bg",
    )
    val borderColor by animateColorAsState(
        targetValue = if (isActive) ButtonActiveBorder else ButtonBorder,
        label = "button_border",
    )
    val contentColor by animateColorAsState(
        targetValue = if (isActive) AccentBlue else TextSecondary,
        label = "button_content",
    )

    Box(
        modifier = modifier
            .scale(scale)
            .border(1.5.dp, borderColor, RoundedCornerShape(14.dp))
            .clip(RoundedCornerShape(14.dp))
            .background(bgColor)
            .pointerInput(direction) {
                detectTapGestures(
                    onPress = {
                        onPress(direction)
                        tryAwaitRelease()
                        onRelease(direction)
                    },
                )
            },
        contentAlignment = Alignment.Center,
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Icon(
                imageVector = direction.toIcon(),
                contentDescription = direction.label,
                tint = contentColor,
                modifier = Modifier.size(38.dp),
            )
            Text(
                text = direction.label,
                color = contentColor,
                fontSize = 11.sp,
                fontWeight = if (isActive) FontWeight.Bold else FontWeight.Normal,
            )
        }
    }
}

// ── Barre de connexion (compacte pour le mode paysage) ───────────────────────

@Composable
private fun ConnectionTextField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    enabled: Boolean,
    modifier: Modifier = Modifier,
    keyboardOptions: KeyboardOptions = KeyboardOptions.Default,
) {
    var isFocused by remember { mutableStateOf(false) }

    val borderColor = when {
        !enabled -> Color(0xFF1A2030)
        isFocused -> AccentBlue
        else -> ButtonBorder
    }
    val labelColor = when {
        !enabled -> TextSecondary
        isFocused -> AccentBlue
        else -> TextSecondary
    }
    val textColor = if (enabled) TextPrimary else TextSecondary

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
                value = value,
                onValueChange = onValueChange,
                enabled = enabled,
                singleLine = true,
                textStyle = TextStyle(
                    color = textColor,
                    fontSize = 13.sp,
                    lineHeight = 18.sp,
                ),
                keyboardOptions = keyboardOptions,
                cursorBrush = SolidColor(AccentBlue),
                modifier = Modifier
                    .fillMaxWidth()
                    .onFocusChanged { isFocused = it.isFocused },
            )
        }

        Text(
            text = label,
            color = labelColor,
            fontSize = 9.sp,
            modifier = Modifier
                .align(Alignment.TopStart)
                .offset(x = 8.dp, y = (-6).dp)
                .background(PanelBg)
                .padding(horizontal = 4.dp),
        )
    }
}

@Composable
private fun ConnectionBar(
    host: String,
    port: String,
    cameraState: CameraUiState,
    onHostChange: (String) -> Unit,
    onPortChange: (String) -> Unit,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
) {
    val isStreaming = cameraState is CameraUiState.Streaming
    val isConnecting = cameraState is CameraUiState.Connecting
    val fieldsEnabled = !isStreaming && !isConnecting

    val statusColor = when (cameraState) {
        is CameraUiState.Streaming -> AccentGreen
        is CameraUiState.Connecting -> AccentYellow
        is CameraUiState.Error -> AccentRed
        else -> TextSecondary
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .background(PanelBg)
            .padding(horizontal = 12.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        // Indicateur de statut
        Box(
            modifier = Modifier
                .size(8.dp)
                .background(statusColor, CircleShape),
        )

        Text(
            text = "RC Camera",
            color = TextPrimary,
            fontWeight = FontWeight.Bold,
            fontSize = 13.sp,
        )

        Spacer(Modifier.width(2.dp))

        ConnectionTextField(
            modifier = Modifier.weight(1f),
            value = host,
            onValueChange = onHostChange,
            enabled = fieldsEnabled,
            label = "IP",
        )

        ConnectionTextField(
            modifier = Modifier.width(88.dp),
            value = port,
            onValueChange = onPortChange,
            enabled = fieldsEnabled,
            label = "Port",
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        )

        when {
            isConnecting -> CircularProgressIndicator(
                modifier = Modifier.size(28.dp),
                color = AccentBlue,
                strokeWidth = 2.5.dp,
            )
            isStreaming -> Button(
                onClick = onDisconnect,
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF7F1D1D)),
                modifier = Modifier.height(36.dp),
                contentPadding = PaddingValues(horizontal = 14.dp),
            ) {
                Text("Stop", fontSize = 12.sp)
            }
            else -> Button(
                onClick = onConnect,
                colors = ButtonDefaults.buttonColors(containerColor = AccentBlue),
                modifier = Modifier.height(36.dp),
                contentPadding = PaddingValues(horizontal = 14.dp),
            ) {
                Text("Connecter", fontSize = 12.sp, color = ScreenBg)
            }
        }
    }
}

// ── Zone caméra ───────────────────────────────────────────────────────────────

@Composable
private fun CameraViewBox(
    modifier: Modifier,
    cameraState: CameraUiState,
    onRetry: () -> Unit,
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(16.dp))
            .background(CameraBg)
            .border(1.dp, ButtonBorder, RoundedCornerShape(16.dp)),
        contentAlignment = Alignment.Center,
    ) {
        when (cameraState) {
            CameraUiState.Idle -> CameraOffOverlay()
            CameraUiState.Connecting -> ConnectingOverlay()
            is CameraUiState.Streaming -> StreamingView(state = cameraState)
            is CameraUiState.Error -> ErrorOverlay(message = cameraState.message, onRetry = onRetry)
        }
    }
}

// ── Overlay : caméra non connectée ───────────────────────────────────────────

@Composable
private fun CameraOffOverlay() {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(10.dp),
        modifier = Modifier.padding(24.dp),
    ) {
        // Icône caméra "éteinte" dessinée avec des cercles et un fond
        Box(
            modifier = Modifier
                .size(72.dp)
                .background(Color(0xFF1A2030), CircleShape)
                .border(2.dp, ButtonBorder, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            // Cercle extérieur de l'objectif
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .background(Color(0xFF252D40), CircleShape)
                    .border(1.dp, ButtonBorder, CircleShape),
                contentAlignment = Alignment.Center,
            ) {
                // Cercle intérieur
                Box(
                    modifier = Modifier
                        .size(24.dp)
                        .background(Color(0xFF0A0B0E), CircleShape),
                )
            }
        }

        Text(
            text = "Caméra non connectée",
            color = TextSecondary,
            fontSize = 14.sp,
            fontWeight = FontWeight.Medium,
            textAlign = TextAlign.Center,
        )
        Text(
            text = "Entrez l'adresse IP du Raspberry Pi\npuis appuyez sur Connecter",
            color = TextSecondary.copy(alpha = 0.5f),
            fontSize = 11.sp,
            textAlign = TextAlign.Center,
            lineHeight = 16.sp,
        )
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
        modifier = Modifier.padding(24.dp),
    ) {
        Text(
            text = "Connexion perdue",
            color = AccentRed,
            fontWeight = FontWeight.Bold,
            fontSize = 15.sp,
        )
        Text(
            text = message,
            color = TextSecondary,
            fontSize = 12.sp,
            textAlign = TextAlign.Center,
        )
        OutlinedButton(
            onClick = onRetry,
            border = BorderStroke(1.dp, AccentBlue),
        ) {
            Icon(
                Icons.Default.Refresh,
                contentDescription = null,
                tint = AccentBlue,
                modifier = Modifier.size(16.dp),
            )
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
            bitmap = resolvedBitmap,
            contentDescription = "Flux caméra en direct",
            modifier = Modifier.fillMaxSize(),
            contentScale = ContentScale.Fit,
        )

        StreamInfoOverlay(resolution = state.resolution, fps = state.fps)
    }
}

// ── Overlay info (résolution / fps) ──────────────────────────────────────────

@Composable
private fun StreamInfoOverlay(resolution: String?, fps: Int?) {
    if (resolution == null && fps == null) return

    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(10.dp),
        contentAlignment = Alignment.BottomStart,
    ) {
        Row(
            modifier = Modifier
                .background(OverlayBg, RoundedCornerShape(6.dp))
                .padding(horizontal = 8.dp, vertical = 4.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                modifier = Modifier
                    .size(6.dp)
                    .background(AccentGreen, CircleShape),
            )
            if (resolution != null) {
                Text(resolution, color = TextPrimary, fontSize = 10.sp)
            }
            if (fps != null) {
                Text("$fps fps", color = AccentGreen, fontSize = 10.sp, fontWeight = FontWeight.Bold)
            }
        }
    }
}

// ── Mapping Direction → icône Material ───────────────────────────────────────

private fun Direction.toIcon(): ImageVector = when (this) {
    Direction.FORWARD -> Icons.Default.KeyboardArrowUp
    Direction.BACKWARD -> Icons.Default.KeyboardArrowDown
    Direction.LEFT -> Icons.AutoMirrored.Filled.KeyboardArrowLeft
    Direction.RIGHT -> Icons.AutoMirrored.Filled.KeyboardArrowRight
    Direction.STOP -> Icons.Default.KeyboardArrowUp
}

private fun TurnSignal.toIcon(): ImageVector = when (this) {
    TurnSignal.LEFT -> Icons.AutoMirrored.Filled.KeyboardArrowLeft
    TurnSignal.RIGHT -> Icons.AutoMirrored.Filled.KeyboardArrowRight
}
