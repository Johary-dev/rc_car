package com.tpi.rccamera.camera

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
 * Les erreurs réseau sont ignorées : la commande est non bloquante.
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

    /** Envoie une valeur d'accélérateur proportionnelle (-100 à 100). */
    suspend fun sendThrottle(config: CameraConnectionConfig, percent: Int) {
        send(config.controlThrottleUrl(percent))
    }

    private suspend fun send(url: String) {
        withContext(Dispatchers.IO) {
            runCatching {
                httpClient.newCall(Request.Builder().url(url).get().build()).execute().close()
            }
        }
    }
}
