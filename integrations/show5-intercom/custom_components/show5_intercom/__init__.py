"""Private, authenticated Show intercom pilot; YAML configured, no public API."""
from __future__ import annotations

import asyncio
import base64
import logging
import secrets
import shlex
import struct
from urllib.parse import urlsplit

import aiohttp
import voluptuous as vol

from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.components import frontend, panel_custom, persistent_notification, websocket_api
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store

from .lease import LeaseGuard, RATE, decode_pcm

DOMAIN = "show5_intercom"
CAMERA = "com.github.digitallyrefined.androidipcamera"
COMPANION = "io.homeassistant.companion.android.minimal"
_LOGGER = logging.getLogger(__name__)
_DIAGNOSTIC_PHASES = frozenset({
    "mute_on_call", "mute_on_readback", "mute_off_call", "mute_off_readback",
    "adb_probe", "adb_grant_camera_mic", "adb_revoke_camera_mic",
    "adb_stop_camera", "adb_start_camera", "adb_stop_companion",
    "adb_start_companion", "adb_open_calls", "adb_wake",
})
CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required("camera_url"): cv.string,
        vol.Required("camera_username"): cv.string,
        vol.Required("camera_password"): cv.string,
        vol.Required("camera_certificate_sha256"): vol.Match(r"^[0-9a-fA-F]{64}$"),
        vol.Required("mute_entity"): cv.entity_id,
        vol.Optional("adb_entity"): cv.entity_id,
        vol.Optional("listen_enabled", default=False): cv.boolean,
        vol.Optional("video_enabled", default=False): cv.boolean,
        vol.Optional("call_panel", default=False): cv.boolean,
    })
}, extra=vol.ALLOW_EXTRA)


async def diagnostic_step(phase, operation):
    """Log fixed labels only; never command/output, exception text or URLs."""
    if phase not in _DIAGNOSTIC_PHASES:
        raise ValueError("Unsupported diagnostic phase")
    _LOGGER.info("SHOW5_BACKEND_STEP %s begin None", phase)
    try:
        result = await operation()
    except BaseException as error:
        category = "OtherError"
        for error_type, label in (
            (asyncio.CancelledError, "CancelledError"),
            (TimeoutError, "TimeoutError"),
            (PermissionError, "PermissionError"),
            (ConnectionError, "ConnectionError"),
            (OSError, "OSError"),
            (ValueError, "ValueError"),
        ):
            if isinstance(error, error_type):
                category = label
                break
        _LOGGER.warning("SHOW5_BACKEND_STEP %s failed %s", phase, category)
        raise
    _LOGGER.info("SHOW5_BACKEND_STEP %s success None", phase)
    return result


class Backend:
    def __init__(self, hass, config):
        self.hass, self.config = hass, config
        url = urlsplit(config["camera_url"])
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ("", "/"):
            raise ValueError("camera_url must be a plain HTTPS origin without credentials")
        self.origin = config["camera_url"].rstrip("/")
        self.ssl = aiohttp.Fingerprint(bytes.fromhex(config["camera_certificate_sha256"]))
        self.auth = aiohttp.BasicAuth(config["camera_username"], config["camera_password"])
        self.http = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=16, connect=4), trust_env=False)
        self.store = Store(hass, 1, DOMAIN + ".lease")
        self.guard = LeaseGuard(self.snapshot, self.prepare, self.restore, self.store.async_save)
        self.room = None
        self.recovery_pending = False

    async def snapshot(self):
        state = self.hass.states.get(self.config["mute_entity"])
        if state is None or state.state not in {"on", "off"}:
            raise ValueError("VACA mute state unavailable")
        return state.state == "on"

    def actor_context(self):
        lease = self.guard.active
        if lease and lease.owner != "recovery":
            return Context(user_id=lease.owner.split(":", 1)[0])
        # Startup recovery is internal restoration of our persisted lease.
        return Context()

    async def set_mute(self, muted):
        phase = "mute_on" if muted else "mute_off"
        async def call_switch():
            # Bound the service call as well as its separate confirmation window.
            async with asyncio.timeout(8):
                await self.hass.services.async_call("switch", "turn_on" if muted else "turn_off", {"entity_id": self.config["mute_entity"]}, blocking=True, context=self.actor_context())
        async def readback():
            async with asyncio.timeout(8):
                while await self.snapshot() != muted:
                    await asyncio.sleep(.2)
        await diagnostic_step(phase + "_call", call_switch)
        await diagnostic_step(phase + "_readback", readback)

    async def request(self, method, path, data=None):
        # Only fixed paths selected in code. No redirect or client-provided URL.
        async with self.http.request(method, self.origin + path, auth=self.auth, ssl=self.ssl, data=data, allow_redirects=False) as response:
            if response.status != 200:
                raise ValueError("Camera refused the request")
            content = await response.content.read(4097)
            if len(content) > 4096:
                raise ValueError("Unexpected camera response")
            return content

    async def adb(self, action, context=None):
        entity = self.config.get("adb_entity")
        # Fixed action allowlist. A client cannot supply an Android command.
        actions = {
            "probe": 'test "$(getprop ro.product.device)" = cronos && test "$(id -u)" = 2000',
            "grant_camera_mic": f"pm grant {CAMERA} android.permission.RECORD_AUDIO",
            "revoke_camera_mic": f"pm revoke {CAMERA} android.permission.RECORD_AUDIO",
            "stop_camera": f"am force-stop {CAMERA} && if pidof {CAMERA} >/dev/null; then exit 1; fi",
            "start_camera": f"am start -n {CAMERA}/.activities.MainActivity",
            "stop_companion": f"am force-stop {COMPANION} && if pidof {COMPANION} >/dev/null; then exit 1; fi",
            "start_companion": "am start -a android.intent.action.VIEW -d 'homeassistant://navigate/echo-show/home?server=default' -p " + COMPANION,
            "open_calls": (f"am force-stop {COMPANION} && " if self.config.get("call_panel") else "") + "am start -a android.intent.action.VIEW -d 'homeassistant://navigate/" + ("show5-call" if self.config.get("call_panel") else "echo-show/receive") + "?server=default' -p " + COMPANION,
            "wake": "input keyevent 224",
        }
        if action not in actions:
            raise ValueError("Unsupported device action")
        marker = "SHOW5_" + secrets.token_hex(12)
        command = actions[action] + " && echo " + shlex.quote(marker)
        async def run():
            if not entity or not self.hass.services.has_service("androidtv", "adb_command"):
                raise ValueError("Verified Android Debug Bridge adapter unavailable")
            async with asyncio.timeout(12):
                await self.hass.services.async_call("androidtv", "adb_command", {"entity_id": entity, "command": command}, blocking=True, context=context or self.actor_context())
            state = self.hass.states.get(entity)
            output = state.attributes.get("adb_response", "") if state else ""
            if not str(output).rstrip().endswith(marker):
                raise ValueError("Device action was not confirmed")
        await diagnostic_step("adb_" + action, run)

    async def prepare(self, mode):
        if mode != "talk" and (not self.config.get(mode + "_enabled") or not self.config.get("adb_entity")):
            raise ValueError("This mode has not been enabled with a verified device adapter")
        await self.set_mute(True)
        # VACA0.13.4 software mute cancels its recorder flow. This grace is not
        # an assertion of HAL exclusivity; operator acceptance checks are required.
        await asyncio.sleep(.5)
        if mode == "listen":
            await self.adb("stop_camera")
            await self.adb("grant_camera_mic")
            await self.adb("start_camera")
            # Recreate the foreground service after permission changes; Android11
            # may otherwise retain its original camera-only foreground type.
            await self.wait_camera()
        elif mode == "video":
            await self.adb("stop_camera")
            await self.adb("wake")

    async def restore(self, mode, prior_muted):
        try:
            await self._restore_resources(mode, prior_muted)
        except BaseException:
            self.report_recovery_error()
            raise

    async def wait_camera(self):
        async with asyncio.timeout(15):
            while True:
                try:
                    await self.request("GET", "/control/status")
                    return
                except (aiohttp.ClientError, OSError):
                    await asyncio.sleep(.5)

    async def _restore_resources(self, mode, prior_muted):
        if mode == "listen":
            # Permission revocation can terminate the camera process. Restart
            # it deliberately, rather than assuming video survives revocation.
            await self.adb("revoke_camera_mic")
            await self.adb("start_camera")
            await self.wait_camera()
            await self.adb("start_companion")
        elif mode == "video":
            # A crashed/disconnected browser cannot acknowledge track.stop().
            # Stop the known call host so it cannot retain camera/mic ownership.
            await self.adb("stop_companion")
            await self.adb("start_camera")
            await self.wait_camera()
            await self.adb("start_companion")
        # AndroidIPCamera's AudioTrack watchdog stops after >1.5s idle.
        await asyncio.sleep(2.5)
        await self.set_mute(prior_muted)

    async def upload(self, pcm):
        async def run():
            await self.request("POST", "/audio/upload", pcm)
            # The response proves accepted bytes, not audible speech. Conservatively
            # keep VACA muted for the full clip duration after the final response.
            await asyncio.sleep(len(pcm) / (RATE * 2))
            return {"accepted_bytes": len(pcm), "audible_verified": False}
        return run

    async def listen(self, seconds):
        async def run():
            async with self.http.get(self.origin + "/audio", auth=self.auth, ssl=self.ssl, allow_redirects=False) as response:
                if response.status != 200:
                    raise ValueError("Camera microphone stream unavailable")
                header = await response.content.readexactly(44)
                if header[:4] != b"RIFF" or header[8:16] != b"WAVEfmt " or header[36:40] != b"data" or struct.unpack_from("<HHI", header, 20) != (1, 1, RATE) or struct.unpack_from("<H", header, 34)[0] != 16:
                    raise ValueError("Unexpected camera audio format")
                pcm = await response.content.readexactly(RATE * 2 * seconds)
            # Exiting the response closes our only audio subscriber. No disk write.
            return {"pcm": base64.b64encode(pcm).decode(), "sample_rate": RATE}
        return run

    async def close(self):
        try:
            lease = self.guard.active
            if lease:
                await self.guard.end(lease.token, lease.owner)
        finally:
            await self.http.close()

    def report_recovery_error(self):
        persistent_notification.async_create(self.hass,
            "The Show intercom could not restore its camera/microphone state. New sessions are blocked. Check the device, then use Recover in the intercom card as an administrator.",
            title="Show intercom needs recovery", notification_id=DOMAIN)


def backend_for(hass, connection):
    backend = hass.data[DOMAIN]
    # This pilot controls Android permissions/processes as well as audio. Mere
    # permission to toggle the VACA mute entity is not an intercom authorization.
    if connection.user is None or not connection.user.is_admin:
        raise ValueError("Administrator access is required for this private pilot")
    if not connection.user.permissions.check_entity(backend.config["mute_entity"], POLICY_CONTROL):
        raise ValueError("Control permission for this Show is required")
    return backend


def owner(connection):
    return connection.user.id + ":" + str(id(connection))


async def reply(connection, msg, operation):
    try:
        connection.send_result(msg["id"], await operation())
    except (Exception, asyncio.CancelledError):
        # Never return network exception strings containing addresses or auth data.
        connection.send_error(msg["id"], "intercom_failed", "Intercom request failed; check device status before retrying.")


@websocket_api.websocket_command({vol.Required("type"): DOMAIN + "/status"})
@websocket_api.async_response
async def status(hass, connection, msg):
    async def run():
        backend = backend_for(hass, connection)
        return {"active": backend.guard.active is not None, "needs_recovery": backend.guard.cleanup_error,
                "recovery_pending": backend.recovery_pending,
                "listen_enabled": backend.config["listen_enabled"], "video_enabled": backend.config["video_enabled"]}
    await reply(connection, msg, run)


@websocket_api.websocket_command({vol.Required("type"): DOMAIN + "/begin", vol.Optional("mode", default="talk"): vol.In(["talk", "listen"])})
@websocket_api.async_response
async def begin(hass, connection, msg):
    async def run():
        backend = backend_for(hass, connection)
        if backend.recovery_pending:
            raise ValueError("Startup recovery is still running")
        if msg["mode"] == "listen" and not (backend.config["listen_enabled"] and backend.config.get("adb_entity")):
            raise ValueError("Listening has not been enabled")
        if msg["mode"] == "listen":
            # Check the trusted adapter before taking the microphone lease. A
            # reboot-lost network ADB connection must not mute normal VACA.
            await backend.adb("probe", Context(user_id=connection.user.id))
        lease = await backend.guard.acquire(owner(connection), msg["mode"])
        return {"session": lease.token, "expires_in": 45}
    await reply(connection, msg, run)


@websocket_api.websocket_command({vol.Required("type"): DOMAIN + "/upload", vol.Required("session"): cv.string,
                                vol.Required("pcm"): vol.All(cv.string, vol.Length(max=1176000))})
@websocket_api.async_response
async def upload(hass, connection, msg):
    async def run():
        backend = backend_for(hass, connection)
        pcm = decode_pcm(msg["pcm"])
        action = await backend.upload(pcm)
        return await backend.guard.perform(msg["session"], owner(connection), "talk", action)
    await reply(connection, msg, run)


@websocket_api.websocket_command({vol.Required("type"): DOMAIN + "/listen", vol.Required("session"): cv.string,
                                vol.Optional("seconds", default=5): vol.All(int, vol.Range(min=1, max=10))})
@websocket_api.async_response
async def listen(hass, connection, msg):
    async def run():
        backend = backend_for(hass, connection)
        action = await backend.listen(msg["seconds"])
        return await backend.guard.perform(msg["session"], owner(connection), "listen", action)
    await reply(connection, msg, run)


@websocket_api.websocket_command({vol.Required("type"): DOMAIN + "/end", vol.Required("session"): cv.string})
@websocket_api.async_response
async def end(hass, connection, msg):
    async def run():
        backend = backend_for(hass, connection)
        await backend.guard.end(msg["session"], owner(connection))
        return {"ended": True}
    await reply(connection, msg, run)


@websocket_api.websocket_command({vol.Required("type"): DOMAIN + "/recover"})
@websocket_api.require_admin
@websocket_api.async_response
async def recover(hass, connection, msg):
    async def run():
        backend = backend_for(hass, connection)
        if backend.recovery_pending:
            raise ValueError("Startup recovery is still running")
        lease = backend.guard.active
        if lease and not backend.guard.cleanup_error:
            raise ValueError("An active session must end normally")
        if lease:
            await backend.guard.end(lease.token, lease.owner)
        if backend.room:
            await backend.room.finish()
        persistent_notification.async_dismiss(hass, DOMAIN)
        return {"recovered": True}
    await reply(connection, msg, run)


async def register_call_panel(hass, config):
    """Register the optional receiver without loading Lovelace resources."""
    if not config.get("call_panel"):
        return
    if not config.get("video_enabled") or not config.get("adb_entity"):
        raise ValueError("The call panel requires enabled video and a verified adapter")
    # Never replace another integration's route.
    if "show5-call" in hass.data.get(frontend.DATA_PANELS, {}):
        raise ValueError("The Show call panel route is already registered")
    await panel_custom.async_register_panel(
        hass, frontend_url_path="show5-call", webcomponent_name="show5-call-panel",
        module_url="/local/show5-call-panel.js", require_admin=True,
    )


async def async_setup(hass: HomeAssistant, config):
    if DOMAIN not in config:
        return True
    backend = Backend(hass, config[DOMAIN])
    try:
        await register_call_panel(hass, config[DOMAIN])
    except Exception:
        await backend.http.close()
        raise
    hass.data[DOMAIN] = backend
    record = await backend.store.async_load()
    if record:
        backend.recovery_pending = True
        async def startup_recovery(_event=None):
            try:
                await backend.guard.recover(record)
            except Exception:
                backend.guard.cleanup_error = True
                backend.report_recovery_error()
            finally:
                backend.recovery_pending = False
        if hass.is_running:
            await startup_recovery()
        else:
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, startup_recovery)
    for command in (status, begin, upload, listen, end, recover):
        websocket_api.async_register_command(hass, command)
    from .room import Room, register
    backend.room = Room(hass, backend)
    register(hass)
    async def stop(_event):
        await backend.close()
    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, stop)
    return True
