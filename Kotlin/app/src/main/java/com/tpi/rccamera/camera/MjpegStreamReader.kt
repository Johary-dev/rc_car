package com.tpi.rccamera.camera

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import java.io.ByteArrayOutputStream
import java.io.IOException
import java.io.InputStream
import java.util.concurrent.TimeUnit
import kotlin.coroutines.coroutineContext

/**
 * Lit le flux MJPEG servi par [rasberry/camera.py] sur /video.
 *
 * Format attendu (multipart/x-mixed-replace, boundary=frame) :
 *   --frame\r\n
 *   Content-Type: image/jpeg\r\n\r\n
 *   [bytes JPEG]\r\n
 */
class MjpegStreamReader(
    private val streamUrl: String,
    private val okHttpClient: OkHttpClient = defaultClient(),
) {
    suspend fun streamFrames(onFrame: suspend (ByteArray) -> Unit) {
        withContext(Dispatchers.IO) {
            val request = Request.Builder()
                .url(streamUrl)
                .header("Accept", "multipart/x-mixed-replace")
                .build()

            val response = okHttpClient.newCall(request).execute()

            response.use {
                if (!response.isSuccessful) {
                    throw IOException("Flux indisponible (HTTP ${response.code})")
                }

                val body = response.body ?: throw IOException("Réponse vide du serveur")
                val contentType = body.contentType()?.toString().orEmpty()
                val boundary = extractBoundary(contentType) ?: DEFAULT_BOUNDARY

                val reader = MultipartFrameReader(body.byteStream(), boundary)

                while (coroutineContext.isActive) {
                    val frame = reader.readNextFrame() ?: break
                    onFrame(frame)
                }
            }
        }
    }

    private fun extractBoundary(contentType: String): String? {
        val prefix = "boundary="
        val index = contentType.indexOf(prefix, ignoreCase = true)
        if (index == -1) return null
        return contentType.substring(index + prefix.length).trim().trim('"')
    }

    companion object {
        private const val DEFAULT_BOUNDARY = "frame"

        fun defaultClient(): OkHttpClient = OkHttpClient.Builder()
            .connectTimeout(10, TimeUnit.SECONDS)
            .readTimeout(0, TimeUnit.SECONDS)
            .retryOnConnectionFailure(true)
            .build()
    }
}

/**
 * Parse un flux multipart/x-mixed-replace frame par frame.
 *
 * Utilise un buffer ByteArray avec deux pointeurs (dataStart / dataEnd) pour
 * éviter toute allocation boxing et les suppressions O(n) en tête de liste.
 */
private class MultipartFrameReader(
    private val inputStream: InputStream,
    boundary: String,
) {
    private val boundaryMarker = "--$boundary".encodeToByteArray()
    private val headerEndMarker = "\r\n\r\n".encodeToByteArray()

    private var buf = ByteArray(INITIAL_BUF_SIZE)
    private var dataStart = 0
    private var dataEnd = 0

    private val buffered get() = dataEnd - dataStart

    // --- Public API ---------------------------------------------------------

    fun readNextFrame(): ByteArray? {
        skipUntilBoundary() ?: return null
        skipHeaders() ?: return null
        return readJpegPayload()
    }

    // --- Private steps ------------------------------------------------------

    private fun skipUntilBoundary(): Unit? {
        while (true) {
            val idx = indexOf(boundaryMarker)
            if (idx >= 0) {
                advance(idx + boundaryMarker.size)
                skipLineEnding()
                return Unit
            }
            // Conserver assez d'octets pour détecter un marqueur coupé entre deux lectures
            val safeToDiscard = (buffered - boundaryMarker.size).coerceAtLeast(0)
            if (safeToDiscard > 0) advance(safeToDiscard)
            if (fillBuffer() <= 0) return null
        }
    }

    private fun skipHeaders(): Unit? {
        while (true) {
            val idx = indexOf(headerEndMarker)
            if (idx >= 0) {
                advance(idx + headerEndMarker.size)
                return Unit
            }
            if (fillBuffer() <= 0) return null
        }
    }

    private fun readJpegPayload(): ByteArray? {
        val output = ByteArrayOutputStream(FRAME_INITIAL_CAPACITY)

        while (true) {
            val idx = indexOf(boundaryMarker)
            if (idx >= 0) {
                // Supprimer le \r\n final qui précède --boundary
                var frameLen = idx
                while (frameLen > 0 && isLineEnding(buf[dataStart + frameLen - 1])) {
                    frameLen--
                }
                output.write(buf, dataStart, frameLen)
                advance(idx) // laisser le marqueur en place pour le prochain appel
                val bytes = output.toByteArray()
                return if (bytes.isEmpty()) null else bytes
            }

            // Vider en toute sécurité les octets qui ne peuvent pas appartenir au marqueur
            val safeBytes = (buffered - boundaryMarker.size).coerceAtLeast(0)
            if (safeBytes > 0) {
                output.write(buf, dataStart, safeBytes)
                advance(safeBytes)
            }

            if (fillBuffer() <= 0) {
                output.write(buf, dataStart, buffered)
                val bytes = output.toByteArray()
                return if (bytes.isEmpty()) null else bytes
            }
        }
    }

    // --- Buffer management --------------------------------------------------

    private fun fillBuffer(): Int {
        compact()
        if (dataEnd >= buf.size) {
            buf = buf.copyOf(buf.size * 2)
        }
        val n = inputStream.read(buf, dataEnd, buf.size - dataEnd)
        if (n > 0) dataEnd += n
        return n
    }

    /** Déplace les données non traitées en début de buffer (évite les réallocations). */
    private fun compact() {
        if (dataStart == 0) return
        buf.copyInto(buf, destinationOffset = 0, startIndex = dataStart, endIndex = dataEnd)
        dataEnd -= dataStart
        dataStart = 0
    }

    private fun advance(n: Int) {
        dataStart = (dataStart + n).coerceAtMost(dataEnd)
    }

    private fun skipLineEnding() {
        while (dataStart < dataEnd && isLineEnding(buf[dataStart])) {
            dataStart++
        }
    }

    private fun isLineEnding(b: Byte) = b == '\r'.code.toByte() || b == '\n'.code.toByte()

    /**
     * Recherche naïve de [pattern] dans buf[dataStart..dataEnd).
     * Retourne l'offset relatif à dataStart, ou -1.
     */
    private fun indexOf(pattern: ByteArray): Int {
        if (buffered < pattern.size) return -1
        val limit = dataEnd - pattern.size
        outer@ for (i in dataStart..limit) {
            for (j in pattern.indices) {
                if (buf[i + j] != pattern[j]) continue@outer
            }
            return i - dataStart
        }
        return -1
    }

    companion object {
        private const val INITIAL_BUF_SIZE = 32 * 1024
        private const val FRAME_INITIAL_CAPACITY = 64 * 1024
    }
}
