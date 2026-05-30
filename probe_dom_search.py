#!/usr/bin/env python3
import asyncio, json, re
from pathlib import Path
from playwright.async_api import async_playwright

COOKIE_FILE=Path('/root/workspace/tiktok-heritage-crawler/cookies.json')

def load_cookies():
    data=json.loads(COOKIE_FILE.read_text(encoding='utf-8'))
    if isinstance(data,dict) and 'cookies' in data: data=data['cookies']
    out=[]
    for c in data:
        if not isinstance(c,dict) or not c.get('name') or c.get('value') is None: continue
        ck={'name':c['name'],'value':c['value'],'domain':c.get('domain') or '.tiktok.com','path':c.get('path') or '/', 'secure':bool(c.get('secure',True)), 'httpOnly':bool(c.get('httpOnly',False))}
        if c.get('expirationDate'): ck['expires']=int(c['expirationDate'])
        ss=c.get('sameSite') or c.get('same_site')
        if ss:
            ss=str(ss).lower().replace('no_restriction','none')
            ck['sameSite']={'none':'None','lax':'Lax','strict':'Strict'}.get(ss,'None')
        out.append(ck)
    return out

async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True, proxy={'server':'socks5://127.0.0.1:10809'})
        ctx=await browser.new_context(locale='en-US', viewport={'width':1366,'height':900})
        await ctx.add_cookies(load_cookies())
        page=await ctx.new_page()
        await page.goto('https://www.tiktok.com/search/video?q=springfestival', wait_until='domcontentloaded', timeout=60000)
        print('url', page.url)
        await page.wait_for_timeout(15000)
        title=await page.title()
        print('title', title)
        body=(await page.locator('body').inner_text(timeout=5000))[:2000]
        print('body', body.replace('\n',' | ')[:1000])
        links=await page.eval_on_selector_all('a[href*="/video/"]', '(els)=>els.map(a=>({href:a.href,text:a.innerText,aria:a.getAttribute("aria-label")})).slice(0,50)')
        print('video_links', len(links))
        print(json.dumps(links[:5],ensure_ascii=False,indent=2))
        html=await page.content()
        Path('data/search_page_spring.html').write_text(html,encoding='utf-8')
        ids=sorted(set(re.findall(r'/video/(\d+)', html)))
        print('ids_in_html', len(ids), ids[:10])
        await browser.close()
asyncio.run(main())
