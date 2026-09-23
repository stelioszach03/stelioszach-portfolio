/* Public map configuration only. Never accepts secret tokens or arbitrary URLs. */
(function(root,factory){
  if(typeof module==='object'&&module.exports)module.exports=factory();
  else root.MtaMapProvider=factory();
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';
  var styles={night:'dark-v11',streets:'streets-v12'};
  function configuration(value){
    if(!value||typeof value.publicToken!=='string'||!/^pk\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$/.test(value.publicToken)||value.publicToken.length>512)return null;
    return {publicToken:value.publicToken};
  }
  function descriptor(value,style,retina){
    var config=configuration(value);
    if(!config||!Object.prototype.hasOwnProperty.call(styles,style))return null;
    return {url:'https://api.mapbox.com/styles/v1/mapbox/'+styles[style]+'/tiles/512/{z}/{x}/{y}'+(retina?'@2x':'')+'?access_token='+encodeURIComponent(config.publicToken),tileSize:512,zoomOffset:-1,maxZoom:16};
  }
  function visibleSnapshot(snapshot,features,filters){
    return {schema_version:1,source:'MTA GTFS-Realtime observations; experimental model scores',generated_utc:snapshot.generated_utc||null,live:snapshot.live||null,window_counters:snapshot.counters||null,filters:filters,exported_map_observations:features.length,observations:features.map(function(f){return {geometry:f.geometry,properties:f.properties};}),score_interpretation:'Deviation scores are not calibrated probabilities or official incident reports.'};
  }
  return {configuration:configuration,descriptor:descriptor,visibleSnapshot:visibleSnapshot};
});
