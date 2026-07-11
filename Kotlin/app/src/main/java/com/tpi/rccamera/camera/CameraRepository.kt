package com.tpi.rccamera.camera

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.IOException
import java.util.concurrent.TimeUnit

class CameraRepository {

    private val httpClient: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(5, TimeUnit.SECONDS)
        .build()

    suspend fun fetchStatus(config: CameraConnectionConfig): CameraStatus =
        withContext(Dispatchers.IO) {
            val request = Request.Builder().url(config.statusUrl).get().build()

            httpClient.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    throw IOException("Statut indisponible (HTTP ${response.code})")
                }

                val body = response.body?.string().orEmpty()
                val json = JSONObject(body)

                CameraStatus(
                    resolution = json.optString("resolution").ifBlank { null },
                    fps = json.optInt("fps", -1).takeIf { it >= 0 },
                    jpegQuality = json.optInt("jpeg_quality", -1).takeIf { it >= 0 },
                )
            }
        }

    suspend fun stream(
        config: CameraConnectionConfig,
        onFrame: suspend (ByteArray) -> Unit,
    ) {
        MjpegStreamReader(config.videoUrl).streamFrames(onFrame)
    }
}
