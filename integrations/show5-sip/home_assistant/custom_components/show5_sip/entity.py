"""Shared identity without exposing SIP credentials or hardware serials."""
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .protocol import DOMAIN


class ShowEntity(CoordinatorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, key, name):
        super().__init__(coordinator)
        config = coordinator.endpoint.config
        self._attr_unique_id = config["endpoint_id"] + "_" + key
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, config["endpoint_id"])}, name=config["name"],
            manufacturer="HA Homelab", model="Echo Show SIP endpoint"
        )
