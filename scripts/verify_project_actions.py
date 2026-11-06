#!/usr/bin/env python3
"""Optional browser checks for project action rows and native installation help.

Requires Playwright/Chromium. Only the loopback preview is fetched; external
navigation targets are inspected or fulfilled with a synthetic local fixture.
"""
import argparse,json,shutil
from pathlib import Path
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--url',default='http://127.0.0.1:8000')
parser.add_argument('--output',type=Path,default=Path('artifacts/project-actions'))
args=parser.parse_args();base=args.url.rstrip('/');args.output.mkdir(parents=True,exist_ok=True);results=[]
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox'])
 for lang in ['en','es']:
  for theme in ['dark','light']:
   for width in [320,390,1440]:
    context=browser.new_context(viewport={'width':width,'height':1000},has_touch=True,is_mobile=width<500)
    context.route('**/*',lambda r:r.continue_() if r.request.url.startswith(base+'/') else r.abort())
    page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto(base+('/es/' if lang=='es' else '/')+'#work');page.evaluate('(t)=>document.documentElement.dataset.theme=t',theme)
    for project in ['grok','gastalo','cumpafit','trading-bot-scout']:
     page.locator('.project-tile').first.focus();page.keyboard.press('Home')
     for _ in range(['grok','gastalo','cumpafit','trading-bot-scout'].index(project)):page.keyboard.press('ArrowRight')
     panel=page.locator('#'+project);links=panel.locator('.project-bottom .button')
     expected=2 if project=='grok' else 1;assert links.count()==expected
     if project=='grok':
      assert links.all_inner_texts()==(['See Visualization','Go to Mission Control'] if lang=='en' else ['Ver visualización','Ir al centro de control'])
      assert links.nth(0).get_attribute('href')==('/fleet-visualization/' if lang=='en' else '/es/fleet-visualization/')
      assert links.nth(1).get_attribute('href')=='#mission-control'
     if project=='trading-bot-scout':
      assert links.inner_text()==('Explore Site' if lang=='en' else 'Explorá el sitio')
      assert links.get_attribute('href')=='https://tradingbotscout.com'
     for scale in ([100,200] if width==320 else [100]):
      page.evaluate('(s)=>document.documentElement.style.fontSize=s+"%"',scale)
      boxes=links.evaluate_all('(es)=>es.map(e=>{const r=e.getBoundingClientRect();const t=document.createRange();t.selectNodeContents(e);return {x:r.x,y:r.y,w:r.width,h:r.height,overflow:e.scrollWidth>e.clientWidth+1,visible:[...t.getClientRects()].every(t=>t.left>=r.left-1&&t.right<=r.right+1&&t.top>=r.top-1&&t.bottom<=r.bottom+1)}})')
      assert all(b['w']>=44 and b['h']>=44 and b['visible'] and not b['overflow'] for b in boxes),boxes
      if expected==2:assert abs(boxes[0]['y']-boxes[1]['y'])<1,boxes
      assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),(lang,width,scale)
     page.evaluate('document.documentElement.style.fontSize="100%"')
     if project in ['gastalo','cumpafit']:
      detail=panel.locator('details');summary=detail.locator('summary');assert not detail.evaluate('(e)=>e.open')
      assert summary.bounding_box()['height']>=44
      summary.focus();page.keyboard.press('Enter');assert detail.evaluate('(e)=>e.open')
      assert panel.get_by_text('iPhone · Safari:',exact=True).is_visible();assert panel.get_by_text('Android · Chrome:',exact=True).is_visible()
      assert detail.locator('li').count()==2;assert 'JSON' in detail.inner_text()
      assert detail.locator('a').count()==1
      assert detail.locator('a').get_attribute('href')==f'https://matiashaderspock-ai.github.io/{project}/'
      assert detail.locator('a').bounding_box()['y']>detail.locator('p').last.bounding_box()['y']
      assert detail.locator('a').bounding_box()['height']>=44
      for scale in ([100,200] if width==320 else [100]):
       page.evaluate('(s)=>document.documentElement.style.fontSize=s+"%"',scale)
       assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
       assert detail.evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
      page.evaluate('document.documentElement.style.fontSize="100%"')
      if width in [320,1440] and theme=='dark':
       panel.screenshot(path=str(args.output/f'{lang}-{width}-{project}-expanded.png'))
      summary.focus();page.keyboard.press('Space');assert not detail.evaluate('(e)=>e.open')
      summary.tap();assert detail.evaluate('(e)=>e.open');summary.tap();assert not detail.evaluate('(e)=>e.open')
    assert not errors,errors
    results.append({'language':lang,'theme':theme,'width':width,'actionRowsFullLabels44px':'PASS','disclosureKeyboardTouchAndOverflow':'PASS','text200Percent':width==320})
    context.close()
  # Native help works with no JavaScript and needs no controller state.
  context=browser.new_context(java_script_enabled=False,viewport={'width':320,'height':900})
  context.route('**/*',lambda r:r.continue_() if r.request.url.startswith(base+'/') else r.abort())
  page=context.new_page();page.goto(base+('/es/' if lang=='es' else '/'))
  for project in ['gastalo','cumpafit']:
   detail=page.locator('#'+project+' details');detail.locator('summary').click();assert detail.get_attribute('open') is not None
  context.close()
 browser.close()
(args.output/'results.json').write_text(json.dumps(results,indent=2));print('PASS',len(results),'responsive scenarios + EN/ES no-JS disclosures')
