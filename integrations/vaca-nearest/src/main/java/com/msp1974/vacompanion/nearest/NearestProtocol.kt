package com.msp1974.vacompanion.nearest

import java.nio.ByteBuffer
import java.nio.charset.CodingErrorAction
import java.security.MessageDigest
import java.security.SecureRandom
import javax.crypto.Mac
import javax.crypto.spec.SecretKeySpec

/** Wire compatibility with TECHO5 nearest v2 (MIT, TECHO5 contributors, 2026).
 * No transport, credential persistence, logging, or device access belongs in this module.
 */
data class NearestClaim(val from: String, val turn: String, val word: String = "", val score: Double)

object NearestWire {
    const val PATH = "/nearest"
    const val AUTH_HEADER = "X-Techo5-Nearest"
    const val ANSWERED_HEADER = "X-Techo5-Nearest-Answered"
    const val MAX_BODY = 4096

    fun newTurn(): String = ByteArray(8).also { SecureRandom().nextBytes(it) }.hex()

    fun encodeClaim(claim: NearestClaim): ByteArray {
        require(claim.from.isNotEmpty() && claim.score.isFinite())
        val word = if (claim.word.isEmpty()) "" else ",\"word\":${quote(claim.word)}"
        return ("{\"from\":${quote(claim.from)},\"turn\":${quote(claim.turn)}$word,\"score\":${claim.score}}")
            .toByteArray(Charsets.UTF_8).also { require(it.size <= MAX_BODY) }
    }

    fun decodeClaim(body: ByteArray): NearestClaim? {
        if (body.size > MAX_BODY) return null
        return try {
            val text = Charsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
                .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(body)).toString()
            val value = Json(text).parse() as? Map<*, *> ?: return null
            val from = value["from"] as? String ?: return null
            val turn = if (value.containsKey("turn")) value["turn"] as? String ?: return null else ""
            val word = if (value.containsKey("word")) value["word"] as? String ?: return null else ""
            val score = if (value.containsKey("score")) value["score"] as? Double ?: return null else 0.0
            if (from.isEmpty() || !score.isFinite()) null else NearestClaim(from, turn, word, score)
        } catch (_: Exception) { null }
    }

    private fun quote(value: String): String = buildString {
        append('"')
        for (c in value) when (c) {
            '"' -> append("\\\""); '\\' -> append("\\\\")
            '\b' -> append("\\b"); '\u000c' -> append("\\f")
            '\n' -> append("\\n"); '\r' -> append("\\r"); '\t' -> append("\\t")
            else -> if (c < ' ') append("\\u" + c.code.toString(16).padStart(4, '0')) else append(c)
        }
        append('"')
    }

    // A bounded JSON reader avoids adding an Android dependency to the protocol core.
    // Duplicate keys and invalid UTF-8 are refused; no normal TECHO5 sender emits either.
    private class Json(private val s: String) {
        private var p = 0
        fun parse(): Any? = value(0).also { white(); require(p == s.length) }
        private fun white() { while (p < s.length && s[p] in " \t\r\n") p++ }
        private fun take(c: Char): Boolean { white(); return if (p < s.length && s[p] == c) { p++; true } else false }
        private fun value(depth: Int): Any? {
            require(depth <= 16); white(); require(p < s.length)
            return when (s[p]) {
                '"' -> string()
                '{' -> {
                    p++; val out = linkedMapOf<String, Any?>()
                    if (!take('}')) { do { val key = string(); require(!out.containsKey(key)); require(take(':')); out[key] = value(depth + 1) } while (take(',')); require(take('}')) }
                    out
                }
                '[' -> {
                    p++; val out = mutableListOf<Any?>()
                    if (!take(']')) { do { out.add(value(depth + 1)) } while (take(',')); require(take(']')) }
                    out
                }
                't' -> literal("true", true)
                'f' -> literal("false", false)
                'n' -> literal("null", null)
                else -> {
                    val begin = p
                    while (p < s.length && s[p] in "0123456789eE+.-") p++
                    val n = s.substring(begin, p)
                    require(n.matches(Regex("-?(0|[1-9][0-9]*)(\\.[0-9]+)?([eE][+-]?[0-9]+)?")))
                    n.toDouble()
                }
            }
        }
        private fun literal(token: String, v: Any?): Any? { require(s.startsWith(token, p)); p += token.length; return v }
        private fun string(): String {
            require(take('"'))
            return buildString {
                while (true) {
                    require(p < s.length); val c = s[p++]
                    if (c == '"') break
                    require(c >= ' ')
                    if (c != '\\') append(c) else {
                        require(p < s.length)
                        when (val e = s[p++]) {
                            '"', '\\', '/' -> append(e)
                            'b' -> append('\b'); 'f' -> append('\u000c'); 'n' -> append('\n'); 'r' -> append('\r'); 't' -> append('\t')
                            'u' -> { require(p + 4 <= s.length); append(s.substring(p, p + 4).toInt(16).toChar()); p += 4 }
                            else -> error("Invalid JSON escape")
                        }
                    }
                }
            }
        }
    }
}

/** Derive once off the audio thread. Replace and close this object when the House word changes. */
class NearestAuthenticator(
    houseWord: String,
    private val startedAtMillis: Long = System.currentTimeMillis(),
    private val monotonicMillis: () -> Long = { System.nanoTime() / 1_000_000 },
) : AutoCloseable {
    private val startMono = monotonicMillis()
    private val key: ByteArray
    private val seen = LinkedHashMap<String, Long>()
    private var closed = false
    init { require(houseWord.isNotEmpty()); key = derive(houseWord.toByteArray(Charsets.UTF_8)) }

    fun sign(body: ByteArray, recipient: String, nowMillis: Long = System.currentTimeMillis()): String =
        signWithNonce(body, recipient, nowMillis, ByteArray(12).also { SecureRandom().nextBytes(it) })

    internal fun signWithNonce(body: ByteArray, recipient: String, nowMillis: Long, nonce: ByteArray): String {
        require(body.size <= NearestWire.MAX_BODY && recipient.isNotEmpty() && nonce.size == 12)
        val ts = Math.floorDiv(nowMillis, 1000).toString()
        val n = nonce.hex()
        return "v2 $ts $n ${requestMac(ts, n, recipient, body).hex()}"
    }

    /** Header preflight allows a server to reject a request before reading its body. */
    fun looksSigned(header: String?, nowMillis: Long = System.currentTimeMillis()): Boolean {
        val parts = parts(header) ?: return false
        val seconds = parts[1].toLongOrNull() ?: return false
        if (seconds !in Long.MIN_VALUE / 1000..Long.MAX_VALUE / 1000) return false
        val sentMillis = seconds * 1000
        // Compare as doubles to avoid integer subtraction overflow for hostile timestamps.
        if (kotlin.math.abs(nowMillis.toDouble() - sentMillis.toDouble()) > 5000.0) return false
        val elapsed = (monotonicMillis() - startMono).coerceAtLeast(0)
        // Same clock-adjustment behavior as TECHO5's startedWall. Injection supports deterministic tests.
        val startWall = if (elapsed == 0L) minOf(startedAtMillis, nowMillis) else nowMillis - elapsed
        return seconds >= Math.floorDiv(startWall, 1000)
    }

    @Synchronized
    fun verify(header: String?, body: ByteArray, recipient: String, nowMillis: Long = System.currentTimeMillis()): Boolean {
        if (closed || body.size > NearestWire.MAX_BODY || !looksSigned(header, nowMillis)) return false
        val p = parts(header) ?: return false
        val got = p[3].unhex() ?: return false
        if (!MessageDigest.isEqual(got, requestMac(p[1], p[2], recipient, body))) return false
        if (seen.containsKey(p[2])) return false
        if (seen.size >= 1024) {
            val iterator = seen.entries.iterator()
            while (iterator.hasNext()) if (nowMillis - iterator.next().value > 10_000) iterator.remove()
            if (seen.size >= 1024) return false
        }
        seen[p[2]] = nowMillis
        return true
    }

    fun answeredProof(requestHeader: String, from: String, by: String): String? {
        val p = parts(requestHeader) ?: return null
        return hmac("answered\n${p[2]}\n${goLower(from)}\n${goLower(by)}\n".toByteArray(Charsets.UTF_8)).hex()
    }

    fun verifyAnswered(proof: String?, requestHeader: String, from: String, by: String): Boolean {
        if (proof == null || proof.length != 64 || closed) return false
        val expected = answeredProof(requestHeader, from, by) ?: return false
        return MessageDigest.isEqual(proof.toByteArray(Charsets.US_ASCII), expected.toByteArray(Charsets.US_ASCII))
    }

    private fun requestMac(ts: String, nonce: String, recipient: String, body: ByteArray): ByteArray =
        hmac("v2\n$ts\n$nonce\n${goLower(recipient)}\n${MessageDigest.getInstance("SHA-256").digest(body).hex()}\n".toByteArray(Charsets.UTF_8))

    @Synchronized private fun hmac(body: ByteArray): ByteArray {
        check(!closed)
        return Mac.getInstance("HmacSHA256").apply { init(SecretKeySpec(key, "HmacSHA256")) }.doFinal(body)
    }

    @Synchronized override fun close() { closed = true; key.fill(0); seen.clear() }

    private fun parts(header: String?): List<String>? {
        if (header == null || header.length > 256) return null
        val p = header.trim().split(Regex("\\s+"))
        if (p.size != 4 || p[0] != "v2" || !p[2].matches(Regex("[0-9a-f]{24}")) || !p[3].matches(Regex("[0-9a-fA-F]{64}"))) return null
        return p
    }

    private fun derive(password: ByteArray): ByteArray {
        try {
            val mac = Mac.getInstance("HmacSHA256").apply { init(SecretKeySpec(password, "HmacSHA256")) }
            var u = mac.doFinal("techo5-nearest v2".toByteArray(Charsets.UTF_8) + byteArrayOf(0, 0, 0, 1))
            val out = u.copyOf()
            repeat(99_999) {
                val next = mac.doFinal(u); u.fill(0); u = next
                for (i in out.indices) out[i] = (out[i].toInt() xor u[i].toInt()).toByte()
            }
            u.fill(0)
            return out
        } finally { password.fill(0) }
    }
}

internal fun ByteArray.hex(): String = joinToString("") { (it.toInt() and 255).toString(16).padStart(2, '0') }
internal fun String.unhex(): ByteArray? = try {
    if (length % 2 != 0) null else ByteArray(length / 2) { substring(it * 2, it * 2 + 2).toInt(16).toByte() }
} catch (_: NumberFormatException) { null }

/** Go uses Unicode simple lowercasing, unlike Java String's context/expansion mappings. */
internal fun goLower(text: String): String = buildString {
    var i = 0
    while (i < text.length) { val c = text.codePointAt(i); appendCodePoint(Character.toLowerCase(c)); i += Character.charCount(c) }
}
