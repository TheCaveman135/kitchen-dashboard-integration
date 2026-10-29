"""A Home Assistant integration for the Kitchen Dashboard touchscreen."""
from __future__ import annotations
import asyncio
from collections import deque
from collections.abc import Callable
import logging
import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .client import CannotConnect, DashboardClient
from .const import DOMAIN, PLATFORMS, SLOTS, appearance_options, migrate_appearance_options

_LOGGER = logging.getLogger(__name__)

async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if entry.version == 1:
        data = {key: value for key, value in entry.data.items() if key != 'pairing_key'}
        hass.config_entries.async_update_entry(entry, data=data, version=2)
    if entry.version == 2:
        hass.config_entries.async_update_entry(entry, options=migrate_appearance_options(entry.options), version=3)
    return entry.version == 3

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    hub = DashboardHub(hass, entry)
    try:
        await hub.client.connect(hub.mapped_slots, appearance_options(entry.options))
        if hub.client.info['device_id'] != entry.unique_id:
            await hub.client.close()
            raise ConfigEntryNotReady('A different dashboard is at this address; reconfigure the entry')
    except CannotConnect as error:
        raise ConfigEntryNotReady(str(error)) from error
    entry.runtime_data = hub
    await hass.config_entries.async_forward_entry_setups(entry, [Platform(p) for p in PLATFORMS])
    hub.start()
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, [Platform(p) for p in PLATFORMS]):
        await entry.runtime_data.stop()
        return True
    return False

class DashboardHub:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        self.hass, self.entry = hass, entry
        self.client = DashboardClient(async_get_clientsession(hass), entry.data[CONF_HOST], entry.data[CONF_PORT])
        self.listeners: set[Callable] = set()
        self.press_listeners: set[Callable] = set()
        self.seen = deque(maxlen=256)
        self.tasks: set[asyncio.Task] = set()
        self.runner = None
        self.stopping = False

    @property
    def mapped_slots(self):
        return [slot for slot in SLOTS if self.entry.options.get(slot)]

    @callback
    def listen(self, callback_func, *, presses=False):
        listeners = self.press_listeners if presses else self.listeners
        listeners.add(callback_func)
        return lambda: listeners.discard(callback_func)

    @callback
    def notify(self):
        for listener in list(self.listeners):
            listener()

    def start(self):
        self.runner = self.hass.async_create_background_task(self._run(), 'Kitchen Dashboard connection')

    async def _run(self):
        delay = 1
        while not self.stopping:
            try:
                if not self.client.connected:
                    await self.client.connect(self.mapped_slots, appearance_options(self.entry.options))
                    if self.client.info['device_id'] != self.entry.unique_id:
                        raise CannotConnect('Dashboard identity changed')
                delay = 1
                self.notify()
                await self.client.listen(self._message)
            except (CannotConnect, aiohttp.ClientError, OSError, ValueError, TypeError) as error:
                _LOGGER.debug('Dashboard connection lost: %s', type(error).__name__)
            finally:
                await self.client.close()
                self.notify()
            if not self.stopping:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30)

    async def _message(self, data):
        if data.get('type') == 'state':
            self.notify()
        elif data.get('type') == 'press':
            press_id, slot = data.get('press_id'), data.get('slot')
            if not isinstance(press_id, str) or len(press_id) > 128 or slot not in SLOTS or press_id in self.seen:
                return
            self.seen.append(press_id)
            for listener in list(self.press_listeners):
                listener(slot)
            if not data.get('managed', False):
                return
            task = self.hass.async_create_task(self._activate(slot, press_id), f'Kitchen Dashboard {slot}')
            self.tasks.add(task)
            task.add_done_callback(self.tasks.discard)

    async def _activate(self, slot, press_id):
        entity_id = self.entry.options.get(slot)
        success = False
        try:
            if not isinstance(entity_id, str) or entity_id.split('.')[0] not in ('scene', 'script'):
                raise HomeAssistantError('No scene or script assigned')
            state = self.hass.states.get(entity_id)
            if state is None or state.state == 'unavailable':
                raise HomeAssistantError('Assigned scene or script is unavailable')
            async with asyncio.timeout(8):
                await self.hass.services.async_call(entity_id.split('.')[0], 'turn_on', {'entity_id': entity_id}, blocking=True)
            success = True
        except (HomeAssistantError, TimeoutError) as error:
            _LOGGER.warning('Unable to activate dashboard slot %s: %s', slot, error)
        finally:
            try:
                await self.client.acknowledge(press_id, success)
            except (aiohttp.ClientError, OSError, RuntimeError):
                pass

    async def stop(self):
        self.stopping = True
        if self.runner:
            self.runner.cancel()
            await asyncio.gather(self.runner, return_exceptions=True)
        for task in list(self.tasks):
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)
        await self.client.close()
