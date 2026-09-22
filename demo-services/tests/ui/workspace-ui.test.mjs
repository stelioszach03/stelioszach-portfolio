import test, { after, before } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { resolve, sep, extname } from 'node:path';
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright');
// Run from the exported demo-services root. Fixtures never contact a live backend.
const SOURCES=resolve(process.env.DEMO_SOURCES_ROOT || process.cwd());
let BASE, browser, server;
before(async()=>{
 server=createServer(async(req,res)=>{
  try{
   const parts=decodeURIComponent(new URL(req.url,'http://localhost').pathname).split('/').filter(Boolean);
   const demo=parts.shift();
   if(req.method!=='GET'||!['deid','mta-scan'].includes(demo)||parts[0]==='api'){res.writeHead(404,{'Content-Type':'application/json'});res.end('{"detail":"Local UI fixture route not configured"}');return;}
   const root=resolve(SOURCES,demo,'static');const file=resolve(root,parts.join('/')||'index.html');
   if(!file.startsWith(root+sep)){res.writeHead(404);res.end();return;}
   const mime={'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.png':'image/png','.svg':'image/svg+xml'};
   res.writeHead(200,{'Content-Type':mime[extname(file)]||'application/octet-stream'});res.end(await readFile(file));
  }catch{if(!res.headersSent)res.writeHead(404);res.end();}
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));BASE='http://127.0.0.1:'+server.address().port;
 browser=await chromium.launch({executablePath:process.env.CHROME_EXECUTABLE || undefined,headless:true});
});
after(async()=>{await browser?.close();server?.closeAllConnections();await new Promise(resolve=>server?server.close(resolve):resolve());});
const example={examples:[{id:'fixture',title:'Synthetic test document',blurb:'Fictional fixture only.',text:'Avery writes to test@example.invalid.'}],policy_map:{EMAIL:'hash',PERSON:'redact'},limits:{max_text_chars:6000,max_body_bytes:32768}};
async function pageFor(path,{mobile=false,examples=example,deidHandler,stateHandler}={}){
 const context=await browser.newContext({viewport:mobile?{width:375,height:812}:{width:1440,height:1000},isMobile:mobile,hasTouch:mobile,reducedMotion:'reduce'});
 await context.route('**/*',route=>new URL(route.request().url()).origin===BASE?route.continue():route.abort());
 const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.addInitScript(()=>{window.__copied=[];Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async value=>window.__copied.push(value)}});});
 if(examples)await page.route('**/deid/api/examples',route=>route.fulfill({json:examples}));
 if(deidHandler)await page.route('**/deid/api/deidentify',deidHandler);
 if(stateHandler)await page.route('**/mta-scan/api/state?*',stateHandler);
 if(path.startsWith('/mta'))await page.route(/https:\/\/(?:[^/]+\.)?(?:cartocdn\.com|tile\.openstreetmap\.org)\//,route=>route.abort());
 await page.goto(BASE+path);return{page,context,errors};
}
const result=(text,entities=[])=>({original_len:Array.from(text).length,result_text:'[REDACTED:EMAIL]',entities,time_ms:7});
const emailEntity={span:[16,36],label:'EMAIL',detector:'regex',action:'redact'};
const station=(name,route,score,id,lon=-73.95)=>({stop_id:id,stop_name:name,route_id:route,anomaly_score:score,headway_sec:180,predicted_headway_sec:100,residual_sec:80,reasons:['Synthetic fixture deviation'],observed_utc:'2026-09-22T20:00:00Z',lat:40.76,lon});
function state({stale=false,items=[station('Central <img src=x onerror="window.__xss=1">','A',.91,'fixture-a'),station('Harbor','1',.42,'fixture-b',-73.98)]}={}){return{generated_utc:'2026-09-22T20:00:10Z',live:{state:stale?'stale':'live',note:stale?'Synthetic fixture: upstream observations are stale.':null,feeds_ok:stale?6:8,feeds_total:8,last_observed_age_sec:stale?900:10,poll_seconds:30},counters:{stations_reporting:items.length,scored_rows:12,anomalies:1,anomalies_high:1},map:{type:'FeatureCollection',features:items.map(p=>({type:'Feature',geometry:{type:'Point',coordinates:[p.lon,p.lat]},properties:p}))},anomalies:items,model:{maturity:stale?'learning':'warm',maturity_note:'Synthetic fixture: baseline history is limited.'},storage:{rows:12,bytes_human:'2 KB',max_bytes_human:'400 MB',retention_hours:48}};}
const waitReview=page=>page.locator('#review:not([hidden])').waitFor();

test('DeID renders untrusted Unicode source/result/labels as text and exports only explicit metadata',async()=>{
 const text='😀 "<img src=x onerror="window.__xss=1">" test@example.invalid';const points=Array.from(text);const start=points.join('').indexOf('test@')-1; // one surrogate pair before the ASCII email
 const label='EMAIL" <img src=x onerror="window.__xss=1">';let posted;
 const ctx=await pageFor('/deid/',{deidHandler:async route=>{posted=route.request().postDataJSON();await route.fulfill({json:{...result(text,[{span:[start,points.length],label,detector:'regex',action:'redact'}]),result_text:'<img src=x onerror="window.__xss=1">'}});}});const{page,context,errors}=ctx;
 await page.locator('#service[data-state=ready]').waitFor();await page.locator('#text').fill(text);await page.locator('#run').click();await waitReview(page);
 assert.deepEqual(posted,{text,mode:'policy'});assert.equal(await page.locator('#annotated mark').innerText(),'test@example.invalid');assert.equal(await page.locator('#annotated img,#result img,#entities img').count(),0);assert.equal(await page.evaluate(()=>window.__xss),undefined);
 await page.locator('#entities button').click();assert.equal(await page.locator('#inspector .matched').innerText(),'test@example.invalid');assert.equal(await page.locator('#inspector img').count(),0);
 assert.equal(await page.evaluate(()=>window.__copied.length),0);await page.locator('#copySummary').click();const summary=JSON.parse(await page.evaluate(()=>window.__copied[0]));assert.equal(summary.review_required,true);assert.equal(summary.source_characters,points.length);assert.ok(!JSON.stringify(summary).includes('test@example.invalid'));assert.ok(!('result_text'in summary));assert.ok(summary.entities.every(e=>!('surface'in e)&&!('text'in e)));
 assert.equal(await page.evaluate(()=>localStorage.length+sessionStorage.length),0);assert.deepEqual(errors,[]);await page.evaluate(()=>window.dispatchEvent(new Event('pagehide')));assert.equal(await page.locator('#text').inputValue(),'');assert.equal(await page.locator('#review').isVisible(),false);await context.close();
});

test('DeID filters detector/label, invalidates changed policy, and refuses stale in-flight results',async()=>{
 let release;let calls=0;
 const{page,context}=await pageFor('/deid/',{deidHandler:async route=>{calls++;const data=route.request().postDataJSON();if(calls===1){await new Promise(r=>{release=r;});try{await route.fulfill({json:result(data.text,[{span:[0,5],label:'PERSON',detector:'spacy',action:'redact'}])});}catch{}return;}await route.fulfill({json:result(data.text,[{span:[0,5],label:'PERSON',detector:'spacy',action:'redact'},{span:[16,36],label:'EMAIL',detector:'regex',action:'hash'}])});}});
 await page.locator('#service[data-state=ready]').waitFor();await page.locator('#run').click();await page.waitForFunction(()=>document.querySelector('#run').textContent.includes('Analysing'));await page.locator('#text').fill('Different synthetic text');release();await page.waitForTimeout(50);assert.equal(await page.locator('#review').isVisible(),false);
 await page.locator('#text').fill(example.examples[0].text);await page.locator('#run').click();await waitReview(page);await page.locator('#detector').selectOption('regex');assert.equal(await page.locator('#entities tr').count(),1);assert.match(await page.locator('#entities').innerText(),/EMAIL/);await page.locator('#labelFilters button[data-label=PERSON]').click();assert.equal(await page.locator('#entities tr').count(),0);assert.match(await page.locator('#noEntities').innerText(),/No detections match/);
 await page.locator('#mode').selectOption('mask');assert.equal(await page.locator('#review').isVisible(),false);await context.close();
});

test('DeID configuration failure and HTTP rejection never substitute a result; Unicode limits match server characters',async()=>{
 const{page,context}=await pageFor('/deid/',{examples:null});await page.route('**/deid/api/examples',r=>r.fulfill({status:503,json:{detail:'Unavailable'}}));await page.reload();await page.locator('#service[data-state=error]').waitFor();assert.equal(await page.locator('#run').isDisabled(),true);assert.equal(await page.locator('#review').isVisible(),false);
 await page.unroute('**/deid/api/examples');await page.route('**/deid/api/examples',r=>r.fulfill({json:{...example,limits:{max_text_chars:3,max_body_bytes:100}}}));await page.locator('#retry').click();await page.locator('#service[data-state=ready]').waitFor();await page.locator('#text').fill('😀ab');assert.equal(await page.locator('#run').isEnabled(),true);await page.locator('#text').fill('😀abc');assert.equal(await page.locator('#run').isDisabled(),true);await page.locator('#text').fill('abc');await page.route('**/deid/api/deidentify',r=>r.fulfill({status:503,json:{detail:'<img src=x onerror=window.__xss=1>'}}));await page.locator('#run').click();await page.waitForFunction(()=>document.querySelector('#message').textContent.includes('HTTP 503'));assert.equal(await page.locator('#message img').count(),0);assert.equal(await page.locator('#review').isVisible(),false);await context.close();
});

test('MTA filters real-shape observations and keyboard inspection escapes station names',async()=>{
 const{page,context,errors}=await pageFor('/mta-scan/',{stateHandler:r=>r.fulfill({json:state()})});await page.locator('#anoms li[role=button]').first().waitFor();assert.equal(await page.locator('#anoms li[role=button]').count(),2);
 await page.locator('#scoreFloor').selectOption('0.85');assert.equal(await page.locator('#anoms li[role=button]').count(),1);assert.match(await page.locator('#filterSummary').innerText(),/1 of 2/);
 const item=page.locator('#anoms li[role=button]').first();await item.focus();await page.keyboard.press('Enter');await page.locator('#stationDetail:not([hidden])').waitFor();assert.match(await page.locator('#stationDetail h3').innerText(),/Central <img/);assert.equal(await page.locator('#stationDetail img').count(),0);assert.equal(await page.evaluate(()=>window.__xss),undefined);
 await page.locator('#stationSearch').fill('does-not-exist');assert.equal(await page.locator('#anoms li[role=button]').count(),0);assert.match(await page.locator('#anoms').innerText(),/No ranked stations match/);await page.locator('#resetFilters').click();assert.equal(await page.locator('#anoms li[role=button]').count(),2);assert.deepEqual(errors,[]);await context.close();
});

test('MTA distinguishes stale live data, paused refresh, frozen replay and API failure',async()=>{
 let available=true,calls=0;const{page,context,errors}=await pageFor('/mta-scan/',{stateHandler:r=>{calls++;return available?r.fulfill({json:state({stale:true})}):r.fulfill({status:503,json:{detail:'Unavailable'}});}});
 await page.locator('#statetext').filter({hasText:'stale'}).waitFor();assert.equal(await page.locator('#railnote').innerText(),'Synthetic fixture: upstream observations are stale.');assert.equal(await page.locator('#modelNote').innerText(),'Synthetic fixture: baseline history is limited.');await page.locator('#pauseLive').click();assert.match(await page.locator('#mapMode').innerText(),/UPDATES PAUSED/);const before=calls;await page.evaluate(()=>document.dispatchEvent(new Event('visibilitychange')));await page.waitForTimeout(50);assert.equal(calls,before);
 await page.locator('#timeline:enabled').waitFor();await page.locator('#timeline').focus();await page.keyboard.press('ArrowRight');assert.match(await page.locator('#mapMode').innerText(),/FROZEN REPLAY/);assert.equal(await page.locator('#stationSearch').isDisabled(),true);assert.match(await page.locator('#counterScope').innerText(),/background live-source/);const recorded=await page.locator('#replayTime').innerText();assert.match(recorded,/UTC/);
 available=false;await page.locator('#refresh').click();await page.waitForFunction(()=>document.querySelector('#freshness').textContent.includes('unavailable'));assert.match(await page.locator('#mapMode').innerText(),/FROZEN REPLAY/);assert.equal(await page.locator('#replayTime').innerText(),recorded);assert.equal(await page.locator('#replayrail').isVisible(),true);
 await page.locator('#backlive').click();assert.equal(await page.locator('#anoms li[role=button]').count(),0);assert.equal(await page.locator('#k-stations').innerText(),'—');assert.match(await page.locator('#railnote').innerText(),/not answering/);assert.deepEqual(errors,[]);await context.close();
});

test('MTA ignores a superseded window response',async()=>{
 let delayed;let count=0;const{page,context}=await pageFor('/mta-scan/',{stateHandler:async r=>{count++;if(count===1){await new Promise(resolve=>delayed=resolve);try{await r.fulfill({json:state({items:[station('Old snapshot','A',.9,'old')]})});}catch{}return;}await r.fulfill({json:state({items:[station('New snapshot','1',.3,'new')]})});}});
 await page.waitForFunction(()=>document.querySelector('#refresh').disabled);await page.locator('#win').selectOption('15m');await page.locator('#anoms').filter({hasText:'New snapshot'}).waitFor();delayed();await page.waitForTimeout(50);assert.doesNotMatch(await page.locator('#anoms').innerText(),/Old snapshot/);await context.close();
});

test('both workspaces fit mobile width and retain usable controls',async()=>{
 for(const path of ['/deid/','/mta-scan/']){
  const{page,context,errors}=await pageFor(path,{mobile:true,stateHandler:r=>r.fulfill({json:state()}),deidHandler:r=>r.fulfill({json:result(example.examples[0].text,[emailEntity])})});
  if(path==='/deid/'){await page.locator('#service[data-state=ready]').waitFor();await page.locator('#run').click();await waitReview(page);}else await page.locator('#anoms li[role=button]').first().waitFor();
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),path+' page overflows');assert.deepEqual(errors,[]);await context.close();
 }
});
