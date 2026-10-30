package com.msp1974.vacompanion.nearest

import java.net.InetAddress

internal object NearestLan {
    fun accepts(address: InetAddress): Boolean {
        if (address.isAnyLocalAddress || address.isLoopbackAddress || address.isMulticastAddress) return false
        val b = address.address.map { it.toInt() and 255 }
        return when (b.size) {
            4 -> b[0] == 10 || (b[0] == 172 && b[1] in 16..31) ||
                (b[0] == 192 && b[1] == 168) || (b[0] == 169 && b[1] == 254)
            16 -> (b[0] and 254) == 252 || (b[0] == 254 && (b[1] and 192) == 128)
            else -> false
        }
    }
}
