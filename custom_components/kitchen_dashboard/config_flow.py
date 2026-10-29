"""Connect a local dashboard and customize its three scene buttons."""
from __future__ import annotations
import json
from pathlib import Path
import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlowWithReload
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .client import CannotConnect, DashboardClient
from .const import DEFAULT_PORT, DEFAULT_APPEARANCE, DOMAIN, SLOTS, appearance_options

SUPPORTED_ICONS = frozenset(json.loads(Path(__file__).with_name('supported_icons.json').read_text()))


def connection_schema(defaults=None):
    defaults = defaults or {}
    return vol.Schema({
        vol.Required(CONF_HOST, default=defaults.get(CONF_HOST, '')): str,
        vol.Required(CONF_PORT, default=defaults.get(CONF_PORT, DEFAULT_PORT)): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
    })


async def validate(hass, data):
    host = data[CONF_HOST].strip()
    if not host or any(char in host for char in ('/', '@', ' ', '?', '#')):
        raise CannotConnect('Enter a hostname or IP address without a URL prefix')
    data[CONF_HOST] = host
    client = DashboardClient(async_get_clientsession(hass), host, data[CONF_PORT])
    try:
        return await client.connect()
    finally:
        await client.close()


class KitchenDashboardConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 3

    async def async_step_user(self, user_input=None):
        return await self._connection_step('user', user_input)

    async def async_step_reconfigure(self, user_input=None):
        return await self._connection_step('reconfigure', user_input)

    async def _connection_step(self, step, user_input):
        errors = {}
        entry = self._get_reconfigure_entry() if step == 'reconfigure' else None
        if user_input is not None:
            try:
                info = await validate(self.hass, user_input)
                await self.async_set_unique_id(info['device_id'])
                if entry:
                    if entry.unique_id != info['device_id']:
                        return self.async_abort(reason='wrong_device')
                    return self.async_update_reload_and_abort(entry, data_updates=user_input)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title=info.get('name', 'Kitchen Dashboard'), data=user_input)
            except (CannotConnect, ValueError):
                errors['base'] = 'cannot_connect'
        return self.async_show_form(step_id=step, data_schema=connection_schema(entry.data if entry else user_input), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return KitchenDashboardOptionsFlow()


class KitchenDashboardOptionsFlow(OptionsFlowWithReload):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            selected = {key: value for key, value in user_input.items() if value not in (None, '')}
            entities = {key: value for key, value in selected.items() if key in SLOTS}
            if any(not isinstance(value, str) or value.split('.')[0] not in ('scene', 'script') or self.hass.states.get(value) is None for value in entities.values()):
                errors['base'] = 'invalid_entity'
            else:
                for style in appearance_options(selected).values():
                    if not isinstance(style['icon'], str) or style['icon'] not in SUPPORTED_ICONS:
                        errors['base'] = 'invalid_icon'
                        break
                    for field in ('color', 'background'):
                        rgb = style[field]
                        if not isinstance(rgb, list) or len(rgb) != 3 or any(type(n) is not int or not 0 <= n <= 255 for n in rgb):
                            errors['base'] = 'invalid_color'
                if not errors:
                    return self.async_create_entry(title='', data=selected)
        schema = {}
        defaults = {**{f'{slot}_{field}': value for slot, style in DEFAULT_APPEARANCE.items() for field, value in style.items()}, **self.config_entry.options}
        for slot in SLOTS:
            schema[vol.Optional(slot)] = selector.EntitySelector(selector.EntitySelectorConfig(domain=['scene', 'script']))
            schema[vol.Optional(f'{slot}_icon', default=defaults[f'{slot}_icon'])] = selector.IconSelector()
            for field in ('color', 'background'):
                schema[vol.Optional(f'{slot}_{field}', default=defaults[f'{slot}_{field}'])] = selector.ColorRGBSelector()
        return self.async_show_form(step_id='init', data_schema=self.add_suggested_values_to_schema(vol.Schema(schema), defaults), errors=errors)
