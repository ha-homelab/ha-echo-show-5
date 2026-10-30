"""Configure reviewed, credential-free bindings through HA's admin setup flow."""
import json

try:
    import probatio as vol
except ImportError:  # Home Assistant releases before the schema migration.
    import voluptuous as vol

from homeassistant.config_entries import ConfigFlow

from .protocol import DOMAIN, ProtocolError, validate_endpoint


def parse_endpoint_document(value):
    """Accept only a bounded endpoint object, without duplicate or secret fields."""
    if not isinstance(value, str) or not 1 <= len(value) <= 16384:
        raise ProtocolError("invalid_endpoint_document")

    def unique_object(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ProtocolError("duplicate_configuration_field")
            result[key] = item
        return result

    try:
        return validate_endpoint(json.loads(value, object_pairs_hook=unique_object))
    except (ValueError, TypeError, RecursionError):
        raise ProtocolError("invalid_endpoint_document") from None


class ShowSipConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def _create_endpoint(self, data, *, imported=False):
        await self.async_set_unique_id(data["endpoint_id"])
        for entry in self._async_current_entries():
            if entry.unique_id == data["endpoint_id"] and not imported and dict(entry.data) != data:
                return self.async_abort(reason="endpoint_id_in_use")
            if entry.unique_id != data["endpoint_id"] and any(entry.data.get(key) == data[key] for key in ("serial", "adb_entity")):
                return self.async_abort(reason="duplicate_endpoint")
        # UI retries are idempotent and cannot silently replace an existing binding.
        self._abort_if_unique_id_configured(updates=data if imported else None)
        return self.async_create_entry(title=data["name"], data=data)

    async def async_step_import(self, user_input):
        try:
            data = validate_endpoint(user_input)
        except ProtocolError:
            return self.async_abort(reason="invalid_configuration")
        return await self._create_endpoint(data, imported=True)

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                if not isinstance(user_input, dict) or set(user_input) != {"endpoint"}:
                    raise ProtocolError("invalid_endpoint_document")
                data = parse_endpoint_document(user_input["endpoint"])
            except ProtocolError:
                errors["endpoint"] = "invalid_configuration"
            else:
                return await self._create_endpoint(data)
        # The built-in config-entry REST/UI endpoint enforces administrator access.
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("endpoint"): str,
        }), errors=errors)
