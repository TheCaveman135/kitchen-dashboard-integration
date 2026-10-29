"""Local dashboard protocol, independent of Home Assistant."""
from __future__ import annotations
import asyncio
from collections.abc import Awaitable, Callable
from typing import Any
import aiohttp
from yarl import URL

class CannotConnect(Exception):
    """Dashboard unavailable or incompatible."""

class DashboardClient:
    def __init__(self, session: aiohttp.ClientSession, host: str, port: int):
        self.session = session
        self.url = URL.build(scheme='ws', host=host.strip('[]'), port=port, path='/')
        self.ws = None
        self.info: dict[str, Any] = {}
        self.state: dict[str, Any] = {}
        self.connected = False
        self._next_id = 1
        self._pending: dict[int, asyncio.Future] = {}

    async def connect(self, slots: list[str] | None = None, appearance: dict | None = None):
        try:
            async with asyncio.timeout(8):
                self.ws = await self.session.ws_connect(self.url, heartbeat=10, max_msg_size=16384)
                hello = await self.ws.receive_json()
                if not isinstance(hello, dict):
                    raise CannotConnect('Invalid handshake')
                if hello.get('type') != 'hello' or hello.get('protocol') != 2 or not isinstance(hello.get('device_id'), str):
                    raise CannotConnect('Incompatible dashboard protocol')
                self.info = hello
                self.state = hello.get('state', {})
                if slots is not None:
                    await self.ws.send_json({'type': 'subscribe', 'id': 0, 'slots': slots, 'appearance': appearance or {}})
                    while True:
                        reply = await self.ws.receive_json()
                        if reply.get('type') == 'state':
                            self.state = reply['state']
                        if reply.get('type') == 'result' and reply.get('id') == 0:
                            if not reply.get('success'):
                                raise CannotConnect('Dashboard rejected configuration: ' + str(reply.get('error', 'unknown error')))
                            break
                self.connected = True
        except CannotConnect:
            await self.close()
            raise
        except (aiohttp.ClientError, TimeoutError, OSError, ValueError, TypeError, KeyError) as error:
            await self.close()
            raise CannotConnect('Unable to connect to dashboard') from error
        return self.info

    async def request(self, kind: str, **data):
        if not self.connected or self.ws is None:
            raise CannotConnect('Dashboard is offline')
        request_id = self._next_id
        self._next_id += 1
        future = asyncio.get_running_loop().create_future()
        self._pending[request_id] = future
        try:
            await self.ws.send_json({'type': kind, 'id': request_id, **data})
            async with asyncio.timeout(8):
                response = await future
            if not response.get('success'):
                raise CannotConnect(response.get('error') or 'Dashboard rejected command')
            return response
        except (aiohttp.ClientError, TimeoutError) as error:
            raise CannotConnect('Dashboard command timed out') from error
        finally:
            self._pending.pop(request_id, None)

    async def listen(self, callback: Callable[[dict], Awaitable[None]]):
        if self.ws is None:
            return
        try:
            async for message in self.ws:
                if message.type != aiohttp.WSMsgType.TEXT:
                    if message.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
                        break
                    continue
                data = message.json()
                if not isinstance(data, dict):
                    continue
                if data.get('type') == 'result':
                    future = self._pending.get(data.get('id'))
                    if future is not None and not future.done():
                        future.set_result(data)
                else:
                    if data.get('type') == 'state' and isinstance(data.get('state'), dict):
                        self.state = data['state']
                    await callback(data)
        finally:
            self.connected = False
            for future in list(self._pending.values()):
                if not future.done():
                    future.set_exception(CannotConnect('Dashboard disconnected'))

    async def acknowledge(self, press_id: str, success: bool):
        if self.connected and self.ws is not None:
            await self.ws.send_json({'type': 'action_result', 'press_id': press_id, 'success': success})

    async def close(self):
        self.connected = False
        if self.ws is not None:
            await self.ws.close()
            self.ws = None
