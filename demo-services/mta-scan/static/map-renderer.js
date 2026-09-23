/* Native Mapbox GL renderer with a narrow compatibility surface for MTA overlays.
   Leaflet is instantiated only when GL cannot run or the provider fails. */
(function(root,factory){
  if(typeof module==='object'&&module.exports)module.exports=factory();
  else root.MtaMapRenderer=factory();
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  var PANES=['linecase','lines','stops','scores'];
  var ATTR_OSM='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors';
  var ATTR_MAPBOX='<a href="https://www.mapbox.com/about/maps/">&copy; Mapbox</a> · '+ATTR_OSM+' · <a href="https://apps.mapbox.com/feedback/">Improve this map</a>';
  function finite(n,fallback){return typeof n==='number'&&Number.isFinite(n)?n:fallback;}
  function clamp(n,lo,hi){return Math.max(lo,Math.min(hi,n));}
  function lngLat(value){return Array.isArray(value)?[Number(value[1]),Number(value[0])]:[value.lng,value.lat];}
  function bounds(value){return [lngLat(value.getSouthWest()),lngLat(value.getNorthEast())];}
  function library(env){
    var leaf=env.leaflet,gl=env.mapboxgl,config=env.config,provider=env.provider;
    var doc=env.document||(typeof document!=='undefined'?document:null),nextId=1;
    var schedule=env.schedule||function(callback){return requestAnimationFrame(callback);};
    var status=env.onStatus||function(){};
    function Group(){this.items=[];this.map=null;}
    Group.prototype.addTo=function(map){map.addLayer(this);return this;};
    Group.prototype.clearLayers=function(){if(this.map)this.map._closePopups();this.items.forEach(function(item){if(item.leaflet)item.leaflet.remove();item.leaflet=null;item.group=null;});this.items=[];if(this.map)this.map._schedule();return this;};
    function Feature(kind,coordinates,options){this.kind=kind;this.coordinates=coordinates;this.options=Object.assign({},options);this.id=nextId++;this.events={};this.group=null;this.leaflet=null;this.popup=null;this.tooltip=null;}
    Feature.prototype.addTo=function(group){this.group=group;group.items.push(this);if(group.map)group.map._schedule();return this;};
    Feature.prototype.setStyle=function(options){Object.assign(this.options,options);if(this.leaflet)this.leaflet.setStyle(options);if(this.group&&this.group.map)this.group.map._schedule();return this;};
    Feature.prototype.setRadius=function(radius){this.options.radius=radius;if(this.leaflet)this.leaflet.setRadius(radius);if(this.group&&this.group.map)this.group.map._schedule();return this;};
    Feature.prototype.bindPopup=function(content,options){this.popup={content:content,options:options};return this;};
    Feature.prototype.bindTooltip=function(content,options){this.tooltip={content:content,options:options||{}};return this;};
    Feature.prototype.on=function(name,callback){(this.events[name]||(this.events[name]=[])).push(callback);return this;};
    Feature.prototype.geojson=function(){
      var options=this.options,coordinates=this.kind==='point'?lngLat(this.coordinates):this.coordinates.map(lngLat);
      var values=this.kind==='point'?[coordinates]:coordinates;
      if(!values.length||values.some(function(p){return !Number.isFinite(p[0])||!Number.isFinite(p[1]);}))return null;
      return {type:'Feature',id:this.id,geometry:{type:this.kind==='point'?'Point':'LineString',coordinates:coordinates},properties:{id:this.id,order:this.id,stroke:options.color||'#ffffff',fill:options.fillColor||options.color||'#ffffff',opacity:clamp(finite(options.opacity,1),0,1),fillOpacity:clamp(finite(options.fillOpacity,1),0,1),weight:Math.max(0,finite(options.weight,1)),radius:Math.max(0,finite(options.radius,3))}};
    };
    function BridgeMap(id,options){
      this.element=typeof id==='string'?doc.getElementById(id):id;this.options=options;this.groups=new Set();this.events={};this.controls=[];this.attributions=[];this.native=null;this.leaflet=null;this.popup=null;this.tooltip=null;this.permanent=[];this.lookup=new Map();this.pending=false;this.style='night';this.generation=0;this.loaded=false;this.dead=false;this.tileLayer=null;this.timer=null;this.resourceErrors=0;this._wheelEnabled=!!options.scrollWheelZoom;this._dragEnabled=options.dragging!==false;
      var self=this;
      this.scrollWheelZoom={enable:function(){self._wheelEnabled=true;self._applyInteractions();},disable:function(){self._wheelEnabled=false;self._applyInteractions();},enabled:function(){return self._wheelEnabled;}};
      this.dragging={enable:function(){self._dragEnabled=true;self._applyInteractions();},disable:function(){self._dragEnabled=false;self._applyInteractions();},enabled:function(){return self._dragEnabled;}};
      this.attributionControl={addAttribution:function(value){self.attributions.push(value);if(self.leaflet)self.leaflet.attributionControl.addAttribution(value);}};
      if(config&&gl&&typeof gl.supported==='function'&&gl.supported())this._startNative();
      else this._fallback(config?'WebGL 2 is unavailable.':'Public Mapbox configuration is unavailable.');
    }
    BridgeMap.prototype._emit=function(name,event){(this.events[name]||[]).forEach(function(callback){callback(event);});};
    BridgeMap.prototype.on=function(name,callback){(this.events[name]||(this.events[name]=[])).push(callback);return this;};
    BridgeMap.prototype._status=function(reason){status({renderer:this.native?'mapbox-gl':'leaflet',provider:this.native?'mapbox':this.tileProvider||'osm',style:this.style,reason:reason||'',ready:this.loaded});};
    BridgeMap.prototype._startNative=function(){
      var self=this,options=this.options;
      try{
        // Both bundles are pinned and served from the page's origin, without blob workers.
        gl.workerUrl=new URL('vendor/mapbox-gl-csp-worker.js?v=3.30.0',doc.baseURI).href;
        gl.workerCount=2;
        this.native=new gl.Map({container:this.element,accessToken:config.publicToken,style:provider.vectorStyle(this.style),center:lngLat(options.center),zoom:options.zoom-1,minZoom:options.minZoom-1,maxZoom:options.maxZoom-1,maxBounds:options.maxBounds.map(lngLat),renderWorldCopies:false,attributionControl:false,dragRotate:false,pitchWithRotate:false,maxPitch:0,fadeDuration:env.reduced?0:180,scrollZoom:this._wheelEnabled,dragPan:this._dragEnabled,touchZoomRotate:this._dragEnabled,keyboard:true});
        this.attribution=new gl.AttributionControl({compact:true,customAttribution:'lines &amp; stations: <a href="https://www.mta.info/developers">MTA GTFS</a>'});
        this.native.addControl(this.attribution,'bottom-right');
        if(options.zoomControl)this.native.addControl(new gl.NavigationControl({showCompass:false}),'top-left');
        this.native.touchZoomRotate.disableRotation();
        this.native.on('style.load',function(){if(!self.native)return;self.loaded=true;self.resourceErrors=0;clearTimeout(self.timer);self._restoreLayers();self._schedule();self._status();});
        this.native.on('error',function(event){if(!self.native)return;var e=event&&event.error;self.resourceErrors++;if(!self.loaded||e&&(e.status===401||e.status===403)||self.resourceErrors>=3)self._fallback('Mapbox vector resources could not load.');else self._status('Some map resources could not load; observations remain available.');});
        this.native.on('webglcontextlost',function(event){if(event&&event.preventDefault)event.preventDefault();self._fallback('WebGL context was lost.');});
        ['zoomend','moveend','click','mouseout'].forEach(function(name){self.native.on(name,function(event){self._emit(name,event);});});
        this.native.on('click',function(event){self._hit(event,false);});
        this.native.on('mousemove',function(event){self._hit(event,true);});
        this.native.on('mouseout',function(){if(self.tooltip){self.tooltip.remove();self.tooltip=null;}if(self.native)self.native.getCanvas().style.cursor='';});
        this._applyInteractions();this._armTimeout();this._status('Loading native Mapbox vector map.');
      }catch(error){this._fallback('Native Mapbox initialization failed.');}
    };
    BridgeMap.prototype._armTimeout=function(){var self=this;clearTimeout(this.timer);this.timer=setTimeout(function(){if(self.native&&!self.loaded)self._fallback('Mapbox vector loading timed out.');},12000);};
    BridgeMap.prototype._restoreLayers=function(){
      if(!this.native||!this.loaded)return;
      var map=this.native;
      PANES.forEach(function(pane){var id='mta-'+pane;if(!map.getSource(id))map.addSource(id,{type:'geojson',data:{type:'FeatureCollection',features:[]},attribution:''});
        if(!map.getLayer(id+'-lines'))map.addLayer({id:id+'-lines',type:'line',source:id,filter:['==',['geometry-type'],'LineString'],layout:{'line-cap':'round','line-join':'round'},paint:{'line-color':['get','stroke'],'line-opacity':['get','opacity'],'line-width':['get','weight']}});
        if(!map.getLayer(id+'-circles'))map.addLayer({id:id+'-circles',type:'circle',source:id,filter:['==',['geometry-type'],'Point'],layout:{'circle-sort-key':['get','order']},paint:{'circle-color':['get','fill'],'circle-opacity':['get','fillOpacity'],'circle-radius':['get','radius'],'circle-stroke-color':['get','stroke'],'circle-stroke-opacity':['get','opacity'],'circle-stroke-width':['get','weight']}});
      });
    };
    BridgeMap.prototype._schedule=function(){if(this.pending||this.dead)return;this.pending=true;var self=this;schedule(function(){self.pending=false;if(!self.dead)self._flush();});};
    BridgeMap.prototype._flush=function(){
      var self=this;
      if(this.leaflet){this.groups.forEach(function(group){group.items.forEach(function(item){if(!item.leaflet){item.leaflet=(item.kind==='point'?leaf.circleMarker:leaf.polyline)(item.coordinates,item.options);if(item.popup)item.leaflet.bindPopup(item.popup.content,item.popup.options);if(item.tooltip)item.leaflet.bindTooltip(item.tooltip.content,item.tooltip.options);Object.keys(item.events).forEach(function(name){item.events[name].forEach(function(fn){item.leaflet.on(name,fn);});});item.leaflet.addTo(self.leaflet);}item.leaflet.options.interactive=item.options.interactive!==false;});});return;}
      if(!this.native||!this.loaded)return;
      this._restoreLayers();var data={};PANES.forEach(function(pane){data[pane]=[];});this.lookup.clear();
      this.groups.forEach(function(group){group.items.forEach(function(item){var feature=item.geojson();if(!feature)return;var pane=PANES.includes(item.options.pane)?item.options.pane:'scores';data[pane].push(feature);self.lookup.set(item.id,item);});});
      PANES.forEach(function(pane){var source=self.native.getSource('mta-'+pane);if(source)source.setData({type:'FeatureCollection',features:data[pane]});});
      this.permanent.forEach(function(p){p.remove();});this.permanent=[];
      this.lookup.forEach(function(item){if(item.tooltip&&item.tooltip.options.permanent&&item.kind==='point'){var p=new gl.Popup({closeButton:false,closeOnClick:false,anchor:'bottom',offset:[0,-(item.options.radius||5)],className:'mta-tooltip'}).setLngLat(lngLat(item.coordinates)).setHTML(item.tooltip.content).addTo(self.native);self.permanent.push(p);}});
    };
    BridgeMap.prototype._hit=function(event,hover){
      if(!this.native||!this.loaded)return;
      var self=this,layers=['mta-scores-circles','mta-stops-circles'].filter(function(id){return !!self.native.getLayer(id);});
      var hits=this.native.queryRenderedFeatures(event.point,{layers:layers});
      var item=hits.map(function(hit){return self.lookup.get(Number(hit.id||hit.properties.id));}).find(function(f){return f&&f.options.interactive!==false&&(finite(f.options.opacity,1)>0||finite(f.options.fillOpacity,1)>0);});
      this.native.getCanvas().style.cursor=item?'pointer':'';
      if(hover){if(this.tooltip){this.tooltip.remove();this.tooltip=null;}if(item&&item.tooltip&&!item.tooltip.options.permanent)this.tooltip=new gl.Popup({closeButton:false,closeOnClick:false,anchor:'bottom',offset:12,className:'mta-tooltip'}).setLngLat(lngLat(item.coordinates)).setHTML(item.tooltip.content).addTo(this.native);return;}
      if(!item)return;
      if(this.popup)this.popup.remove();
      if(item.popup){var html=typeof item.popup.content==='function'?item.popup.content():item.popup.content;this.popup=new gl.Popup({closeButton:true,maxWidth:'320px',offset:10}).setLngLat(lngLat(item.coordinates)).setHTML(html).addTo(this.native);}
      (item.events.click||[]).forEach(function(fn){fn({target:item,latlng:{lat:item.coordinates[0],lng:item.coordinates[1]}});});
    };
    BridgeMap.prototype._closePopups=function(){if(this.popup)this.popup.remove();if(this.tooltip)this.tooltip.remove();this.popup=this.tooltip=null;this.permanent.forEach(function(p){p.remove();});this.permanent=[];};
    BridgeMap.prototype._applyInteractions=function(){if(this.native){this.native.scrollZoom[this._wheelEnabled?'enable':'disable']();this.native.dragPan[this._dragEnabled?'enable':'disable']();this.native.touchZoomRotate[this._dragEnabled?'enable':'disable']();this.native.touchZoomRotate.disableRotation();}else if(this.leaflet){this.leaflet.scrollWheelZoom[this._wheelEnabled?'enable':'disable']();this.leaflet.dragging[this._dragEnabled?'enable':'disable']();if(this.leaflet.touchZoom)this.leaflet.touchZoom[this._dragEnabled?'enable':'disable']();}};
    BridgeMap.prototype._fallback=function(reason){
      if(this.leaflet||this.dead)return;
      var center=this.getCenter(),zoom=this.getZoom();this._closePopups();clearTimeout(this.timer);this.loaded=false;
      if(this.native){var native=this.native;this.native=null;native.remove();}
      this.element.replaceChildren();
      this.leaflet=leaf.map(this.element,Object.assign({},this.options,{center:center,zoom:zoom,dragging:this._dragEnabled,scrollWheelZoom:this._wheelEnabled}));
      PANES.forEach(function(pane,index){this.leaflet.createPane(pane).style.zIndex=370+index*30;},this);
      var self=this;Object.keys(this.events).concat(['zoomend','moveend','click','mouseout']).filter(function(x,i,a){return a.indexOf(x)===i;}).forEach(function(name){self.leaflet.on(name,function(e){self._emit(name,e);});});
      this.attributions.forEach(function(a){self.leaflet.attributionControl.addAttribution(a);});
      this.controls.forEach(function(control){self.leaflet.addControl(control);});
      this._fallbackTiles(reason);this.loaded=true;this._applyInteractions();this._schedule();this._status(reason);
    };
    BridgeMap.prototype._fallbackTiles=function(reason,forceOsm){
      if(!this.leaflet)return;if(this.tileLayer){this.tileLayer.off();this.leaflet.removeLayer(this.tileLayer);}
      var descriptor=!forceOsm&&provider.descriptor(config,this.style,typeof devicePixelRatio!=='undefined'&&devicePixelRatio>1),self=this,errors=0,generation=++this.generation;
      this.tileProvider=descriptor?'mapbox-raster':'osm';
      var options={maxZoom:16,updateWhenIdle:true,keepBuffer:1,crossOrigin:true,referrerPolicy:'strict-origin-when-cross-origin',attribution:descriptor?ATTR_MAPBOX:ATTR_OSM};if(descriptor){options.tileSize=descriptor.tileSize;options.zoomOffset=descriptor.zoomOffset;}
      this.tileLayer=leaf.tileLayer(descriptor?descriptor.url:'https://tile.openstreetmap.org/{z}/{x}/{y}.png',options).addTo(this.leaflet);
      this.tileLayer.on('tileerror',function(){if(generation!==self.generation)return;errors++;if(descriptor&&errors>=3){self._fallbackTiles('Mapbox is unavailable; using OpenStreetMap fallback.',true);self._status('Mapbox is unavailable; using OpenStreetMap fallback.');}else if(!descriptor&&errors===3)self._status('Fallback tiles are unavailable; observations and the station list remain available.');});
      this._status(reason);
    };
    BridgeMap.prototype.setBasemap=function(style){if(!provider.vectorStyle(style))return;this.style=style;this.resourceErrors=0;this._closePopups();if(this.native){this.loaded=false;this.native.setStyle(provider.vectorStyle(style),{diff:false});this._armTimeout();this._status('Loading vector style.');}else{this._fallbackTiles('Leaflet fallback renderer.');this._status();}};
    BridgeMap.prototype.getCenter=function(){return this.native?this.native.getCenter():this.leaflet?this.leaflet.getCenter():this.options.center;};
    BridgeMap.prototype.getZoom=function(){return this.native?this.native.getZoom()+1:this.leaflet?this.leaflet.getZoom():this.options.zoom;};
    BridgeMap.prototype.fitBounds=function(value,options){options=options||{};if(this.native){var pad=options.padding||[0,0];this.native.fitBounds(bounds(value),{duration:options.animate===false||env.reduced?0:300,padding:{top:pad[1],bottom:pad[1],left:pad[0],right:pad[0]},maxZoom:options.maxZoom===undefined?this.options.maxZoom-1:options.maxZoom-1});}else if(this.leaflet)this.leaflet.fitBounds(value,options);return this;};
    BridgeMap.prototype.setView=function(value,zoom){if(this.native)this.native.easeTo({center:lngLat(value),zoom:zoom-1,duration:env.reduced?0:300});else if(this.leaflet)this.leaflet.setView(value,zoom);return this;};
    BridgeMap.prototype.invalidateSize=function(){if(this.native)this.native.resize();else if(this.leaflet)this.leaflet.invalidateSize({pan:false});return this;};
    BridgeMap.prototype.createPane=function(){return {style:{}};};
    BridgeMap.prototype.addLayer=function(group){this.groups.add(group);group.map=this;this._schedule();return this;};
    BridgeMap.prototype.removeLayer=function(group){this._closePopups();this.groups.delete(group);group.map=null;group.items.forEach(function(item){if(item.leaflet)item.leaflet.remove();item.leaflet=null;});this._schedule();return this;};
    BridgeMap.prototype.addControl=function(control){this.controls.push(control);if(this.leaflet)this.leaflet.addControl(control);else if(this.native){var self=this;this.native.addControl({onAdd:function(){var element=control.onAdd(self);element.classList.add('mapboxgl-ctrl');return element;},onRemove:function(){}},'top-left');}return this;};
    BridgeMap.prototype.remove=function(){this.dead=true;clearTimeout(this.timer);this._closePopups();if(this.native)this.native.remove();if(this.leaflet)this.leaflet.remove();this.native=this.leaflet=null;};
    return {map:function(id,options){return new BridgeMap(id,options);},layerGroup:function(){return new Group();},circleMarker:function(coords,options){return new Feature('point',coords,options);},polyline:function(coords,options){return new Feature('line',coords,options);},latLngBounds:leaf.latLngBounds,extend:leaf.extend,Control:leaf.Control,DomUtil:leaf.DomUtil,DomEvent:leaf.DomEvent};
  }
  return {library:library};
});
