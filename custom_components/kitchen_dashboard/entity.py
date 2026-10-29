"""Common device identity and push updates."""
from homeassistant.core import callback
from homeassistant.helpers.entity import DeviceInfo, Entity
from .const import DOMAIN

class DashboardEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, hub, key):
        self.hub = hub
        self._attr_unique_id = f'{hub.entry.unique_id}_{key}'
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, hub.entry.unique_id)}, name=hub.entry.title, manufacturer='Kitchen Dashboard', model='Touchscreen dashboard', sw_version=hub.client.info.get('version'))

    @property
    def available(self):
        return self.hub.client.connected

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self.hub.listen(self._updated))

    @callback
    def _updated(self):
        self.async_write_ha_state()
