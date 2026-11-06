#!/usr/bin/env python3
"""Optional focused project regression check; requires Playwright and Chromium.

Run against a static preview of public/. Outputs stay in ignored artifacts/.
All external browser requests are blocked; sample fixtures contain no user data.
"""
from pathlib import Path
import argparse,json,shutil
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser(description="Check project detail cleanup, gesture edge cases and compact app actions.")
parser.add_argument('--url',default='http://127.0.0.1:8000')
parser.add_argument('--browser',default=shutil.which('chromium'))
parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]/'artifacts/project-refinements')
args=parser.parse_args();BASE=args.url.rstrip('/');OUT=args.output;OUT.mkdir(parents=True,exist_ok=True);results=[]
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=args.browser,args=['--no-sandbox'])
 def context(**kw):
  c=b.new_context(**kw);c.route('**/*',lambda r:r.continue_() if r.request.url.startswith(BASE+'/') else r.abort());return c
 def fresh(lang='en',**kw):
  c=context(viewport={'width':390,'height':1000},**kw);page=c.new_page();page.goto(BASE+'/'+('es/' if lang=='es' else '')+'#work');page.locator('.project-stage').scroll_into_view_if_needed();return c,page
 def home(page):
  page.locator('.project-tile.is-selected').focus();page.keyboard.press('Home');page.wait_for_timeout(550)
 def matrix(page,index):return page.locator('.project-tile').nth(index).evaluate('(e)=>{const m=new DOMMatrixReadOnly(getComputedStyle(e).transform);return {x:m.m41,y:m.m42,scale:Math.hypot(m.a,m.b)}}')
 def begin(page):
  box=page.locator('.project-stage').bounding_box();x=box['x']+box['width']*.6;y=box['y']+140;page.mouse.move(x,y);page.mouse.down();return x,y
 def drag(page,dx,dy=0):
  x,y=begin(page);page.mouse.move(x+dx,y+dy,steps=8);page.mouse.up();return x,y
 for lang in ['en','es']:
  c,page=fresh(lang)
  assert page.locator('#grok .project-usage').count()==0
  assert page.locator('#grok .project-bottom a').count()==2
  assert page.locator('#grok a[href$="fleet-visualization/"]').count()==1
  assert page.locator('#work article img, #work article video, #work .project-shot').count()==0
  assert not page.locator('#grok').get_by_text('Play fleet film',exact=True).count()
  for project in ['gastalo','cumpafit']:
   page.locator('.project-tile.is-selected').press('ArrowRight')
   a=page.locator('#'+project);assert a.locator('.project-usage').count()==0
   links=a.locator('.project-actions a');assert links.count()==2
   assert a.locator('.project-bottom a').count()==1
   assert not links.nth(1).is_visible()
   a.locator('summary').click();assert links.nth(1).is_visible()
   a.locator('summary').click()
   assert links.nth(0).inner_text()==('Open public demo' if lang=='en' else 'Abrir demo pública')
   assert links.nth(1).inner_text()==('Open personal app' if lang=='en' else 'Abrir app personal')
   assert '?demo=1' in links.nth(0).get_attribute('href')
   assert links.nth(1).get_attribute('href')==f'https://matiashaderspock-ai.github.io/{project}/'
   assert a.locator('a').count()==2
  for project in ['trading-automations','monitor']:assert page.locator('#'+project+' .project-usage').count()==0
  assert page.locator('#trading-bot-scout .project-usage').count()==0
  assert page.locator('#trading-bot-scout .project-bottom a').count()==1
  # Small-card playback remains keyboard accessible after detail media removal.
  home(page)
  imageLink=page.locator('.project-tile').first;imageLink.focus();page.keyboard.press('Enter');page.wait_for_function('document.querySelector("video").currentTime>.1')
  assert page.locator('video').evaluate('(v)=>v.videoWidth===1280&&v.controls&&v.playsInline&&!v.autoplay')
  page.keyboard.press('Escape');page.wait_for_function('!document.querySelector("dialog").open')
  assert imageLink.evaluate('(e)=>document.activeElement===e')
  assert page.locator('video').get_attribute('src') is None
  results.append({'language':lang,'detailCleanupAndDestinations':'PASS','smallCardVideoKeyboardActivationAndFocus':'PASS'});c.close()
 # Direct movement follows the finger and the incoming card progresses before release.
 c,page=fresh();home(page);x,y=begin(page);start=matrix(page,0);incoming=matrix(page,1)
 page.mouse.move(x-70,y,steps=8);middle=matrix(page,0);nextMiddle=matrix(page,1)
 assert abs(middle['x']+70)<1,(start,middle);assert 0<nextMiddle['x']<incoming['x']
 assert page.locator('#grok').is_visible();assert page.locator('.project-stage.is-dragging').count()==1
 page.locator('.project-stage').screenshot(path=str(OUT/'swipe-mid-gesture.png'))
 page.mouse.up();page.wait_for_timeout(90);leaving=matrix(page,0)
 assert leaving['x']<middle['x']-30,(middle,leaving)
 assert page.locator('#gastalo').is_visible();assert not page.locator('dialog').is_visible()
 page.wait_for_timeout(550);assert page.locator('.project-stage.is-dragging').count()==0
 assert page.locator('.project-tile').nth(1).evaluate('(e)=>e===document.activeElement')
 results.append({'fingerTracking':'PASS','start':start,'during':middle,'incomingDuring':nextMiddle,'outgoingAfterRelease':leaving});
 # Short drags and reversed gestures settle back and never play the film.
 home(page);drag(page,-25);page.wait_for_timeout(550);assert page.locator('#grok').is_visible();assert abs(matrix(page,0)['x'])<1;assert not page.locator('dialog').is_visible()
 x,y=begin(page);page.mouse.move(x-90,y,steps=6);page.mouse.move(x-12,y,steps=6);page.mouse.up();page.wait_for_timeout(550)
 assert page.locator('#grok').is_visible();assert not page.locator('dialog').is_visible()
 # Cancel while moving, lost capture, Escape, controls and keyboard interrupt cleanly.
 for kind in ['cancel','lost','escape','control','keyboard']:
  home(page);x,y=begin(page);page.mouse.move(x-80,y,steps=6)
  if kind=='cancel':page.locator('.project-stage').dispatch_event('pointercancel',{'pointerId':1})
  elif kind=='lost':page.locator('.project-stage').evaluate('(e)=>e.releasePointerCapture(1)');page.mouse.move(x-85,y)
  elif kind=='escape':page.keyboard.press('Escape')
  elif kind=='control':page.locator('.project-controls button').last.evaluate('(e)=>e.click()')
  else:page.keyboard.press('ArrowRight')
  page.mouse.up();page.wait_for_timeout(550)
  assert page.locator('.project-stage.is-dragging').count()==0,kind
  assert page.locator('#'+('gastalo' if kind in ['control','keyboard'] else 'grok')).is_visible(),kind
  assert not page.locator('dialog').is_visible(),kind
 # Repeated swipes interrupt the previous outgoing animation and remain responsive.
 home(page)
 for target in ['gastalo','cumpafit','trading-bot-scout']:
  drag(page,-105);assert page.locator('#'+target).is_visible();page.wait_for_timeout(25)
 drag(page,105);assert page.locator('#cumpafit').is_visible();page.wait_for_timeout(550)
 # Reverse past the origin to the previous card; buttons stay responsive during exit.
 x,y=begin(page);page.mouse.move(x-85,y,steps=6);page.mouse.move(x+95,y,steps=8);page.mouse.up();assert page.locator('#gastalo').is_visible()
 page.locator('.project-controls button').last.click();assert page.locator('#cumpafit').is_visible();page.wait_for_timeout(550)
 home(page);drag(page,100);page.wait_for_timeout(550);assert page.locator('#grok').is_visible()
 # Mouse vertical drag never selects or launches film. A fresh tap still plays.
 drag(page,2,90);assert page.locator('#grok').is_visible();assert not page.locator('dialog').is_visible()
 page.locator('.project-tile').first.locator('.project-art').click();page.wait_for_function('document.querySelector("video").currentTime>.1');page.keyboard.press('Escape')
 results.append({'shortReversedCanceledLostCaptureEscInterruptedRepeatedEdgeVerticalAndTap':'PASS'});c.close()
 # Real native touch: horizontal movement and vertical page-scroll coexist.
 c,page=fresh(has_touch=True,is_mobile=True);session=c.new_cdp_session(page)
 box=page.locator('.project-stage').bounding_box();x=box['x']+box['width']*.65;y=box['y']+130
 session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
 for dx in [15,35,65,100]:
  session.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x-dx,'y':y}]});page.wait_for_timeout(20)
 assert matrix(page,0)['x']<-60
 session.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});assert page.locator('#gastalo').is_visible();assert not page.locator('dialog').is_visible()
 page.wait_for_timeout(550);page.locator('.project-stage').scroll_into_view_if_needed();box=page.locator('.project-stage').bounding_box();x=box['x']+box['width']*.6;y=box['y']+240;before=page.evaluate('scrollY')
 session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
 for dy in [20,40,70,110]:
  session.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x+1,'y':y-dy}]});page.wait_for_timeout(20)
 session.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});page.wait_for_timeout(250)
 after=page.evaluate('scrollY');assert abs(after-before)>30,(before,after)
 assert page.locator('#gastalo').is_visible();assert page.locator('.project-stage.is-dragging').count()==0
 # Native touch cancellation returns to the committed project without a film click.
 page.locator('.project-stage').scroll_into_view_if_needed();box=page.locator('.project-stage').bounding_box();x=box['x']+box['width']*.6;y=box['y']+140
 session.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':x,'y':y}]})
 session.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':x-75,'y':y}]});page.wait_for_timeout(30)
 session.send('Input.dispatchTouchEvent',{'type':'touchCancel','touchPoints':[]});page.wait_for_timeout(550)
 assert page.locator('#gastalo').is_visible();assert page.locator('.project-stage.is-dragging').count()==0;assert not page.locator('dialog').is_visible()
 results.append({'nativeTouchSwipeAndVerticalPageScroll':'PASS','scrollBefore':before,'scrollAfter':after});c.close()
 # Reduced motion has no animated exit or settling; user-driven drag stays direct.
 c,page=fresh(reduced_motion='reduce');home(page);x,y=begin(page);page.mouse.move(x-85,y,steps=6);assert matrix(page,0)['x']<-80;page.mouse.up()
 assert page.locator('#gastalo').is_visible();assert page.locator('.project-tile').first.evaluate('(e)=>getComputedStyle(e).transitionDuration')=='0s'
 assert page.locator('.project-stage').evaluate('(e)=>e.getAnimations({subtree:true}).filter(a=>a.playState==="running").length')==0
 assert not page.locator('dialog').is_visible();results.append({'reducedMotion':'PASS'});c.close()
 # Detail panels stay text-only, with demo action and the personal action below expanded instructions.
 for lang in ['en','es']:
  for theme in ['dark','light']:
   for width in [320,360,375,390,430,1440]:
    c=context(viewport={'width':width,'height':1000});page=c.new_page();page.add_init_script(f'localStorage.setItem("mh-theme","{theme}")');page.goto(BASE+'/'+('es/' if lang=='es' else '')+'#work')
    assert page.locator('#work article img, #work article video, #work .project-shot').count()==0
    assert page.locator('.project-art img').count()==4
    page.locator('.project-tile').first.focus()
    for project in ['gastalo','cumpafit']:
     page.locator('.project-tile.is-selected').press('ArrowRight');page.locator('#'+project+' summary').click();links=page.locator('#'+project+' .project-actions a');boxes=links.evaluate_all('(es)=>es.map(e=>e.getBoundingClientRect().toJSON())')
     assert boxes[1]['y']>boxes[0]['y']+boxes[0]['height'],boxes
     assert all(box['width']>=44 and box['height']>=44 for box in boxes),boxes
     assert links.evaluate_all('(es)=>es.every(e=>e.scrollWidth<=e.clientWidth+1)'),boxes
     assert links.evaluate_all('(es)=>es.every(e=>{const r=document.createRange();r.selectNodeContents(e);return r.getClientRects().length===1})'),boxes
     assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
     if width in [320,390,1440] and theme=='dark':
      page.wait_for_timeout(550);page.locator('.project-browser').screenshot(path=str(OUT/f'after-{lang}-{width}-{project}.png'))
    if width==320:
     page.evaluate('document.documentElement.style.fontSize="200%"')
     links=page.locator('#cumpafit .project-actions a');boxes=links.evaluate_all('(es)=>es.map(e=>e.getBoundingClientRect().toJSON())')
     assert boxes[1]['y']>boxes[0]['y'] and all(box['height']>=44 for box in boxes)
     assert links.evaluate_all('(es)=>es.every(e=>e.scrollWidth<=e.clientWidth+1)')
    c.close()
 results.append({'textOnlyPanelsAndDisclosureActions':'PASS: EN/ES × dark/light × 320/360/375/390/430/1440; 44px targets and 200% text enlargement'})
 # Actual keyboard and touch activation follow the distinct demo/personal URLs.
 # Navigation is fulfilled locally so this check never opens a personal app.
 navigations=[]
 for lang in ['en','es']:
  c=context(viewport={'width':320,'height':900},has_touch=True,is_mobile=True);page=c.new_page()
  page.route('https://matiashaderspock-ai.github.io/**',lambda r:r.fulfill(status=200,content_type='text/html',body='<title>Navigation test</title><p>Local navigation fixture</p>'))
  for project in ['gastalo','cumpafit']:
   for index in [0,1]:
    for mode in ['keyboard','touch']:
     page.goto(BASE+'/'+('es/' if lang=='es' else '')+'#'+project);button=page.locator('#'+project+' .project-actions a').nth(index);expected=button.get_attribute('href')
     if index==1:page.locator('#'+project+' summary').click()
     if mode=='keyboard':
      page.keyboard.press('Tab');button.focus();assert button.evaluate('(e)=>parseFloat(getComputedStyle(e).outlineWidth)>=2');page.keyboard.press('Enter')
     else:button.tap()
     page.wait_for_url(expected);assert page.url==expected
     navigations.append({'language':lang,'project':project,'action':index,'input':mode,'destination':expected})
  c.close()
 results.append({'buttonKeyboardTouchNavigation':'PASS: 16 activations; external navigation intercepted','destinations':navigations})
 b.close()
(OUT/'focused-results.json').write_text(json.dumps(results,indent=2));print('PASS',len(results),'focused groups',json.dumps(results,indent=2))
