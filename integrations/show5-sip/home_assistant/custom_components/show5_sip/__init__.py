"""Private Show SIP controls over the existing authenticated AndroidTV adapter."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging

try:
    import probatio as vol
except ImportError:  # Home Assistant releases before the schema migration.
    import voluptuous as vol

from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.core import Context, HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .controller import Endpoint
from .protocol import DOMAIN, ProtocolError, call_id, slug, validate_endpoint

_LOGGER = logging.getLogger(__name__)
PLATFORMS = ["sensor", "button"]


def validate_configuration(values):
    """One configured controller per physical Show and AndroidTV entity."""
    if not isinstance(values, list) or not 1 <= len(values) <= 16:
        raise vol.Invalid("Configure one to sixteen Show SIP endpoints")
    try:
        endpoints = [validate_endpoint(value) for value in values]
    except ProtocolError as exc:
        raise vol.Invalid(str(exc)) from None
    for key in ("endpoint_id", "serial", "adb_entity"):
        if len({entry[key] for entry in endpoints}) != len(endpoints):
            raise vol.Invalid("Duplicate Show SIP " + key)
    return endpoints


CONFIG_SCHEMA = vol.Schema({vol.Optional(DOMAIN): validate_configuration}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config):
    hass.data.setdefault(DOMAIN, {})
    for endpoint in config.get(DOMAIN, []):
        hass.async_create_task(hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=endpoint
        ))
    return True


async def require_operator(hass, context, adb_entity):
    """A button or service call must originate from an authorized administrator."""
    user_id = context.user_id if context is not None else None
    user = await hass.auth.async_get_user(user_id) if user_id else None
    if user is None or not user.is_active or not user.is_admin or not user.permissions.check_entity(adb_entity, POLICY_CONTROL):
        raise HomeAssistantError("Show SIP call controls require an active administrator")


class ShowCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=entry.title, config_entry=entry,
                         update_interval=timedelta(seconds=10))
        self.endpoint = Endpoint(dict(entry.data), self._execute)

    async def _execute(self, command, context=None):
        entity = self.endpoint.config["adb_entity"]
        state = self.hass.states.get(entity)
        if state is None or state.state in {"unknown", "unavailable"}:
            raise ProtocolError("adb_unavailable")
        try:
            async with asyncio.timeout(10):
                await self.hass.services.async_call(
                    "androidtv", "adb_command", {"entity_id": entity, "command": command},
                    blocking=True, context=context or Context()
                )
        except Exception:
            # Third-party ADB exceptions may include command output or network details.
            raise ProtocolError("adb_request_failed") from None
        state = self.hass.states.get(entity)
        if state is None:
            raise ProtocolError("adb_unavailable")
        return state.attributes.get("adb_response", "")

    async def _async_update_data(self):
        try:
            status = await self.endpoint.refresh()
        except Exception:
            raise UpdateFailed("Show SIP status is unavailable") from None
        self.update_interval = timedelta(seconds=5 if status.state != "idle" or status.lease_held else 10)
        return status

    async def operate(self, command, context, *, contact_id=None, expected_call_id=None):
        await require_operator(self.hass, context, self.endpoint.config["adb_entity"])
        try:
            async with asyncio.timeout(35):
                status = await self.endpoint.command(command, contact_id=contact_id,
                                                     expected_call_id=expected_call_id, context=context)
        except ProtocolError as exc:
            raise HomeAssistantError("Show SIP: " + str(exc)) from None
        except TimeoutError:
            raise HomeAssistantError("Show SIP command timed out; inspect status before retrying") from None
        self.update_interval = timedelta(seconds=5 if status.state != "idle" or status.lease_held else 10)
        self.async_set_updated_data(status)
        # An accepted dial is not a connected call, and an accepted hangup can still be ending.
        return {"accepted": True, **status.public()}


async def _reload(hass, entry):
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    validate_endpoint(dict(entry.data))
    entries = hass.data.setdefault(DOMAIN, {})
    for other in entries.values():
        other_config = other.endpoint.config
        if any(other_config[key] == entry.data[key] for key in ("endpoint_id", "serial", "adb_entity")):
            raise HomeAssistantError("A Show SIP controller already owns this endpoint")
    coordinator = ShowCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entries[entry.entry_id] = coordinator
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except BaseException:
        entries.pop(entry.entry_id, None)
        raise
    entry.async_on_unload(entry.add_update_listener(_reload))

    if not hass.services.has_service(DOMAIN, "dial"):
        async def control(call: ServiceCall):
            matches = [value for value in hass.data.get(DOMAIN, {}).values()
                       if value.endpoint.config["endpoint_id"] == call.data["endpoint_id"]]
            if len(matches) != 1:
                raise HomeAssistantError("Show SIP endpoint is not available")
            return await matches[0].operate(call.service, call.context,
                                           contact_id=call.data.get("contact_id"),
                                           expected_call_id=call.data.get("expected_call_id"))

        for service in ("dial", "answer", "decline", "hangup"):
            fields = {vol.Required("endpoint_id"): vol.All(cv.string, slug)}
            fields[vol.Required("contact_id" if service == "dial" else "expected_call_id")] = vol.All(
                cv.string, slug if service == "dial" else call_id)
            async_register_admin_service(hass, DOMAIN, service, control,
                                         schema=vol.Schema(fields), supports_response=SupportsResponse.OPTIONAL)
    return True


async def async_unload_entry(hass, entry):
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        if not hass.data[DOMAIN]:
            for service in ("dial", "answer", "decline", "hangup"):
                hass.services.async_remove(DOMAIN, service)
    # Unloading the controls must not terminate a phone call or change microphone ownership.
    return unloaded
