package com.tpi.rccamera.camera

/** Axes de contrôle envoyés au Raspberry Pi via /control/press|release/<command>. */
enum class Direction(val command: String, val label: String) {
    FORWARD("forward",  "Avant"),
    BACKWARD("backward", "Arrière"),
    LEFT("left",        "Gauche"),
    RIGHT("right",      "Droite"),
}

data class CameraConnectionConfig(
    val host: String = DEFAULT_HOST,
    val port: Int    = DEFAULT_PORT,
) {
    val videoUrl: String  get() = "http://$host:$port/video"
    val statusUrl: String get() = "http://$host:$port/status"
    fun switchAutoUrl()              = "http://$host:$port/switch/auto"
    fun switchManualUrl()            = "http://$host:$port/switch/manual"
    fun controlPressUrl(d: Direction)   = "http://$host:$port/control/press/${d.command}"
    fun controlReleaseUrl(d: Direction) = "http://$host:$port/control/release/${d.command}"
    /** [percent] doit être compris entre -100 (arrière max) et 100 (avant max). */
    fun controlThrottleUrl(percent: Int) = "http://$host:$port/control/throttle/$percent"

    companion object {
        /** Valeurs par défaut — identiques aux buildConfigField dans app/build.gradle.kts. */
        const val DEFAULT_HOST = "192.168.1.100"
        const val DEFAULT_PORT = 5000
    }
}

sealed interface CameraUiState {

    data object Idle : CameraUiState

    data object Connecting : CameraUiState

    /** Le Pi répond mais la caméra USB n'est pas branchée (HTTP 503 sur /video). */
    data object NoCamera : CameraUiState

    data class Streaming(
        val frame: ByteArray,
        val resolution: String? = null,
        val fps: Int? = null,
    ) : CameraUiState {
        // equals/hashCode sur le contenu du tableau pour éviter les recompositions inutiles
        override fun equals(other: Any?): Boolean {
            if (this === other) return true
            if (other !is Streaming) return false
            return frame.contentEquals(other.frame) &&
                resolution == other.resolution &&
                fps == other.fps
        }

        override fun hashCode(): Int = 31 * frame.contentHashCode() +
            resolution.hashCode() * 31 + fps.hashCode()
    }

    data class Error(val message: String) : CameraUiState
}

data class CameraStatus(
    val resolution: String?,
    val fps: Int?,
    val jpegQuality: Int?,
    /** null si le champ n'existe pas dans la réponse (ancien serveur). */
    val cameraConnected: Boolean?,
    /** Niveau de batterie en pourcentage (0–100). null si non disponible. */
    val batteryPercent: Int?,
)
