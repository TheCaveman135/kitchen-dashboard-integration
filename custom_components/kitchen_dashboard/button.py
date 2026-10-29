"""Wake the dashboard or activate its configured scene buttons."""
from homeassistant.components.button import ButtonEntity
from homeassistant.exceptions import HomeAssistantError
from .client import CannotConnect
from .const import SLOTS, SLOT_NAMES, DEFAULT_APPEARANCE
from .entity import DashboardEntity

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([DashboardButton(entry.runtime_data, slot) for slot in (*SLOTS, 'wake')])

class DashboardButton(DashboardEntity, ButtonEntity):
    def __init__(self, hub, slot):
        super().__init__(hub, f'activate_{slot}')
        self.slot = slot
        self._attr_name = 'Wake screen' if slot == 'wake' else SLOT_NAMES[slot]
        self._attr_icon = hub.entry.options.get(f'{slot}_icon', DEFAULT_APPEARANCE[slot]['icon']) if slot != 'wake' else 'mdi:monitor'

    async def async_press(self):
        try:
            if self.slot == 'wake':
                await self.hub.client.request('wake')
            else:
                await self.hub.client.request('press', slot=self.slot)
        except CannotConnect as error:
            raise HomeAssistantError(str(error)) from error
