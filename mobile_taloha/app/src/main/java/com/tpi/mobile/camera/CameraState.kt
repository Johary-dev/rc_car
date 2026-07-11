package com.tpi.mobile.camera

import com.tpi.mobile.BuildConfig

/**
 * Commandes de direction envoyées au Raspberry Pi via GET /control/{command}.
 * Correspond aux méthodes de [rasberry/direction.py] : forward, backward, left, right, stop.
 */
enum class Direction(val command: String, val label: String) {
    FORWARD("forward", "Avant"),
    BACKWARD("backward", "Arrière"),
    LEFT("left", "Gauche"),
    RIGHT("right", "Droite"),
    STOP("stop", "Stop"),
}

enum class TurnSignal(val command: String, val label: String) {
    LEFT("left", "Clignotant gauche"),
    RIGHT("right", "Clignotant droit"),
}

data class CameraConnectionConfig(
    val host: String = BuildConfig.DEFAULT_RASPBERRY_HOST,
    val port: Int = BuildConfig.DEFAULT_RASPBERRY_PORT,
) {
    val videoUrl: String get() = "http://$host:$port/video"
    val statusUrl: String get() = "http://$host:$port/status"
    fun controlPressUrl(direction: Direction) = "http://$host:$port/control/press/${direction.command}"
    fun controlReleaseUrl(direction: Direction) = "http://$host:$port/control/release/${direction.command}"
    fun controlBlinkerToggleUrl(signal: TurnSignal) =
        "http://$host:$port/control/blinker/${signal.command}/toggle"
    fun controlBlinkerOffUrl() = "http://$host:$port/control/blinker/off"
}

sealed interface CameraUiState {

    data object Idle : CameraUiState

    data object Connecting : CameraUiState

    data class Streaming(
        val frame: ByteArray,
        val resolution: String? = null,
        val fps: Int? = null,
    ) : CameraUiState {
        override fun equals(other: Any?): Boolean {
            if (this === other) return true
            if (other !is Streaming) return false
            return frame.contentEquals(other.frame) &&
                resolution == other.resolution &&
                fps == other.fps
        }

        override fun hashCode(): Int =
            31 * frame.contentHashCode() + resolution.hashCode() * 31 + fps.hashCode()
    }

    data class Error(val message: String) : CameraUiState
}

data class CameraStatus(
    val resolution: String?,
    val fps: Int?,
    val jpegQuality: Int?,
)
