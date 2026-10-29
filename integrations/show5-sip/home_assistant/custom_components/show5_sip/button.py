"""Call controls; every terminal action is bound to a particular call ID."""
from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError

from .entity import ShowEntity
from .protocol import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    buttons = [ShowSipButton(coordinator, command) for command in ("answer", "decline", "hangup")]
    buttons.extend(ShowSipButton(coordinator, "dial", contact) for contact in coordinator.endpoint.config["contacts"])
    async_add_entities(buttons)


class ShowSipButton(ShowEntity, ButtonEntity):
    def __init__(self, coordinator, command, contact=None):
        self.command, self.contact = command, contact
        name = "Call " + contact["label"] if contact else {"answer": "Answer call", "decline": "Decline call", "hangup": "Hang up"}[command]
        key = "sip_dial_" + contact["id"] if contact else "sip_" + command
        super().__init__(coordinator, key, name)
        self._attr_icon = {"dial": "mdi:phone-outgoing", "answer": "mdi:phone-incoming", "decline": "mdi:phone-cancel", "hangup": "mdi:phone-hangup"}[command]

    @property
    def available(self):
        if not super().available or self.coordinator.data is None:
            return False
        data = self.coordinator.data
        if self.command == "dial":
            return data.configured and data.registration == "registered" and data.state in {"idle", "error"} and not data.lease_held and data.call_id is None
        if self.command in {"answer", "decline"}:
            return data.state == "ringing" and data.call_id is not None
        return data.state in {"ringing", "preparing", "dialing", "active", "ending"} and data.call_id is not None

    async def async_press(self):
        data = self.coordinator.data
        if data is None:
            raise HomeAssistantError("Show SIP status is unavailable")
        await self.coordinator.operate(self.command, self._context,
                                       contact_id=self.contact["id"] if self.contact else None,
                                       expected_call_id=None if self.contact else data.call_id)
