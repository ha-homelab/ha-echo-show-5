package com.msp1974.vacompanion.telephony

import android.app.Service
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import android.os.Message
import android.os.Messenger
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** Same-signer IPC only. No HTTP listener, shell command, SIP credential or audio payload. */
class AudioLeaseService : Service() {
    private data class Client(val reply: Messenger, val death: IBinder.DeathRecipient)
    private val clients = mutableMapOf<String, Client>()
    private var expiry: Job? = null
    private val receiver = Messenger(object : Handler(Looper.getMainLooper()) {
        override fun handleMessage(message: Message) {
            val uid = message.sendingUid
            val reply = message.replyTo ?: return
            if (packageManager.checkSignatures(uid, applicationInfo.uid) != PackageManager.SIGNATURE_MATCH ||
                packageManager.getPackagesForUid(uid)?.contains(SIP_PACKAGE) != true) return
            val data = try { Bundle(message.data) } catch (_: Exception) { return }
            val request = runCatching { data.getString("request_id", "") }.getOrDefault("")
            if (request.length !in 1..80 || !request.matches(Regex("[A-Za-z0-9_-]+"))) return
            val operation = message.what
            AudioLeaseRuntime.scope.launch {
                val token = runCatching { data.getString("lease_id", "") }.getOrDefault("")
                val result = try {
                    check(AudioLeaseRuntime.journalValid())
                    when (operation) {
                        STATUS -> AudioLeaseRuntime.coordinator.status(uid)
                        ACQUIRE -> {
                            val ttl = data.getLong("ttl_ms", 30_000L)
                            attach(uid, token, reply)
                            val value = AudioLeaseRuntime.coordinator.acquire(uid, token, ttl, AudioLeaseRuntime.boot)
                            if (value.ok) scheduleExpiry(uid, token, ttl)
                            else if (value.token != token) detach(token)
                            value
                        }
                        RENEW -> {
                            val ttl = data.getLong("ttl_ms", 30_000L)
                            val value = AudioLeaseRuntime.coordinator.renew(uid, token, ttl)
                            if (value.ok) { attach(uid, token, reply); scheduleExpiry(uid, token, ttl) }
                            value
                        }
                        RELEASE -> {
                            val value = AudioLeaseRuntime.coordinator.release(uid, token)
                            if (value.ok) detach(token)
                            value
                        }
                        else -> AudioLeaseCoordinator.Result(false, "recovery", reason = "unknown_operation")
                    }
                } catch (_: Exception) {
                    if (AudioLeaseRuntime.coordinator.status(uid).token != token) detach(token)
                    AudioLeaseCoordinator.Result(false, "recovery", reason = "request_failed")
                }
                send(reply, RESULT, request, result)
            }
        }
    })

    override fun onCreate() {
        super.onCreate()
        AudioLeaseRuntime.initialize(applicationContext)
    }

    override fun onBind(intent: Intent?): IBinder? =
        if (intent?.action == ACTION) receiver.binder else null

    private fun attach(uid: Int, token: String, reply: Messenger) {
        require(token.matches(Regex("[A-Za-z0-9_-]{16,80}")))
        val old = clients[token]
        if (old?.reply?.binder == reply.binder) return
        val death = IBinder.DeathRecipient {
            AudioLeaseRuntime.scope.launch {
                if (clients[token]?.reply?.binder == reply.binder) {
                    val result = AudioLeaseRuntime.coordinator.release(uid, token)
                    if (result.ok) detach(token)
                }
            }
        }
        // Register death before acquisition so a dying process cannot orphan a granted lease.
        reply.binder.linkToDeath(death, 0)
        old?.let { runCatching { it.reply.binder.unlinkToDeath(it.death, 0) } }
        clients[token] = Client(reply, death)
    }

    private fun detach(token: String) {
        clients.remove(token)?.let { runCatching { it.reply.binder.unlinkToDeath(it.death, 0) } }
    }

    private fun scheduleExpiry(uid: Int, token: String, ttl: Long) {
        expiry?.cancel()
        expiry = AudioLeaseRuntime.scope.launch {
            delay(ttl + 25L)
            val revoked = AudioLeaseRuntime.coordinator.expire() ?: return@launch
            if (revoked.uid == uid && revoked.token == token) {
                clients[token]?.reply?.let {
                    send(it, REVOKE, "", AudioLeaseCoordinator.Result(false, "revoked", token, "lease_expired"))
                }
            }
        }
    }

    private fun send(reply: Messenger, code: Int, request: String, result: AudioLeaseCoordinator.Result) {
        val response = Message.obtain(null, code).apply {
            data = Bundle().apply {
                putInt("protocol", 1)
                putString("request_id", request)
                putString("lease_id", result.token)
                putBoolean("ok", result.ok)
                putString("state", result.state)
                putString("reason", result.reason)
            }
        }
        runCatching { reply.send(response) }
    }

    companion object {
        const val ACTION = "com.msp1974.vacompanion.AUDIO_LEASE"
        const val SIP_PACKAGE = "org.hahomelab.show5sip"
        const val STATUS = 1
        const val ACQUIRE = 2
        const val RENEW = 3
        const val RELEASE = 4
        const val RESULT = 100
        const val REVOKE = 101
    }
}
