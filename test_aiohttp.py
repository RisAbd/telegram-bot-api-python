#!/usr/bin/env python3

import asyncio
import aiohttp
from decouple import config
import io


async def main(debug_server_url):
    f = io.BytesIO(b'keklelxd')
    f.name = 'test.txt'
    form = aiohttp.FormData()
    form.add_field('file', f)
    form.add_field('kek', '1')
    async with aiohttp.request('GET', debug_server_url, data=form) as r:
        print(r, r.status)
        print(await r.json())



if __name__ == '__main__':    
    url = config('DEBUG_SERVER_URL', cast=str, default='http://localhost:5055')
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main(url))
