#!/usr/bin/env python3
import asyncio, json
from pathlib import Path
from playwright.async_api import async_playwright

COOKIE_FILE = Path('/root/workspace/tiktok-heritage-crawler/cookies.json')

def load_pw_cookies():
    data=json.loads(COOKIE_FILE.read_text(encoding='utf-8'))
    if isinstance(data,dict) and 'cookies' in data: data=data['cookies']
    out=[]
    for c in data:
        if not isinstance(c,dict) or not c.get('name') or c.get('value') is None: continue
        ck={
            'name': c['name'], 'value': c['value'],
            'domain': c.get('domain') or '.tiktok.com',
            'path': c.get('path') or '/',
            'secure': bool(c.get('secure', True)),
            'httpOnly': bool(c.get('httpOnly', False)),
        }
        if c.get('expirationDate'): ck['expires']=int(c['expirationDate'])
        ss=c.get('sameSite') or c.get('same_site')
        if ss:
            ss=str(ss).lower().replace('no_restriction','none')
            ck['sameSite']={'none':'None','lax':'Lax','strict':'Strict'}.get(ss,'None')
        out.append(ck)
    return out

async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True)
        context=await browser.new_context(locale='en-US', user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        await context.add_cookies(load_pw_cookies())
        page=await context.new_page()
        hits=[]
        async def on_response(resp):
            url=resp.url
            if '/api/' in url or 'search' in url.lower():
                try:
                    ct=resp.headers.get('content-type','')
                    text=''
                    if 'json' in ct or '/api/' in url:
                        text=(await resp.text())[:500]
                    hits.append({'status':resp.status,'ct':ct,'url':url,'body':text})
                    print('RESP', resp.status, ct[:40], url[:220])
                    if text: print('BODY', text[:180].replace('\n',' '))
                except Exception as e:
                    print('RESPERR', url[:120], e)
        page.on('response', on_response)
        print('goto search page')
        await page.goto('https://www.tiktok.com/search/video?q=springfestival', wait_until='domcontentloaded', timeout=60000)
        print('url', page.url)
        await page.wait_for_timeout(15000)
        await browser.close()
        Path('/root/workspace/tiktok-heritage-crawler/data/search_network_hits.json').write_text(json.dumps(hits,ensure_ascii=False,indent=2),encoding='utf-8')
        print('saved hits', len(hits))
asyncio.run(main())
