package com.msp1974.vacompanion.nearest

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.os.Handler
import android.os.Looper
import android.os.SystemClock
import java.io.Closeable
import java.net.InetAddress
import java.util.ArrayDeque
import java.util.concurrent.ConcurrentHashMap

internal class NearestDiscovery(context: Context, private val config: NearestConfig) : Closeable {
    data class Peer(val name: String, val address: InetAddress, val port: Int, val seen: Long)
    private val nsd = context.getSystemService(Context.NSD_SERVICE) as NsdManager
    private val handler = Handler(Looper.getMainLooper())
    private val known = ConcurrentHashMap<String, Peer>()
    private val services = ConcurrentHashMap<String, NsdServiceInfo>()
    private val queue = ArrayDeque<NsdServiceInfo>()
    private var resolving = false
    @Volatile private var ticket = 0L
    @Volatile private var closed = false
    private var registered = false
    private var discovering = false
    @Volatile private var registerState = "pending"
    @Volatile private var discoverState = "pending"
    fun state() = if (registerState == "ready" && discoverState == "ready") "ready" else "$registerState/$discoverState"
    fun peers() = known.values.filter { state() == "ready" && SystemClock.elapsedRealtime() - it.seen < 363_000 }
        .sortedBy { it.name }.take(16)
    fun start() {
        nsd.registerService(NsdServiceInfo().apply {
            serviceName = config.name; serviceType = "_techo5._tcp."; port = config.port
            setAttribute("name", config.name); setAttribute("nearest", "1"); setAttribute("intercom", "0")
        }, NsdManager.PROTOCOL_DNS_SD, registration)
        registered = true
        nsd.discoverServices("_techo5._tcp.", NsdManager.PROTOCOL_DNS_SD, discovery)
        discovering = true; handler.postDelayed(refresh, 120_000)
    }
    private val refresh = object : Runnable {
        override fun run() {
            if (closed) return
            services.values.take(32).forEach { enqueue(it) }
            handler.postDelayed(this, 120_000)
        }
    }
    private val registration = object : NsdManager.RegistrationListener {
        override fun onServiceRegistered(info: NsdServiceInfo) { registerState = "ready" }
        override fun onRegistrationFailed(info: NsdServiceInfo, code: Int) { registered = false; registerState = "failed" }
        override fun onServiceUnregistered(info: NsdServiceInfo) {}
        override fun onUnregistrationFailed(info: NsdServiceInfo, code: Int) {}
    }
    private val discovery = object : NsdManager.DiscoveryListener {
        override fun onDiscoveryStarted(type: String) { discoverState = "ready" }
        override fun onDiscoveryStopped(type: String) {}
        override fun onStartDiscoveryFailed(type: String, code: Int) { discovering = false; discoverState = "failed" }
        override fun onStopDiscoveryFailed(type: String, code: Int) {}
        override fun onServiceLost(info: NsdServiceInfo) { services.remove(info.serviceName); known.remove(info.serviceName) }
        override fun onServiceFound(info: NsdServiceInfo) {
            if (!closed && (services.size < 32 || services.containsKey(info.serviceName))) { services[info.serviceName] = info; enqueue(info) }
        }
    }
    private fun enqueue(info: NsdServiceInfo) = synchronized(queue) {
        if (!closed && queue.size < 32) { queue.addLast(info); resolveNext() }
    }
    @Suppress("DEPRECATION")
    private fun resolveNext() {
        if (closed || resolving || queue.isEmpty()) return
        resolving = true; val current = ++ticket
        val service = queue.removeFirst()
        fun done() = synchronized(queue) {
            if (ticket == current) { ticket++; resolving = false; resolveNext() }
        }
        handler.postDelayed({ done() }, 5000)
        val listener = object : NsdManager.ResolveListener {
            override fun onResolveFailed(info: NsdServiceInfo, code: Int) { done() }
            override fun onServiceResolved(info: NsdServiceInfo) {
                try {
                    val name = info.attributes["name"]?.toString(Charsets.UTF_8) ?: info.serviceName
                    val host = info.host
                    if (!closed && ticket == current && services.containsKey(info.serviceName) &&
                        name.length in 1..40 && name.none { it.isISOControl() } && name != config.name &&
                        info.port in 1..65535 && host != null && NearestLan.accepts(host) &&
                        info.attributes["hears"]?.toString(Charsets.UTF_8) != "0" &&
                        (known.size < 32 || known.containsKey(info.serviceName))) {
                        known[info.serviceName] = Peer(name, host, info.port, SystemClock.elapsedRealtime())
                    }
                } finally { done() }
            }
        }
        try { nsd.resolveService(service, listener) } catch (_: Exception) { done() }
    }
    override fun close() {
        if (closed) return
        closed = true; handler.removeCallbacksAndMessages(null)
        if (discovering) runCatching { nsd.stopServiceDiscovery(discovery) }
        if (registered) runCatching { nsd.unregisterService(registration) }
        known.clear(); services.clear(); synchronized(queue) { queue.clear(); ticket++ }
    }
}
