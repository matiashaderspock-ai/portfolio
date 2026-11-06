#!/usr/bin/env python3
"""Optional browser regression check. Requires Playwright and Chromium.

Start a static preview of public/ first. External requests are blocked so the
suite exercises local assets and system-font fallbacks without third-party data.
Screenshots and results go to ignored artifacts/project-review by default.
"""
import argparse,hashlib,json,shutil
from pathlib import Path
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser(description="Verify project cards, images, native video and accessible interactions against a local preview.")
parser.add_argument('--url',default='http://127.0.0.1:8000',help='Local static preview origin')
parser.add_argument('--browser',default=shutil.which('chromium'),help='Chromium executable; omit to use the Playwright browser')
parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'artifacts/project-review')
args=parser.parse_args();BASE=args.url.rstrip('/');OUT=args.output;OUT.mkdir(parents=True,exist_ok=True);results=[]
order=['grok','gastalo','cumpafit','trading-bot-scout','trading-automations','monitor']
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=args.browser,headless=True,args=['--no-sandbox'])
 def context(**kw):
  c=b.new_context(**kw); c.route('**/*',lambda r:r.continue_() if r.request.url.startswith(BASE+'/') else r.abort()); return c
 for lang in ['en','es']:
  for theme in ['dark','light']:
   for width in [320,390,1440]:
    c=context(viewport={'width':width,'height':1000}); page=c.new_page(); errors=[]; page.on('pageerror',lambda e:errors.append(str(e)))
    page.add_init_script(f'localStorage.setItem("mh-theme","{theme}")')
    page.goto(BASE+'/'+('es/' if lang=='es' else '')+'#work'); page.wait_for_selector('.project-browser.is-ready')
    assert page.locator('#work article').evaluate_all('(es)=>es.map(e=>e.id)')==order
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(lang,theme,width,'overflow')
    assert page.locator('#grok h3').inner_text()==('Mi fleet de agentes de IA' if lang=='es' else 'My AI Agent Fleet')
    assert page.locator('#grok .tags li').last.inner_text()=='OpenAI Dots'
    assert page.locator('.project-crop').count()==2
    assert page.locator('.project-crop img').evaluate_all('(es)=>es.every(e=>Math.abs(e.clientWidth/e.clientHeight-e.naturalWidth/e.naturalHeight)<.01)')
    assert page.locator('.project-art img').evaluate_all('(es)=>es.every(e=>getComputedStyle(e).backgroundColor==="rgb(17, 31, 43)")')
    assert page.locator('.project-number, .tile-number').count()==0
    assert page.locator('.project-controls [role=status]').inner_text()=='01 / 06'
    assert page.locator('.project-art.image-art').count()==4
    assert page.locator('.project-art img').evaluate_all('(es)=>es.every(e=>e.complete&&e.naturalWidth>0&&getComputedStyle(e).objectFit==="contain")')
    assert page.locator('video').get_attribute('preload')=='none'
    assert page.locator('video').get_attribute('src') is None
    tiles=page.locator('.project-tile'); tiles.first.focus()
    for i in range(6):
     assert page.locator('#'+order[i]).is_visible()
     assert page.locator('.project-controls [role=status]').inner_text()==f'{i+1:02d} / 06'
     if i<5: page.keyboard.press('ArrowRight')
    page.keyboard.press('Home'); assert page.locator('#grok').is_visible()
    page.keyboard.press('End'); assert page.locator('#monitor').is_visible()
    page.keyboard.press('Home')
    # Actual mouse wheel and pointer swipe selection.
    stage=page.locator('.project-stage'); stage.hover(); page.mouse.wheel(0,100); page.wait_for_timeout(250); assert page.locator('#gastalo').is_visible()
    box=stage.bounding_box(); sx=box['x']+box['width']*.6; sy=box['y']+150; page.mouse.move(sx,sy); page.mouse.down(); page.mouse.move(sx-110,sy,steps=6); page.mouse.up(); assert page.locator('#cumpafit').is_visible(); assert not page.locator('dialog').is_visible()
    page.keyboard.press('Home')
    for i,id in enumerate(order[:3]):
     if i: page.keyboard.press('ArrowRight')
     page.wait_for_timeout(550)
     if width in [390,1440] and theme=='dark':
      page.locator('.project-browser').screenshot(path=str(OUT/f'draft-{lang}-{width}-{id}.png'))
    assert not errors, errors
    results.append({'language':lang,'theme':theme,'width':width,'result':'PASS','checks':['order','selection','keyboard','wheel','swipe','images','no overflow','no eager video','no JS errors']}); c.close()
 # Real video: explicit activation, decoding, actual time advancement, dismissal and focus.
 for lang in ['en','es']:
  c=context(viewport={'width':1440,'height':1000}); page=c.new_page(); page.goto(BASE+'/'+('es/' if lang=='es' else '')+'#work')
  tile=page.locator('.project-tile').first
  for method in ['Escape','close','backdrop']:
   tile.locator('.project-art').click(); page.wait_for_function('document.querySelector("video").currentTime>0.1')
   state=page.locator('video').evaluate('(v)=>({duration:v.duration,width:v.videoWidth,height:v.videoHeight,paused:v.paused,controls:v.controls,inline:v.playsInline,src:v.currentSrc})')
   assert abs(state['duration']-10.041667)<0.02 and state['width']==1280 and state['height']==720 and state['src'].endswith('/media/bot-fleet-night.mp4') and not state['paused'] and state['controls'] and state['inline'],state
   if method=='Escape': page.keyboard.press('Escape')
   elif method=='close': page.locator('dialog button').click()
   else: page.mouse.click(2,2)
   page.wait_for_function('!document.querySelector("dialog").open && !document.querySelector("video").getAttribute("src")')
   assert page.locator('video').evaluate('(v)=>v.paused')
   assert tile.evaluate('(e)=>document.activeElement===e')
  # An unselected film card selects on first click; subsequent explicit artwork click plays.
  page.locator('.project-tile').nth(1).dispatch_event('click',{'detail':1})
  tile.locator('.project-art').dispatch_event('click',{'detail':1}); assert page.locator('#grok').is_visible(); assert not page.locator('dialog').is_visible()
  # Visualization remains separate navigation, in the existing new-tab behavior.
  link=page.locator('#grok .project-bottom a').first
  with page.expect_popup() as popup: link.click()
  popup.value.wait_for_load_state(); assert popup.value.url.endswith('/es/fleet-visualization/' if lang=='es' else '/fleet-visualization/')
  assert popup.value.locator('video source').get_attribute('src')=='/media/bot-fleet-night.mp4'
  assert hashlib.sha256(page.request.get(state['src']).body()).hexdigest()=='0f7d29beaba31245edf61bb3df694feea203ba7226b47265ae9e21b0209bbb6e'
  results.append({'language':lang,'result':'PASS','actualVideo':state,'dismissals':['Escape','button','backdrop'],'focusRestored':True,'separateNavigation':True}); c.close()
 c=context(viewport={'width':390,'height':1000},has_touch=True,is_mobile=True); page=c.new_page(); page.goto(BASE+'/#work'); stage=page.locator('.project-stage'); stage.scroll_into_view_if_needed(); box=stage.bounding_box(); x=box['x']+box['width']*.7; y=box['y']+150
 session=c.new_cdp_session(page)
 session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
 for dx in [20,40,60,90,120]: session.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x-dx,'y':y}]})
 session.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
 assert page.locator('#gastalo').is_visible(); assert not page.locator('dialog').is_visible()
 # Return by keyboard, then activate the selected film using Enter.
 page.locator('.project-tile').nth(1).focus(); page.keyboard.press('Home'); page.keyboard.press('Enter'); page.wait_for_function('document.querySelector("video").currentTime>0.1')
 page.keyboard.press('Tab'); assert page.locator('dialog').evaluate('(d)=>d.contains(document.activeElement)')
 page.keyboard.press('Escape'); assert page.locator('.project-tile').first.evaluate('(e)=>document.activeElement===e')
 results.append({'realTouchSwipe':'PASS','keyboardFilmActivation':'PASS','modalFocusContainment':'PASS'}); c.close()
 for lang in ['en','es']:
  c=context(java_script_enabled=False,viewport={'width':320,'height':900}); page=c.new_page(); page.goto(BASE+'/'+('es/' if lang=='es' else '')+'#work')
  assert page.locator('#work article:visible').count()==6
  assert page.locator('.project-shot').count()==0
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  results.append({'language':lang,'noJavaScript':'PASS'}); c.close()
 c=context(reduced_motion='reduce'); page=c.new_page(); page.goto(BASE+'/#work'); assert page.locator('.project-tile').first.evaluate('(e)=>getComputedStyle(e).transitionDuration')=='0s'; results.append({'reducedMotion':'PASS'}); c.close()
 c=context(); c.route('**/media/*',lambda r:r.abort()); page=c.new_page(); page.goto(BASE+'/#work'); page.wait_for_timeout(200)
 assert page.locator('.project-art.image-art').count()==0; assert page.locator('.project-art svg:visible').count()==6
 results.append({'brokenImages':'PASS: original SVG fallback and card names remain'}); c.close(); b.close()
(OUT/'browser-results.json').write_text(json.dumps(results,indent=2)); print('PASS',len(results),'browser scenarios')
