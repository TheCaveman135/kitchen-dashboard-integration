"""Diagnostics omit legacy credentials retained by older entries."""
from homeassistant.components.diagnostics import async_redact_data

async def async_get_config_entry_diagnostics(hass, entry):
    hub = entry.runtime_data
    return {'entry': async_redact_data(entry.as_dict(), {'pairing_key'}),
            'connected': hub.client.connected, 'device': hub.client.info,
            'state': hub.client.state}
