"""Read-only app state. Active means media is running, not acoustic acceptance."""
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity

from .entity import ShowEntity
from .protocol import DOMAIN, REGISTRATIONS, STATES


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([ShowSipSensor(coordinator, "registration"), ShowSipSensor(coordinator, "call")])


class ShowSipSensor(ShowEntity, SensorEntity):
    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(self, coordinator, kind):
        super().__init__(coordinator, "sip_" + kind, "SIP " + kind)
        self.kind = kind
        self._attr_options = sorted(REGISTRATIONS if kind == "registration" else STATES)
        self._attr_icon = "mdi:phone-check" if kind == "registration" else "mdi:phone-in-talk"

    @property
    def native_value(self):
        data = self.coordinator.data
        if data is None:
            return None
        return data.registration if self.kind == "registration" else data.state

    @property
    def extra_state_attributes(self):
        data = self.coordinator.data
        if data is None or self.kind == "registration":
            return None
        return {key: value for key, value in data.public().items() if key not in {"registration", "state"}}
