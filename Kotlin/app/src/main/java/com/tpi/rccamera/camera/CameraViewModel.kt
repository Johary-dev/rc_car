package com.tpi.rccamera.camera

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.tpi.rccamera.BuildConfig
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * ViewModel gérant la connexion au flux MJPEG du Raspberry Pi.
 *
 * Le constructeur sans paramètre est intentionnel : il permet l'instanciation
 * via [androidx.activity.viewModels] sans factory explicite.
 */
class CameraViewModel : ViewModel() {

    private val repository = CameraRepository()
    private var streamJob: Job? = null

    private val _uiState = MutableStateFlow<CameraUiState>(CameraUiState.Idle)
    val uiState: StateFlow<CameraUiState> = _uiState.asStateFlow()

    private val _host = MutableStateFlow(BuildConfig.DEFAULT_RASPBERRY_HOST)
    val host: StateFlow<String> = _host.asStateFlow()

    private val _port = MutableStateFlow(BuildConfig.DEFAULT_RASPBERRY_PORT.toString())
    val port: StateFlow<String> = _port.asStateFlow()

    // --- UI events ----------------------------------------------------------

    fun updateHost(value: String) {
        _host.value = value.trim()
    }

    fun updatePort(value: String) {
        _port.value = value.filter { it.isDigit() }.take(5)
    }

    fun connect() {
        val config = buildConfig() ?: run {
            _uiState.value = CameraUiState.Error("Adresse ou port invalide")
            return
        }

        disconnect()
        _uiState.value = CameraUiState.Connecting

        streamJob = viewModelScope.launch {
            try {
                val status = runCatching { repository.fetchStatus(config) }.getOrNull()

                repository.stream(config) { frameBytes ->
                    withContext(Dispatchers.Main.immediate) {
                        _uiState.value = CameraUiState.Streaming(
                            frame = frameBytes,
                            resolution = status?.resolution,
                            fps = status?.fps,
                        )
                    }
                }

                // Le flux s'est terminé normalement
                if (_uiState.value !is CameraUiState.Error) {
                    _uiState.value = CameraUiState.Idle
                }
            } catch (_: CancellationException) {
                // Déconnexion volontaire — ne pas changer l'état ici,
                // disconnect() positionne déjà Idle.
            } catch (error: Exception) {
                _uiState.value = CameraUiState.Error(
                    error.message ?: "Impossible de se connecter au flux caméra",
                )
            }
        }
    }

    fun disconnect() {
        streamJob?.cancel()
        streamJob = null
        _uiState.value = CameraUiState.Idle
    }

    fun retryAfterError() {
        if (_uiState.value is CameraUiState.Error) {
            connect()
        }
    }

    override fun onCleared() {
        disconnect()
        super.onCleared()
    }

    // --- Helpers ------------------------------------------------------------

    private fun buildConfig(): CameraConnectionConfig? {
        val trimmedHost = _host.value.trim()
        if (trimmedHost.isEmpty()) return null

        val parsedPort = _port.value.toIntOrNull() ?: return null
        if (parsedPort !in 1..65535) return null

        return CameraConnectionConfig(host = trimmedHost, port = parsedPort)
    }
}
