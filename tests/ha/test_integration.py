"""Run inside a Home Assistant Python environment; no live devices or HA config used."""
import asyncio
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import uuid
from aiohttp import web
from homeassistant.core import HomeAssistant
from homeassistant import loader
from homeassistant.bootstrap import async_from_config_dict
from homeassistant.config_entries import SOURCE_USER

ROOT = Path(__file__).resolve().parents[2]
TOKEN = 'test-only-key-do-not-use-on-a-device'

class FakeDashboard:
    def __init__(self):
        self.device_id = str(uuid.uuid4())
        self.sockets = []
        self.subscriptions = []
        self.acks = []
        self.commands = []
    async def websocket(self, request):
        ws = web.WebSocketResponse(heartbeat=10)
        await ws.prepare(request)
        self.sockets.append(ws)
        await ws.send_json({'type':'hello','protocol':2,'device_id':self.device_id,'name':'Kitchen Dashboard Test','version':'0.2.0','state':{'sleeping':False,'lights_online':True}})
        async for incoming in ws:
            if incoming.type != web.WSMsgType.TEXT: continue
            data = incoming.json()
            self.commands.append(data)
            if data['type']=='subscribe': self.subscriptions.append(data['slots'])
            if data['type']=='action_result': self.acks.append(data)
            if 'id' in data: await ws.send_json({'type':'result','id':data['id'],'success':True})
        return ws
    async def press(self, slot='cooking', press_id='test-press', managed=True):
        for ws in self.sockets:
            if not ws.closed:
                await ws.send_json({'type':'press','press_id':press_id,'slot':slot,'managed':managed})

class IntegrationTests(unittest.IsolatedAsyncioTestCase):
    temp_dirs = []

    @classmethod
    def tearDownClass(cls):
        # HA's namespace-package importer retains component directories per process.
        for directory in cls.temp_dirs:
            directory.cleanup()

    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.temp_dirs.append(self.temp)
        custom = Path(self.temp.name)/'custom_components'
        custom.mkdir()
        shutil.copytree(ROOT/'custom_components/kitchen_dashboard',custom/'kitchen_dashboard',ignore=shutil.ignore_patterns('__pycache__'))
        self.hass = HomeAssistant(self.temp.name)
        loader.async_setup(self.hass)
        self.hass.config.skip_pip = True
        await async_from_config_dict({'homeassistant':{'name':'Integration test','latitude':0,'longitude':0,'elevation':0,'unit_system':'metric','time_zone':'UTC'}},self.hass)
        self.fake = FakeDashboard()
        application = web.Application()
        application.router.add_get('/',self.fake.websocket)
        self.runner = web.AppRunner(application)
        await self.runner.setup()
        self.site = web.TCPSite(self.runner,'127.0.0.1',0)
        await self.site.start()
        self.port = self.site._server.sockets[0].getsockname()[1]
        self.calls = []
        async def action(call): self.calls.append(call.data['entity_id'])
        self.hass.services.async_register('scene','turn_on',action)
        self.hass.services.async_register('script','turn_on',action)
        self.hass.states.async_set('scene.test_cooking','unknown')
        self.hass.states.async_set('script.test_night','off')

    async def asyncTearDown(self):
        for entry in self.hass.config_entries.async_entries('kitchen_dashboard'):
            await self.hass.config_entries.async_unload(entry.entry_id)
        for ws in self.fake.sockets: await ws.close()
        await self.runner.cleanup()
        await self.hass.async_stop()

    async def setup_entry(self):
        result = await self.hass.config_entries.flow.async_init('kitchen_dashboard',context={'source':SOURCE_USER},data={'host':'127.0.0.1','port':self.port})
        self.assertEqual(result['type'],'create_entry',result)
        self.entry = result['result']
        await self.hass.async_block_till_done()
        self.assertTrue(self.entry.runtime_data.client.connected)
        return self.entry

    async def assign(self, **options):
        result = await self.hass.config_entries.options.async_init(self.entry.entry_id,data=options)
        self.assertEqual(result['type'],'create_entry',result)
        await self.hass.async_block_till_done()
        await asyncio.sleep(.1)

    async def test_setup_and_device_entities(self):
        await self.setup_entry()
        states = [s for s in self.hass.states.async_all() if 'kitchen_dashboard_test' in s.entity_id]
        self.assertEqual(len(states),10,[(s.entity_id,s.state) for s in states])
        self.assertIn([],self.fake.subscriptions)
        names={s.attributes.get('friendly_name') for s in states}
        for index in (1,2,3):
            self.assertIn(f'Kitchen Dashboard Test Custom Button {index}',names)
            self.assertIn(f'Kitchen Dashboard Test Custom Button {index} press',names)

    async def test_keyless_setup_form_and_entry(self):
        result = await self.hass.config_entries.flow.async_init('kitchen_dashboard',context={'source':SOURCE_USER})
        fields = {str(key) for key in result['data_schema'].schema}
        self.assertEqual(fields, {'host', 'port'})
        await self.setup_entry()
        self.assertNotIn('pairing_key', self.entry.data)
        self.assertFalse(any(c['type'] == 'auth' for c in self.fake.commands))

    async def test_legacy_entry_migrates_and_keeps_assignments(self):
        await self.setup_entry()
        await self.assign(cooking='scene.test_cooking')
        await self.hass.config_entries.async_unload(self.entry.entry_id)
        self.hass.config_entries.async_update_entry(self.entry, version=1, data={**self.entry.data, 'pairing_key': TOKEN})
        self.assertTrue(await self.hass.config_entries.async_setup(self.entry.entry_id))
        self.assertEqual(self.entry.version, 3)
        self.assertNotIn('pairing_key', self.entry.data)
        self.assertEqual(self.entry.options['cooking'], 'scene.test_cooking')

    async def test_old_saved_defaults_migrate_without_changing_custom_button_or_action(self):
        from custom_components.kitchen_dashboard.const import LEGACY_APPEARANCE
        await self.setup_entry()
        await self.hass.config_entries.async_unload(self.entry.entry_id)
        options = {f'{slot}_{field}': value for slot, style in LEGACY_APPEARANCE.items() for field, value in style.items()}
        options.update(cooking='scene.test_cooking', evening_icon='mdi:sofa', evening_color=[10,200,140])
        self.hass.config_entries.async_update_entry(self.entry, version=2, options=options)
        self.assertTrue(await self.hass.config_entries.async_setup(self.entry.entry_id))
        self.assertEqual(self.entry.version, 3)
        self.assertEqual(self.entry.options['cooking_icon'], 'mdi:numeric-1-circle-outline')
        self.assertEqual(self.entry.options['night_icon'], 'mdi:numeric-3-circle-outline')
        self.assertEqual(self.entry.options['cooking_color'], [216,216,216])
        self.assertEqual(self.entry.options['cooking'], 'scene.test_cooking')
        self.assertEqual(self.entry.options['evening_icon'], 'mdi:sofa')
        self.assertEqual(self.entry.options['evening_color'], [10,200,140])
        self.assertEqual(self.entry.options['evening_background'], options['evening_background'])

    async def test_icon_and_colors_sent_on_setup_and_reconnect(self):
        await self.setup_entry()
        await self.assign(cooking_icon='mdi:chef-hat', cooking_color=[20,220,130], cooking_background=[12,30,55])
        expected = {'icon':'mdi:chef-hat', 'color':[20,220,130], 'background':[12,30,55]}
        subs = [c for c in self.fake.commands if c['type']=='subscribe']
        self.assertEqual(subs[-1]['appearance']['cooking'], expected)
        for ws in self.fake.sockets: await ws.close()
        await asyncio.sleep(1.4)
        subs = [c for c in self.fake.commands if c['type']=='subscribe']
        self.assertEqual(subs[-1]['appearance']['cooking'], expected)

    async def test_unknown_icon_is_rejected(self):
        await self.setup_entry()
        result=await self.hass.config_entries.options.async_init(self.entry.entry_id,data={'night_icon':'mdi:unknown-unsupported-icon'})
        self.assertEqual(result['type'],'form')
        self.assertEqual(result['errors']['base'],'invalid_icon')

    async def test_options_route_scene_once_and_script(self):
        await self.setup_entry()
        await self.assign(cooking='scene.test_cooking',night='script.test_night')
        self.assertIn(['cooking','night'],self.fake.subscriptions)
        await self.fake.press()
        await self.fake.press()
        await self.fake.press('night','second-press')
        await asyncio.sleep(.2)
        await self.hass.async_block_till_done()
        self.assertEqual(self.calls,['scene.test_cooking','script.test_night'])
        self.assertEqual(len(self.fake.acks),2)
        self.assertTrue(all(a['success'] for a in self.fake.acks))
        events=[s for s in self.hass.states.async_all('event') if s.attributes.get('event_type')=='press']
        self.assertEqual(len(events),2)

    async def test_local_press_reports_event_without_calling_ha_action(self):
        await self.setup_entry()
        await self.fake.press(managed=False)
        await asyncio.sleep(.1)
        self.assertEqual(self.calls,[])
        events=[s for s in self.hass.states.async_all('event') if s.attributes.get('event_type')=='press']
        self.assertEqual(len(events),1)

    async def test_options_reject_non_scene_entity(self):
        await self.setup_entry()
        self.hass.states.async_set('light.other','off')
        result=await self.hass.config_entries.options.async_init(self.entry.entry_id,data={'cooking':'light.other'})
        self.assertEqual(result['type'],'form')
        self.assertEqual(result['errors']['base'],'invalid_entity')

    async def test_missing_scene_failure_and_no_local_replay_command(self):
        await self.setup_entry()
        await self.assign(cooking='scene.test_cooking')
        self.hass.states.async_remove('scene.test_cooking')
        await self.fake.press()
        await asyncio.sleep(.1)
        self.assertFalse(self.fake.acks[-1]['success'])
        self.assertEqual(self.calls,[])
        self.assertFalse(any(c['type']=='press' for c in self.fake.commands))

    async def test_reconnect_resubscribes_without_replaying_press(self):
        await self.setup_entry()
        await self.assign(cooking='scene.test_cooking')
        await self.fake.press(); await asyncio.sleep(.1)
        for ws in self.fake.sockets: await ws.close()
        await asyncio.sleep(1.4)
        self.assertTrue(self.entry.runtime_data.client.connected)
        self.assertEqual(self.calls,['scene.test_cooking'])
        self.assertGreaterEqual(len(self.fake.subscriptions),3)

    async def test_diagnostics_redact_pairing_key(self):
        await self.setup_entry()
        from custom_components.kitchen_dashboard.diagnostics import async_get_config_entry_diagnostics
        data=await async_get_config_entry_diagnostics(self.hass,self.entry)
        self.assertNotIn(TOKEN,json.dumps(data,default=str))

if __name__=='__main__':
    unittest.main(verbosity=2)
