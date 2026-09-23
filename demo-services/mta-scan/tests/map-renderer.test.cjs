const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
function loadUMD(name){const filename=path.join(__dirname,'../static',name),module={exports:{}};vm.runInThisContext('(function(module,exports){'+fs.readFileSync(filename,'utf8')+'\n})',{filename})(module,module.exports);return module.exports;}
const Renderer=loadUMD('map-renderer.js');
const Provider=loadUMD('map-provider.js');
function environment(supported=true){
 const state={native:[],leaflet:[],status:[],queue:[],popups:[]};
 const element={replaceChildren(){this.cleared=true;}};
 class Evented{constructor(){this.handlers={};}on(name,fn){(this.handlers[name]??=[]).push(fn);return this;}fire(name,data={}){for(const fn of this.handlers[name]||[])fn(data);} }
 class Native extends Evented{
  constructor(options){super();this.options=options;this.center={lng:options.center[0],lat:options.center[1]};this.zoom=options.zoom;this.sources={};this.layers={};this.canvas={style:{}};this.controls=[];state.native.push(this);for(const k of ['scrollZoom','dragPan','touchZoomRotate']){this[k]={active:false,enable(){this.active=true;},disable(){this.active=false;},disableRotation(){}};}}
  addControl(c){this.controls.push(c);return this;}getCanvas(){return this.canvas;}getCenter(){return this.center;}getZoom(){return this.zoom;}
  addSource(id,source){this.sources[id]={...source,setData(data){this.data=data;}};}getSource(id){return this.sources[id];}addLayer(layer){this.layers[layer.id]=layer;}getLayer(id){return this.layers[id];}
  setStyle(style,options){this.style=style;this.styleOptions=options;this.sources={};this.layers={};}fitBounds(value,options){this.fitted={value,options};}easeTo(options){this.center={lng:options.center[0],lat:options.center[1]};this.zoom=options.zoom;}resize(){this.resized=true;}remove(){this.removed=true;}queryRenderedFeatures(){return this.hits||[];}
 }
 class Popup{constructor(){state.popups.push(this);}setLngLat(x){this.coords=x;return this;}setHTML(x){this.html=x;return this;}addTo(){return this;}remove(){this.removed=true;}}
 class LeafMap extends Evented{constructor(options){super();this.options=options;this.layers=[];this.attributions=[];state.leaflet.push(this);for(const k of ['scrollWheelZoom','dragging','touchZoom'])this[k]={active:false,enable(){this.active=true;},disable(){this.active=false;}};this.attributionControl={addAttribution:x=>this.attributions.push(x)};}createPane(){return{style:{}};}addControl(){}removeLayer(layer){this.layers=this.layers.filter(x=>x!==layer);}getCenter(){return this.options.center;}getZoom(){return this.options.zoom;}fitBounds(value,options){this.fitted={value,options};}setView(value,zoom){this.options.center={lat:value[0],lng:value[1]};this.options.zoom=zoom;}invalidateSize(){}remove(){this.removed=true;}}
 class LeafFeature extends Evented{constructor(coords,options){super();this.coordinates=coords;this.options={...options};}addTo(map){this.map=map;map.layers.push(this);return this;}bindPopup(){return this;}bindTooltip(){return this;}setStyle(options){Object.assign(this.options,options);}setRadius(r){this.options.radius=r;}remove(){if(this.map)this.map.removeLayer(this);}off(){this.handlers={};}}
 const leaf={map:(el,opts)=>new LeafMap(opts),circleMarker:(c,o)=>new LeafFeature(c,o),polyline:(c,o)=>new LeafFeature(c,o),tileLayer:(url,o)=>{const f=new LeafFeature(null,o);f.url=url;return f;},extend:Object.assign,Control:{},DomUtil:{},DomEvent:{}};
 const lib=Renderer.library({leaflet:leaf,mapboxgl:{supported:()=>supported,Map:Native,Popup,AttributionControl:class{constructor(o){this.options=o;}},NavigationControl:class{}},config:{publicToken:'pk.test.value'},provider:Provider,document:{baseURI:'https://example.test/demos/mta-scan/',getElementById:()=>element},schedule:fn=>state.queue.push(fn),onStatus:x=>state.status.push(x),reduced:true});
 const map=lib.map('map',{center:{lat:40.7,lng:-73.9},zoom:11,minZoom:9,maxZoom:16,maxBounds:[[40.4,-74.3],[41,-73.6]],zoomControl:true,scrollWheelZoom:false,dragging:false});
 const flush=()=>{while(state.queue.length)state.queue.shift()();};
 return{state,lib,map,flush,ready(){map.native.fire('style.load');flush();}};
}
test('uses native vector style, explicit public token and native GeoJSON layers without a Leaflet map',t=>{
 const e=environment();t.after(()=>e.map.remove());assert.equal(e.state.leaflet.length,0);assert.equal(e.map.native.options.style,'mapbox://styles/mapbox/dark-v11');assert.deepEqual(e.map.native.options.center,[-73.9,40.7]);assert.equal(e.map.getZoom(),11);
 const group=e.lib.layerGroup().addTo(e.map);e.lib.circleMarker([40.71,-73.91],{pane:'scores',radius:6,color:'#fff',fillColor:'#123456',opacity:.8,fillOpacity:.4}).addTo(group);e.lib.polyline([[40.7,-73.9],[40.8,-73.8]],{pane:'lines',weight:3,color:'#ff0000'}).addTo(group);e.ready();
 assert.deepEqual(e.map.native.getSource('mta-scores').data.features[0].geometry.coordinates,[-73.91,40.71]);assert.equal(e.map.native.getSource('mta-scores').data.features[0].properties.radius,6);assert.equal(e.map.native.getLayer('mta-lines-lines').type,'line');assert.equal(e.map.native.getLayer('mta-scores-circles').type,'circle');assert.equal(e.map.native.getSource('mta-lines').data.features.length,1);
});
test('filters, zoom radii and live/replay group switching update the actual rendered data',t=>{
 const e=environment();t.after(()=>e.map.remove());const live=e.lib.layerGroup().addTo(e.map),replay=e.lib.layerGroup();const point=e.lib.circleMarker([40.7,-73.9],{pane:'scores',radius:4}).addTo(live);e.ready();point.setStyle({opacity:0,fillOpacity:0});point.setRadius(9);e.flush();assert.equal(e.map.native.getSource('mta-scores').data.features[0].properties.fillOpacity,0);assert.equal(e.map.native.getSource('mta-scores').data.features[0].properties.radius,9);
 e.map.removeLayer(live);e.lib.circleMarker([40.8,-73.8],{pane:'scores',radius:12}).addTo(replay);replay.addTo(e.map);e.flush();assert.equal(e.map.native.getSource('mta-scores').data.features.length,1);assert.deepEqual(e.map.native.getSource('mta-scores').data.features[0].geometry.coordinates,[-73.8,40.8]);e.map.removeLayer(replay);live.addTo(e.map);e.flush();assert.equal(e.map.native.getSource('mta-scores').data.features[0].properties.radius,9);
});
test('style switching restores overlays and preserves filters rather than losing application data',t=>{
 const e=environment();t.after(()=>e.map.remove());const group=e.lib.layerGroup().addTo(e.map);e.lib.circleMarker([40.7,-73.9],{pane:'scores',fillOpacity:.17}).addTo(group);e.ready();e.map.setBasemap('streets');assert.equal(e.map.native.style,'mapbox://styles/mapbox/streets-v12');assert.deepEqual(e.map.native.styleOptions,{diff:false});assert.equal(e.map.loaded,false);e.ready();assert.equal(e.map.native.getSource('mta-scores').data.features[0].properties.fillOpacity,.17);
});
test('provider failure preserves camera, active groups and gesture lock in labelled fallback',t=>{
 const e=environment();t.after(()=>e.map.remove());const group=e.lib.layerGroup().addTo(e.map);e.lib.circleMarker([40.7,-73.9],{pane:'scores',radius:8}).addTo(group);e.ready();e.map.setView([40.8,-73.8],14);const native=e.map.native;native.fire('error',{error:{status:403}});e.flush();assert.equal(native.removed,true);assert.equal(e.state.leaflet.length,1);assert.equal(e.map.getZoom(),14);assert.deepEqual(e.map.getCenter(),{lat:40.8,lng:-73.8});assert.equal(e.map.leaflet.dragging.active,false);assert.ok(e.map.leaflet.layers.some(x=>x.options.radius===8));assert.equal(e.state.status.at(-1).renderer,'leaflet');assert.equal(e.state.status.at(-1).provider,'mapbox-raster');
});
test('unsupported WebGL is an explicit raster fallback, not a claimed native renderer',t=>{
 const e=environment(false);t.after(()=>e.map.remove());assert.equal(e.state.native.length,0);assert.equal(e.state.leaflet.length,1);assert.match(e.state.status.at(-1).reason,/WebGL/);assert.equal(e.state.status.at(-1).renderer,'leaflet');e.map.dragging.enable();assert.equal(e.map.leaflet.dragging.active,true);
});
test('only currently interactive observations can trigger station inspection',t=>{
 const e=environment();t.after(()=>e.map.remove());const group=e.lib.layerGroup().addTo(e.map);let clicks=0;const feature=e.lib.circleMarker([40.7,-73.9],{pane:'scores',interactive:true}).bindPopup(()=>'<p>Escaped upstream text</p>').on('click',()=>clicks++).addTo(group);e.ready();e.map.native.hits=[{id:feature.id,properties:{id:feature.id}}];e.map.native.fire('click',{point:{x:1,y:1}});assert.equal(clicks,1);feature.options.interactive=false;e.map.native.fire('click',{point:{x:1,y:1}});assert.equal(clicks,1);
});
test('fallback also degrades visibly to OSM if Mapbox raster tiles fail',t=>{
 const e=environment(false);t.after(()=>e.map.remove());const tiles=e.map.tileLayer;for(let i=0;i<3;i++)tiles.fire('tileerror');assert.equal(e.map.tileProvider,'osm');assert.match(e.map.tileLayer.url,/tile.openstreetmap.org/);assert.equal(e.state.status.at(-1).provider,'osm');
});
test('public configuration never accepts secret keys or arbitrary style endpoints',()=>{
 assert.equal(Provider.configuration({publicToken:'sk.do.not.use'}),null);assert.equal(Provider.vectorStyle('https://attacker.test/style'),null);assert.equal(Provider.vectorStyle('night'),'mapbox://styles/mapbox/dark-v11');
});
test('WebGL context loss falls back with the currently filtered state intact',t=>{
 const e=environment();t.after(()=>e.map.remove());const group=e.lib.layerGroup().addTo(e.map);e.lib.circleMarker([40.7,-73.9],{pane:'scores',opacity:.05,fillOpacity:.03,interactive:false}).addTo(group);e.ready();e.map.native.fire('webglcontextlost',{});e.flush();const point=e.map.leaflet.layers.find(x=>x.options.pane==='scores');assert.equal(point.options.fillOpacity,.03);assert.equal(point.options.interactive,false);assert.match(e.state.status.at(-1).reason,/context was lost/);
});
