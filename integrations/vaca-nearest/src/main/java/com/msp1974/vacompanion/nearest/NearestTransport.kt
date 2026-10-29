package com.msp1974.vacompanion.nearest

import android.content.Context
import android.os.SystemClock
import java.io.Closeable
import java.net.*
import java.util.Locale
import java.util.concurrent.ArrayBlockingQueue
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.ThreadPoolExecutor
import java.util.concurrent.TimeUnit
import kotlin.concurrent.thread

/** Metadata only: no microphone, playback, settings or credential endpoint. */
internal class NearestTransport(context: Context, private val config: NearestConfig,
    private val received: (NearestClaim) -> Boolean) : Closeable {
    private val auth = NearestAuthenticator(config.houseWord)
    private val discovery = NearestDiscovery(context, config)
    private val sockets = ConcurrentHashMap.newKeySet<Socket>()
    private val workers = ThreadPoolExecutor(2, 4, 30, TimeUnit.SECONDS, ArrayBlockingQueue(8))
    @Volatile private var closed = false
    private var listening: ServerSocket? = null
    fun peers() = discovery.peers()
    fun networkState() = discovery.state()
    fun start() {
        val server = ServerSocket().apply { reuseAddress = true; bind(InetSocketAddress(config.port), 8) }
        listening = server
        thread(name = "nearest-http", isDaemon = true) {
            while (!closed) {
                val socket = try { server.accept() } catch (_: Exception) { break }
                if (!NearestLan.accepts(socket.inetAddress)) { socket.close(); continue }
                sockets.add(socket)
                try { workers.execute { socket.use { receive(it) }; sockets.remove(socket) } }
                catch (_: Exception) { sockets.remove(socket); runCatching { socket.close() } }
            }
        }
        try { discovery.start() } catch (_: Exception) { close(); error("Nearest discovery unavailable") }
    }
    fun post(peer: NearestDiscovery.Peer, claim: NearestClaim): Boolean {
        if (closed || !NearestLan.accepts(peer.address)) return false
        var connection: HttpURLConnection? = null
        return try {
            val body = NearestWire.encodeClaim(claim)
            val signature = auth.sign(body, peer.name)
            val url = URI("http", null, peer.address.hostAddress, peer.port, "/nearest", null, null).toURL()
            val request = url.openConnection(Proxy.NO_PROXY) as HttpURLConnection
            connection = request
            request.connectTimeout = 500; request.readTimeout = 500
            request.instanceFollowRedirects = false; request.requestMethod = "POST"
            request.doOutput = true; request.setFixedLengthStreamingMode(body.size)
            request.setRequestProperty("Content-Type", "application/json")
            request.setRequestProperty("X-Techo5-Nearest", signature)
            request.outputStream.use { it.write(body) }
            request.responseCode == 409 && auth.verifyAnswered(
                request.getHeaderField("X-Techo5-Nearest-Answered"), signature, claim.from, peer.name)
        } catch (_: Exception) { false } finally { connection?.disconnect() }
    }
    private fun receive(socket: Socket) {
        try {
            val deadline = SystemClock.elapsedRealtime() + 2000
            val input = socket.getInputStream(); var readBytes = 0
            fun byte(): Int {
                val remaining = deadline - SystemClock.elapsedRealtime()
                require(remaining > 0 && ++readBytes <= 8192)
                socket.soTimeout = remaining.toInt()
                return input.read().also { require(it >= 0) }
            }
            fun line(): String {
                val value = StringBuilder()
                while (true) {
                    val b = byte()
                    if (b == 13) { require(byte() == 10); return value.toString() }
                    require(b in 32..126 && value.length < 4096); value.append(b.toChar())
                }
            }
            if (line() != "POST /nearest HTTP/1.1") { reply(socket, 404); return }
            val headers = mutableMapOf<String, String>()
            while (true) {
                val row = line(); if (row.isEmpty()) break
                val colon = row.indexOf(':'); require(colon > 0)
                val name = row.substring(0, colon).lowercase(Locale.ROOT)
                require(!headers.containsKey(name) && headers.size < 32)
                headers[name] = row.substring(colon + 1).trim()
            }
            require("transfer-encoding" !in headers)
            val length = headers["content-length"]?.toIntOrNull() ?: error("Missing length")
            require(length in 1..NearestWire.MAX_BODY)
            val signature = headers["x-techo5-nearest"] ?: run { reply(socket, 401); return }
            if (!auth.looksSigned(signature)) { reply(socket, 401); return }
            val body = ByteArray(length) { byte().toByte() }
            if (!auth.verify(signature, body, config.name)) { reply(socket, 401); return }
            val claim = NearestWire.decodeClaim(body) ?: run { reply(socket, 400); return }
            if (closed) { reply(socket, 503); return }
            if (received(claim)) reply(socket, 409, auth.answeredProof(signature, claim.from, config.name))
            else reply(socket, 204)
        } catch (_: Exception) { runCatching { reply(socket, 400) } }
    }
    private fun reply(socket: Socket, status: Int, proof: String? = null) {
        val header = if (proof != null) "X-Techo5-Nearest-Answered: $proof\r\n" else ""
        socket.getOutputStream().write(("HTTP/1.1 $status Status\r\nContent-Length: 0\r\n" +
            "Connection: close\r\n" + header + "\r\n").toByteArray(Charsets.US_ASCII))
    }
    override fun close() {
        closed = true; runCatching { listening?.close() }; listening = null
        sockets.forEach { runCatching { it.close() } }; sockets.clear()
        discovery.close(); workers.shutdownNow(); auth.close()
    }
}
