package com.tpi.mobile.camera

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.tpi.mobile.BuildConfig
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

class CameraViewModel : ViewModel() {

    private val cameraRepository = CameraRepository()
    private val directionRepository = DirectionRepository()
    private var streamJob: Job? = null

    // --- Camera state -------------------------------------------------------

    private val _cameraState = MutableStateFlow<CameraUiState>(CameraUiState.Idle)
    val cameraState: StateFlow<CameraUiState> = _cameraState.asStateFlow()

    // --- Direction state ----------------------------------------------------

    /** Boutons actuellement maintenus (plusieurs directions possibles en même temps). */
    private val _activeDirections = MutableStateFlow<Set<Direction>>(emptySet())
    val activeDirections: StateFlow<Set<Direction>> = _activeDirections.asStateFlow()

    /** Clignotant actif (gauche ou droite), null si aucun. */
    private val _activeTurnSignal = MutableStateFlow<TurnSignal?>(null)
    val activeTurnSignal: StateFlow<TurnSignal?> = _activeTurnSignal.asStateFlow()

    // --- Connection config --------------------------------------------------

    private val _host = MutableStateFlow(BuildConfig.DEFAULT_RASPBERRY_HOST)
    val host: StateFlow<String> = _host.asStateFlow()

    private val _port = MutableStateFlow(BuildConfig.DEFAULT_RASPBERRY_PORT.toString())
    val port: StateFlow<String> = _port.asStateFlow()

    // --- UI events : connexion caméra ---------------------------------------

    fun updateHost(value: String) {
        _host.value = value.trim()
    }

    fun updatePort(value: String) {
        _port.value = value.filter { it.isDigit() }.take(5)
    }

    fun connect() {
        val config = buildConfig() ?: run {
            _cameraState.value = CameraUiState.Error("Adresse ou port invalide")
            return
        }

        disconnect()
        _cameraState.value = CameraUiState.Connecting

        streamJob = viewModelScope.launch {
            try {
                val status = runCatching { cameraRepository.fetchStatus(config) }.getOrNull()

                cameraRepository.stream(config) { frameBytes ->
                    withContext(Dispatchers.Main.immediate) {
                        _cameraState.value = CameraUiState.Streaming(
                            frame = frameBytes,
                            resolution = status?.resolution,
                            fps = status?.fps,
                        )
                    }
                }

                if (_cameraState.value !is CameraUiState.Error) {
                    _cameraState.value = CameraUiState.Idle
                }
            } catch (_: CancellationException) {
                // Déconnexion volontaire — disconnect() positionne déjà Idle.
            } catch (error: Exception) {
                _cameraState.value = CameraUiState.Error(
                    error.message ?: "Impossible de se connecter au flux caméra",
                )
            }
        }
    }

    fun disconnect() {
        streamJob?.cancel()
        streamJob = null
        _cameraState.value = CameraUiState.Idle
        stopTurnSignals()
    }

    fun retryAfterError() {
        if (_cameraState.value is CameraUiState.Error) connect()
    }

    // --- UI events : direction véhicule -------------------------------------

    /**
     * Appelé quand un bouton de direction est maintenu appuyé.
     * Envoie la commande au Raspberry Pi et mémorise la direction active.
     */
    fun pressDirection(direction: Direction) {
        if (direction == Direction.STOP) return
        val config = buildConfig() ?: return
        _activeDirections.value += direction
        viewModelScope.launch {
            directionRepository.sendPress(config, direction)
        }
    }

    /** Relâche une direction sans stopper les autres axes encore maintenus. */
    fun releaseDirection(direction: Direction) {
        if (direction == Direction.STOP) return
        val config = buildConfig() ?: run {
            _activeDirections.value -= direction
            return
        }
        _activeDirections.value -= direction
        viewModelScope.launch {
            directionRepository.sendRelease(config, direction)
        }
    }

    /** Active ou désactive un clignotant (toggle). Un seul côté actif à la fois. */
    fun toggleTurnSignal(signal: TurnSignal) {
        val config = buildConfig() ?: return
        _activeTurnSignal.value = if (_activeTurnSignal.value == signal) null else signal
        viewModelScope.launch {
            directionRepository.sendBlinkerToggle(config, signal)
        }
    }

    private fun stopTurnSignals() {
        if (_activeTurnSignal.value == null) return
        _activeTurnSignal.value = null
        val config = buildConfig() ?: return
        viewModelScope.launch {
            directionRepository.sendBlinkerOff(config)
        }
    }

    // --- Lifecycle ----------------------------------------------------------

    override fun onCleared() {
        stopTurnSignals()
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
