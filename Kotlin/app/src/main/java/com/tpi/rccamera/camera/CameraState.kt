package com.tpi.rccamera.camera

import com.tpi.rccamera.BuildConfig

data class CameraConnectionConfig(
    val host: String = BuildConfig.DEFAULT_RASPBERRY_HOST,
    val port: Int = BuildConfig.DEFAULT_RASPBERRY_PORT,
) {
    val videoUrl: String get() = "http://$host:$port/video"
    val statusUrl: String get() = "http://$host:$port/status"
}

sealed interface CameraUiState {

    data object Idle : CameraUiState

    data object Connecting : CameraUiState

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
)
