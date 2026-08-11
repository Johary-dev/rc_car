package com.tpi.rccamera.camera

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlin.math.roundToInt

/**
 * ViewModel gérant la connexion au flux MJPEG du Raspberry Pi.
 *
 * Le constructeur sans paramètre est intentionnel : il permet l'instanciation
 * via [androidx.activity.viewModels] sans factory explicite.
 */
class CameraViewModel : ViewModel() {

    private val repository          = CameraRepository()
    private val directionRepository = DirectionRepository()
    private var streamJob: Job? = null

    private val _uiState = MutableStateFlow<CameraUiState>(CameraUiState.Idle)
    val uiState: StateFlow<CameraUiState> = _uiState.asStateFlow()

    /** true quand le suivi de ligne automatique est actif côté Raspberry Pi. */
    private val _autopilotActive = MutableStateFlow(false)
    val autopilotActive: StateFlow<Boolean> = _autopilotActive.asStateFlow()

    /** Ensemble des axes de direction actuellement enfoncés par l'utilisateur. */
    private val _activeDirections = MutableStateFlow<Set<Direction>>(emptySet())
    val activeDirections: StateFlow<Set<Direction>> = _activeDirections.asStateFlow()

    /** Position actuelle du slider avant/arrière, de -1f (arrière max) à 1f (avant max). */
    private val _throttleValue = MutableStateFlow(0f)
    val throttleValue: StateFlow<Float> = _throttleValue.asStateFlow()
    private var throttleJob: Job? = null

    /** Latence mesurée vers le serveur Pi en ms. null = injoignable. */
    private val _latencyMs = MutableStateFlow<Int?>(null)
    val latencyMs: StateFlow<Int?> = _latencyMs.asStateFlow()

    /** Niveau de batterie en % (0–100). null = non disponible. */
    private val _batteryPercent = MutableStateFlow<Int?>(null)
    val batteryPercent: StateFlow<Int?> = _batteryPercent.asStateFlow()

    private var pingJob: Job? = null

    private val _host = MutableStateFlow(CameraConnectionConfig.DEFAULT_HOST)
    val host: StateFlow<String> = _host.asStateFlow()

    private val _port = MutableStateFlow(CameraConnectionConfig.DEFAULT_PORT.toString())
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

                // Si le Pi répond mais signale que la caméra est absente, ne pas tenter
                // de streamer : afficher "Caméra non connectée" et rester connecté au Pi.
                if (status?.cameraConnected == false) {
                    _uiState.value = CameraUiState.NoCamera
                    startPinging(config)
                    return@launch
                }

                repository.stream(config) { frameBytes ->
                    startPinging(config)   // démarre au premier frame reçu
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
                // Le serveur Pi est actif mais la caméra n'est pas branchée (HTTP 503).
                val isCameraAbsent = error.message?.contains("503") == true
                _uiState.value = if (isCameraAbsent) {
                    CameraUiState.NoCamera
                } else {
                    CameraUiState.Error(error.message ?: "Impossible de se connecter au flux caméra")
                }
            }
        }
    }

    fun disconnect() {
        streamJob?.cancel()
        streamJob = null
        _uiState.value = CameraUiState.Idle
        _activeDirections.value = emptySet()
        _throttleValue.value = 0f
        stopPinging()
        _batteryPercent.value = null
    }

    // --- Jauge réseau -------------------------------------------------------

    /**
     * Lance un ping périodique vers le Pi pour alimenter [latencyMs].
     * Appelé dès que le Pi est joignable (stream actif ou caméra absente).
     */
    /**
     * Lance un polling périodique qui mesure la latence ET lit la batterie
     * via un seul appel à [CameraRepository.fetchStatusTimed].
     */
    private fun startPinging(config: CameraConnectionConfig) {
        if (pingJob?.isActive == true) return
        pingJob = viewModelScope.launch {
            while (isActive) {
                val result = repository.fetchStatusTimed(config)
                _latencyMs.value     = result?.first
                _batteryPercent.value = result?.second?.batteryPercent
                delay(PING_INTERVAL_MS)
            }
        }
    }

    private fun stopPinging() {
        pingJob?.cancel()
        pingJob = null
        _latencyMs.value      = null
        _batteryPercent.value = null
    }

    /** Appui sur un bouton de direction (déclenche /control/press/<cmd>). */
    fun pressDirection(direction: Direction) {
        if (_autopilotActive.value) return
        _activeDirections.value += direction
        val config = buildConfig() ?: return
        viewModelScope.launch {
            directionRepository.sendPress(config, direction)
        }
    }

    /** Relâchement d'un bouton de direction (déclenche /control/release/<cmd>). */
    fun releaseDirection(direction: Direction) {
        _activeDirections.value -= direction
        val config = buildConfig() ?: return
        viewModelScope.launch {
            directionRepository.sendRelease(config, direction)
        }
    }

    /**
     * Déplacement du slider avant/arrière. [value] va de -1f (arrière max) à 1f (avant max).
     * Un léger debounce évite de saturer le réseau pendant le glissement continu.
     */
    fun setThrottle(value: Float) {
        if (_autopilotActive.value) return
        val clamped = value.coerceIn(-1f, 1f)
        _throttleValue.value = clamped
        val percent = (clamped * 100f).roundToInt()
        val config = buildConfig() ?: return
        throttleJob?.cancel()
        throttleJob = viewModelScope.launch {
            delay(30L)
            directionRepository.sendThrottle(config, percent)
        }
    }

    /** Relâchement du slider : la voiture revient à l'arrêt (throttle 0). */
    fun releaseThrottle() {
        throttleJob?.cancel()
        _throttleValue.value = 0f
        val config = buildConfig() ?: return
        viewModelScope.launch {
            directionRepository.sendThrottle(config, 0)
        }
    }

    fun retryAfterError() {
        if (_uiState.value is CameraUiState.Error || _uiState.value is CameraUiState.NoCamera) {
            connect()
        }
    }

    /**
     * Bascule entre pilotage manuel et automatique.
     *
     * Avec rc_unified.py le serveur reste le même processus : /switch/auto|manual
     * ne fait que basculer un flag. Pas de redémarrage → pas de déconnexion.
     */
    fun toggleAutopilot() {
        val config = buildConfig() ?: return
        val activating = !_autopilotActive.value
        _autopilotActive.value = activating
        _activeDirections.value = emptySet()
        throttleJob?.cancel()
        _throttleValue.value = 0f
        viewModelScope.launch {
            repository.sendSwitch(config, toAuto = activating)
        }
    }

    companion object {
        /** Intervalle entre deux pings réseau (ms). */
        private const val PING_INTERVAL_MS = 3000L
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
