from __future__ import annotations

import socket

from aiohttp import ClientSession, TCPConnector
from aiogram.client.session.aiohttp import AiohttpSession


class IPv4OnlySession(AiohttpSession):
    async def create_session(self) -> ClientSession:
        if self._session is None or self._session.closed:
            connector = TCPConnector(family=socket.AF_INET, limit=100, ttl_dns_cache=300)
            self._session = ClientSession(connector=connector)
        return self._session