#!/usr/bin/env python3
"""Verify project interactions survive a browser with assets cached from PR30.

Requires Playwright, Chromium and repository history for the baseline commit.
Uses exact project DOM/assets on a loopback fixture, with a deliberate long
asset lifetime and no external origins. This tests a cache-upgrade failure mode;
it does not assert that production currently sends these cache headers.
"""
import argparse,json,re,shutil,subprocess
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline',default='e73114e92e9a50d45ee3d53f9524472924e3d7e9')
parser.add_argument('--candidate-ref',help='Optional committed candidate; default tests the working tree')
parser.add_argument('--browser',default=shutil.which('chromium'))
parser.add_argument('--output',type=Path,default=ROOT/'artifacts/project-asset-upgrade')
args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
state={'phase':0,'language':'en','requests':[]};results=[]
def content(path):
    ref=args.baseline if state['phase']==0 else args.candidate_ref
    if ref:return subprocess.check_output(['git','show',ref+':public/'+path],cwd=ROOT)

    target=(ROOT/'public'/path).resolve()
    if not target.is_relative_to(ROOT/'public'):raise ValueError('Invalid fixture path')
    return target.read_bytes()
def document():
    source=content('es/index.html' if state['language']=='es' else 'index.html').decode()
    work=re.search(r'<section class="section wrap" id="work".*?</section>',source,re.S)[0]
    dialog=re.search(r'<dialog class="project-film".*?</dialog>',source,re.S)[0]
    assets=''.join(tag for tag in re.findall(r'<(?:link|script)\b[^>]*(?:>|></script>)',source) if '/assets/styles.css' in tag or '/assets/projects.css' in tag)
    script=re.search(r'<script src="/assets/projects\.js[^\"]*" defer></script>',source)[0]
    return ('<!doctype html><html lang="'+state['language']+'"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'+assets+script+'</head><body>'+work+dialog+'</body></html>').encode()
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        path=urlsplit(self.path).path;state['requests'].append({'phase':state['phase'],'path':self.path})
        if path=='/':body=document();mime='text/html; charset=utf-8';cache='no-store'
        elif path.startswith(('/assets/','/media/')):
            body=content(path.lstrip('/'));mime='text/javascript' if path.endswith('.js') else 'text/css' if path.endswith('.css') else 'image/png' if path.endswith('.png') else 'image/jpeg';cache='public, max-age=31536000'
        else:self.send_error(404);return
        self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control',cache);self.end_headers();self.wfile.write(body)

server=ThreadingHTTPServer(('127.0.0.1',0),Handler);Thread(target=server.serve_forever,daemon=True).start();base=f'http://127.0.0.1:{server.server_port}/'
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=args.browser,args=['--no-sandbox'])
        for language in ['en','es']:
            state.update(phase=0,language=language,requests=[])
            context=browser.new_context(viewport={'width':390,'height':900},has_touch=True,is_mobile=True,reduced_motion='no-preference')
            page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base);page.wait_for_selector('.project-browser.is-ready');initial=page.locator('.project-tile').count()
            old_ref=page.locator('script[src*="projects.js"]').get_attribute('src');state['phase']=1
            page.goto(base);page.wait_for_timeout(100);new_ref=page.locator('script[src*="projects.js"]').get_attribute('src')
            ready=bool(page.locator('.project-browser.is-ready').count());tiles=page.locator('.project-tile').count()
            row={'candidate':args.candidate_ref or 'working tree','language':language,'initialCards':initial,'upgradedReady':ready,'upgradedCards':tiles,'errors':errors,'oldScriptRef':old_ref,'newScriptRef':new_ref,'newScriptRequested':any(r['phase']==1 and r['path']==new_ref for r in state['requests']),'requests':list(state['requests'])}
            if ready and tiles==6 and not errors:
                page.locator('.project-controls button').last.click();assert page.locator('#gastalo').is_visible()
                page.wait_for_timeout(70);x=page.locator('.project-tile').nth(1).evaluate('(e)=>new DOMMatrixReadOnly(getComputedStyle(e).transform).m41')
                assert 0<x<94;row['incomingCardXAt70ms']=x;page.wait_for_timeout(550)
                page.locator('.project-tile').nth(1).focus();page.keyboard.press('ArrowRight');assert page.locator('#cumpafit').is_visible()
                page.keyboard.press('ArrowLeft');assert page.locator('#gastalo').is_visible();row['keyboardArrowsVerified']=True;page.wait_for_timeout(550)
                stage=page.locator('.project-stage');stage.scroll_into_view_if_needed();box=stage.bounding_box();sx=box['x']+box['width']*.6;sy=box['y']+140;session=context.new_cdp_session(page)
                session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':sx,'y':sy}]})
                for dx in [20,40,70]:
                    session.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':sx-dx,'y':sy}]});page.wait_for_timeout(20)
                drag_x=page.locator('.project-tile').nth(1).evaluate('(e)=>new DOMMatrixReadOnly(getComputedStyle(e).transform).m41');assert drag_x<-60
                session.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});assert page.locator('#cumpafit').is_visible();assert not page.locator('dialog').is_visible()
                row['fingerTrackingXAt70px']=drag_x;row['keyboardButtonsAndTouch']='PASS'
            page.wait_for_timeout(550);page.locator('#work').screenshot(path=str(args.output/f'upgrade-{language}.png'));results.append(row);context.close()
        browser.close()
finally:
    server.shutdown();server.server_close()
(args.output/'upgrade-results.json').write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
assert all(r['initialCards']==6 and r['upgradedReady'] and r['upgradedCards']==6 and not r['errors'] for r in results),'REGRESSION: project interactions disappear after a cached asset upgrade'
assert all(r['newScriptRequested'] and r.get('keyboardButtonsAndTouch')=='PASS' for r in results)
