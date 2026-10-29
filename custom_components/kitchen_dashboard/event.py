"""Physical scene-button events for automations."""
from homeassistant.components.event import EventEntity, EventDeviceClass
from homeassistant.core import callback
from .const import SLOTS, SLOT_NAMES, DEFAULT_APPEARANCE
from .entity import DashboardEntity

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities(DashboardPress(entry.runtime_data, slot) for slot in SLOTS)

class DashboardPress(DashboardEntity, EventEntity):
    _attr_device_class = EventDeviceClass.BUTTON
    _attr_event_types = ['press']

    def __init__(self, hub, slot):
        super().__init__(hub, f'{slot}_press')
        self.slot = slot
        self._attr_name = SLOT_NAMES[slot] + ' press'
        self._attr_icon = hub.entry.options.get(f'{slot}_icon', DEFAULT_APPEARANCE[slot]['icon'])

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self.async_on_remove(self.hub.listen(self._pressed, presses=True))

    @callback
    def _pressed(self, slot):
        if slot == self.slot:
            self._trigger_event('press')
            self.async_write_ha_state()
