"""Dashboard connectivity and display state."""
from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.helpers.entity import EntityCategory
from .entity import DashboardEntity

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([DashboardStatus(entry.runtime_data, key) for key in ('connected','screen_awake','lights_online')])

class DashboardStatus(DashboardEntity, BinarySensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    def __init__(self, hub, key):
        super().__init__(hub, key)
        self.key = key
        self._attr_name = {'connected':'Connection','screen_awake':'Screen awake','lights_online':'Lights online'}[key]
        if key in ('connected','lights_online'):
            self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def available(self):
        return self.key == 'connected' or self.hub.client.connected

    @property
    def is_on(self):
        if self.key == 'connected':
            return self.hub.client.connected
        if self.key == 'screen_awake':
            return not self.hub.client.state.get('sleeping', False)
        return self.hub.client.state.get('lights_online', False)
