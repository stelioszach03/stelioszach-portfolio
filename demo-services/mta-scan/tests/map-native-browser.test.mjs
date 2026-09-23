// Real Mapbox GL JS/WebGL with intercepted local style/data fixtures. No provider billing.
import test,{before,after} from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {resolve,extname,sep} from 'node:path';
import {fileURLToPath} from 'node:url';
const {chromium}=await import(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const ROOT=resolve(fileURLToPath(new URL('../static/',import.meta.url)));
const ORIGIN='https://stelioszach.com';
let browser;
before(async()=>{browser=await chromium.launch({executablePath:process.env.CHROME_EXECUTABLE||undefined,args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});});
after(async()=>{await browser?.close();});
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jOe8AAAAASUVORK5CYII=','base64');
const observation={stop_id:'synthetic-a',stop_name:'Synthetic station',route_id:'A',anomaly_score:.9,headway_sec:180,predicted_headway_sec:90,observed_utc:'2026-09-22T20:00:00Z',reasons:['Synthetic fixture only']};
const snapshot={generated_utc:'2026-09-22T20:00:10Z',live:{state:'live',feeds_ok:8,feeds_total:8,last_observed_age_sec:10,poll_seconds:30},counters:{stations_reporting:1,scored_rows:12,anomalies:1,anomalies_high:1},map:{type:'FeatureCollection',features:[{type:'Feature',geometry:{type:'Point',coordinates:[-73.95,40.76]},properties:observation}]},anomalies:[observation],model:{maturity:'warm'},storage:{rows:12,bytes_human:'2 KB',max_bytes_human:'400 MB',retention_hours:48}};
async function open({width=1440,token='pk.eyJ1IjoiZml4dHVyZSIsImEiOiJ0ZXN0In0.fixture',styleFails=false}={}){
 const context=await browser.newContext({viewport:{width,height:900},isMobile:width<600,hasTouch:width<600,reducedMotion:'reduce',acceptDownloads:true,serviceWorkers:'block'});
 const calls=[];await context.route('**/*',async route=>{
  const u=new URL(route.request().url());
  if(u.origin==='https://api.mapbox.com'){
   calls.push(u.pathname);
   if(u.pathname.includes('/tiles/'))return route.fulfill({body:png,contentType:'image/png'});
   if(u.pathname.startsWith('/styles/v1/'))return styleFails?route.fulfill({status:403,json:{message:'Fixture provider failure'}}):route.fulfill({json:{version:8,name:'Local renderer fixture',sources:{},layers:[{id:'background',type:'background',paint:{'background-color':'#081528'}}]}});
   return route.fulfill({status:200,json:{}});
  }
  if(u.origin==='https://events.mapbox.com')return route.fulfill({status:200,json:{}});
  if(u.origin==='https://tile.openstreetmap.org')return route.fulfill({body:png,contentType:'image/png'});
  if(u.origin!==ORIGIN)return route.abort();
  const rel=u.pathname.replace('/demos/mta-scan/','');
  if(rel==='api/state')return route.fulfill({json:snapshot});
  if(rel==='map-config.json')return route.fulfill({json:{publicToken:token}});
  if(!u.pathname.startsWith('/demos/mta-scan/'))return route.fulfill({status:204,body:''});
  const path=resolve(ROOT,rel||'index.html');if(!path.startsWith(ROOT+sep))return route.fulfill({status:404,body:''});
  try{return route.fulfill({body:await readFile(path),contentType:({'.html':'text/html','.js':'text/javascript','.css':'text/css','.json':'application/json','.svg':'image/svg+xml'})[extname(path)]||'application/octet-stream'});}catch{return route.fulfill({status:404,body:''});}
 });
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(ORIGIN+'/demos/mta-scan/');await page.locator('#exportSnapshot:enabled').waitFor();return {page,context,errors,calls};
}
test('actual GL engine creates native GeoJSON layers and restores observations across vector styles',async()=>{
 const {page,context,errors}=await open();try{await page.waitForFunction(()=>window.__mtaScanMap?.map.native&&window.__mtaScanMap.map.loaded);assert.equal(await page.locator('.mapboxgl-canvas').count(),1);assert.equal(await page.locator('.leaflet-container').count(),0);await page.waitForFunction(()=>window.__mtaScanMap.map.native.getSource('mta-scores')?._data.features.length===1);assert.equal(await page.evaluate(()=>window.__mtaScanMap.map.native.getLayer('mta-scores-circles').type),'circle');await page.waitForFunction(()=>window.__mtaScanMap.map.native.queryRenderedFeatures({layers:['mta-scores-circles']}).length>0);await page.locator('#mapStyle').selectOption('streets');await page.waitForFunction(()=>window.__mtaScanMap.map.loaded&&window.__mtaScanMap.map.native.getSource('mta-scores')?._data.features.length===1);assert.match(await page.locator('#mapProviderStatus').innerText(),/Mapbox GL.*Streets vector/);assert.deepEqual(errors,[]);}finally{await context.close();}
});
test('native filtering, inspector, export and replay preserve the existing data semantics',async()=>{
 const {page,context,errors}=await open();try{await page.waitForFunction(()=>window.__mtaScanMap?.map.native&&window.__mtaScanMap.map.loaded);await page.locator('#anoms li[role=button]').first().click();assert.equal(await page.locator('#stationDetail').isVisible(),true);await page.locator('#stationSearch').fill('missing');await page.waitForFunction(()=>window.__mtaScanMap.map.native.getSource('mta-scores')._data.features[0].properties.fillOpacity===.03);assert.equal(await page.locator('#anoms li[role=button]').count(),0);const waiting=page.waitForEvent('download');await page.locator('#exportSnapshot').click();const download=await waiting;const data=JSON.parse(await readFile(await download.path(),'utf8'));assert.equal(data.exported_map_observations,0);assert.equal(data.filters.search,'missing');await page.locator('#resetFilters').click();await page.locator('#timeline:enabled').waitFor();await page.locator('#timeline').focus();await page.keyboard.press('ArrowRight');await page.waitForFunction(()=>window.__mtaScanMap.map.native.getSource('mta-scores')._data.features.length===6);assert.equal(await page.locator('#exportSnapshot').isDisabled(),true);await page.locator('#backlive').click();await page.waitForFunction(()=>window.__mtaScanMap.map.native.getSource('mta-scores')._data.features.length===1);assert.deepEqual(errors,[]);}finally{await context.close();}
});
test('provider authorization failure exposes real fallback without losing observations',async()=>{
 const {page,context,errors}=await open({styleFails:true});try{await page.waitForFunction(()=>!!window.__mtaScanMap?.map.leaflet);assert.match(await page.locator('#mapProviderStatus').innerText(),/Leaflet fallback/);assert.equal(await page.locator('.mapboxgl-canvas').count(),0);assert.equal(await page.locator('.leaflet-container').count(),1);assert.equal(await page.locator('#anoms li[role=button]').count(),1);assert.deepEqual(errors,[]);}finally{await context.close();}
});
test('secret configuration never reaches Mapbox and still supports the live table',async()=>{
 const {page,context,calls,errors}=await open({token:'sk.synthetic.secret'});try{assert.equal(calls.length,0);assert.match(await page.locator('#mapProviderStatus').innerText(),/OpenStreetMap.*Leaflet fallback/);assert.equal(await page.locator('#anoms li[role=button]').count(),1);assert.deepEqual(errors,[]);}finally{await context.close();}
});
test('native phone map retains44px controls and the explicit pan lock',async()=>{
 for(const width of [320,375,390]){const {page,context,errors}=await open({width});try{await page.waitForFunction(()=>window.__mtaScanMap?.map.native&&window.__mtaScanMap.map.loaded);assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));assert.equal(await page.evaluate(()=>window.__mtaScanMap.map.native.dragPan.isEnabled()),false);await page.locator('#maphint').click();assert.equal(await page.evaluate(()=>window.__mtaScanMap.map.native.dragPan.isEnabled()),true);await page.locator('#lockMap').click();assert.equal(await page.evaluate(()=>window.__mtaScanMap.map.native.dragPan.isEnabled()),false);await page.locator('#windowControls > summary').click();for(const id of ['refresh','pauseLive','mapStyle','exportSnapshot','fitFiltered'])assert.ok((await page.locator('#'+id).boundingBox()).height>=44,id);assert.deepEqual(errors,[]);}finally{await context.close();}}
});
test('native snapshot export retains its successful window while a changed window is still loading',async()=>{
 const {page,context}=await open();let release;
 try{await page.waitForFunction(()=>window.__mtaScanMap?.map.native&&window.__mtaScanMap.map.loaded);await page.route('**/api/state?*',async route=>{await new Promise(r=>release=r);try{await route.fulfill({json:snapshot});}catch{}});await page.locator('#win').selectOption('6h');await page.waitForFunction(()=>document.querySelector('#refresh').disabled);const waiting=page.waitForEvent('download');await page.locator('#exportSnapshot').click();const download=await waiting;const data=JSON.parse(await readFile(await download.path(),'utf8'));assert.equal(data.filters.window,'1h');}finally{release?.();await context.close();}
});
