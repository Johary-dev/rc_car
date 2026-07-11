package com.tpi.rccamera.ui

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.tpi.rccamera.camera.CameraUiState
import com.tpi.rccamera.camera.CameraViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

private val BackgroundColor = Color(0xFF111111)
private val SurfaceDarkColor = Color(0xFF1E1E1E)
private val TextPrimaryColor = Color.White
private val TextSecondaryColor = Color(0xFFCCCCCC)
private val BorderActiveColor = Color(0xFF5C9EFF)
private val BorderInactiveColor = Color(0xFF555555)
private val OverlayBackgroundColor = Color(0xCC000000)
private val ErrorColor = Color(0xFFFF5252)

@Composable
fun CameraScreen(viewModel: CameraViewModel) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val host by viewModel.host.collectAsStateWithLifecycle()
    val port by viewModel.port.collectAsStateWithLifecycle()

    MaterialTheme {
        Surface(
            modifier = Modifier.fillMaxSize(),
            color = BackgroundColor,
        ) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text(
                    text = "Flux caméra Raspberry Pi",
                    color = TextPrimaryColor,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.headlineSmall,
                )

                ConnectionPanel(
                    host = host,
                    port = port,
                    uiState = uiState,
                    onHostChange = viewModel::updateHost,
                    onPortChange = viewModel::updatePort,
                    onConnect = viewModel::connect,
                    onDisconnect = viewModel::disconnect,
                )

                StreamPanel(
                    uiState = uiState,
                    onRetry = viewModel::retryAfterError,
                )
            }
        }
    }
}

@Composable
private fun ConnectionPanel(
    host: String,
    port: String,
    uiState: CameraUiState,
    onHostChange: (String) -> Unit,
    onPortChange: (String) -> Unit,
    onConnect: () -> Unit,
    onDisconnect: () -> Unit,
) {
    val fieldsEnabled = uiState is CameraUiState.Idle || uiState is CameraUiState.Error
    val isStreaming = uiState is CameraUiState.Streaming
    val isConnecting = uiState is CameraUiState.Connecting

    val textFieldColors = OutlinedTextFieldDefaults.colors(
        focusedTextColor = TextPrimaryColor,
        unfocusedTextColor = TextPrimaryColor,
        disabledTextColor = BorderInactiveColor,
        focusedLabelColor = BorderActiveColor,
        unfocusedLabelColor = TextSecondaryColor,
        disabledLabelColor = BorderInactiveColor,
        focusedBorderColor = BorderActiveColor,
        unfocusedBorderColor = BorderInactiveColor,
        disabledBorderColor = Color(0xFF333333),
        cursorColor = BorderActiveColor,
    )

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        OutlinedTextField(
            modifier = Modifier.weight(1f),
            value = host,
            onValueChange = onHostChange,
            enabled = fieldsEnabled,
            label = { Text("IP Raspberry Pi") },
            singleLine = true,
            colors = textFieldColors,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
        )

        OutlinedTextField(
            modifier = Modifier.width(120.dp),
            value = port,
            onValueChange = onPortChange,
            enabled = fieldsEnabled,
            label = { Text("Port") },
            singleLine = true,
            colors = textFieldColors,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        )

        when {
            isConnecting -> {
                CircularProgressIndicator(
                    modifier = Modifier.size(36.dp),
                    color = BorderActiveColor,
                    strokeWidth = 3.dp,
                )
            }
            isStreaming -> {
                Button(onClick = onDisconnect) {
                    Text("Arrêter")
                }
            }
            else -> {
                Button(onClick = onConnect) {
                    Text("Connecter")
                }
            }
        }
    }
}

@Composable
private fun StreamPanel(
    uiState: CameraUiState,
    onRetry: () -> Unit,
) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.Black, RoundedCornerShape(12.dp)),
        contentAlignment = Alignment.Center,
    ) {
        when (uiState) {
            CameraUiState.Idle -> {
                PlaceholderText("Entrez l'IP du Raspberry Pi puis appuyez sur Connecter.")
            }

            CameraUiState.Connecting -> {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    CircularProgressIndicator(color = Color.White)
                    Spacer(modifier = Modifier.height(12.dp))
                    Text("Connexion au flux /video…", color = TextSecondaryColor)
                }
            }

            is CameraUiState.Streaming -> {
                StreamingContent(state = uiState)
            }

            is CameraUiState.Error -> {
                ErrorContent(message = uiState.message, onRetry = onRetry)
            }
        }
    }
}

@Composable
private fun StreamingContent(state: CameraUiState.Streaming) {
    val bitmap by produceState<ImageBitmap?>(initialValue = null, state.frame) {
        value = withContext(Dispatchers.Default) {
            BitmapFactory.decodeByteArray(state.frame, 0, state.frame.size)?.asImageBitmap()
        }
    }

    val resolvedBitmap = bitmap ?: return

    Image(
        bitmap = resolvedBitmap,
        contentDescription = "Flux caméra en direct",
        modifier = Modifier.fillMaxSize(),
        contentScale = ContentScale.Fit,
    )

    StreamInfoOverlay(resolution = state.resolution, fps = state.fps)
}

@Composable
private fun ErrorContent(message: String, onRetry: () -> Unit) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(16.dp),
        modifier = Modifier.padding(24.dp),
    ) {
        Text(
            text = "Erreur de connexion",
            color = ErrorColor,
            fontWeight = FontWeight.Bold,
            style = MaterialTheme.typography.titleMedium,
        )
        Text(
            text = message,
            color = TextSecondaryColor,
            fontSize = 14.sp,
        )
        OutlinedButton(
            onClick = onRetry,
            border = androidx.compose.foundation.BorderStroke(1.dp, BorderActiveColor),
        ) {
            Text("Réessayer", color = BorderActiveColor)
        }
    }
}

@Composable
private fun StreamInfoOverlay(resolution: String?, fps: Int?) {
    if (resolution == null && fps == null) return

    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(12.dp),
        contentAlignment = Alignment.BottomStart,
    ) {
        Text(
            text = buildString {
                if (resolution != null) append(resolution)
                if (fps != null) {
                    if (isNotEmpty()) append(" • ")
                    append("$fps fps")
                }
            },
            color = Color.White,
            fontSize = 12.sp,
            modifier = Modifier
                .background(OverlayBackgroundColor, RoundedCornerShape(8.dp))
                .padding(horizontal = 10.dp, vertical = 6.dp),
        )
    }
}

@Composable
private fun PlaceholderText(message: String) {
    Text(
        text = message,
        color = TextSecondaryColor,
        modifier = Modifier.padding(24.dp),
    )
}
