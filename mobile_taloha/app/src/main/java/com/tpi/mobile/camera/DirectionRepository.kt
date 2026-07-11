package com.tpi.mobile.camera

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.util.concurrent.TimeUnit

/**
 * Envoie des commandes press/release au Raspberry Pi.
 *
 *   GET /control/press/forward    → active l'axe avant
 *   GET /control/release/forward  → désactive l'axe avant
 *
 * Plusieurs axes peuvent être actifs en même temps (ex. avant + droite).
 */
class DirectionRepository {

    private val httpClient: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(2, TimeUnit.SECONDS)
        .readTimeout(2, TimeUnit.SECONDS)
        .build()

    suspend fun sendPress(config: CameraConnectionConfig, direction: Direction) {
        send(config.controlPressUrl(direction))
    }

    suspend fun sendRelease(config: CameraConnectionConfig, direction: Direction) {
        send(config.controlReleaseUrl(direction))
    }

    suspend fun sendBlinkerToggle(config: CameraConnectionConfig, signal: TurnSignal) {
        send(config.controlBlinkerToggleUrl(signal))
    }

    suspend fun sendBlinkerOff(config: CameraConnectionConfig) {
        send(config.controlBlinkerOffUrl())
    }

    private suspend fun send(url: String) {
        withContext(Dispatchers.IO) {
            try {
                val request = Request.Builder().url(url).get().build()
                httpClient.newCall(request).execute().close()
            } catch (_: Exception) {
                // Commande non bloquante — une erreur réseau ne bloque pas l'UI.
            }
        }
    }
}
