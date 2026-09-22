import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';


import { JSDOM, VirtualConsole } from 'jsdom';
const clone=x=>JSON.parse(JSON.stringify(x));
const fixture=name=>JSON.parse(readFileSync(new URL(`./ui-fixtures/${name}.json`,import.meta.url),'utf8'));
const tick=()=>new Promise(r=>setTimeout(r,5));
async function until(fn){for(let i=0;i<150;i++){if(fn())return;await tick();}throw new Error('Timed out waiting for UI');}
async function setup(name,{data=fixture(name),post,bootFail=false}={}){
 const calls=[],copied=[],errors=[];let fail=bootFail;
 const html=readFileSync(new URL(`../${name}/static/index.html`,import.meta.url),'utf8');
 const vc=new VirtualConsole();vc.on('jsdomError',e=>errors.push(e));
 const dom=new JSDOM(html,{url:`http://localhost/demos/${name}/`,runScripts:'dangerously',virtualConsole:vc,beforeParse(w){
  w.TextEncoder=TextEncoder;w.fetch=async(path,options={})=>{
   if(path==='api/examples'){if(fail)return{ok:false,status:503,json:async()=>({detail:'busy'})};return{ok:true,status:200,json:async()=>clone(data.examples)};}
   const request=JSON.parse(options.body);calls.push(request);const response=post?await post(request,calls.length):clone(data.responses[0].response);
   return response?.httpStatus?{ok:false,status:response.httpStatus,json:async()=>response.body}:{ok:true,status:200,json:async()=>response};
  };
  Object.defineProperty(w.navigator,'clipboard',{value:{writeText:async text=>copied.push(text)}});
 }});
 const w=dom.window,d=w.document,$=id=>d.getElementById(id);await until(()=>$('status').textContent.includes(bootFail?'unavailable':'Ready'));
 return {w,d,$,calls,copied,errors,data,retryBoot(){fail=false;$('retry').click();},close(){dom.window.close();}};
}
function input(ui,id,value){ui.$(id).value=value;ui.$(id).dispatchEvent(new ui.w.Event('input',{bubbles:true}));}
async function run(ui){const n=ui.calls.length;ui.$('go').click();await until(()=>ui.calls.length===n+1&&!ui.$('go').disabled);}

for(const name of ['smt-verify','fraud-graph']){
 test(`${name}: loads API presets without auto-analysis; stores capped in-memory snapshots and copies the selected run`,async()=>{
  const ui=await setup(name);try{
   assert.equal(ui.calls.length,0);assert.equal(ui.$('empty').hidden,false);
   await run(ui);assert.equal(ui.$('history').options.length,1);assert.equal(ui.$('copy').disabled,false);
   input(ui,name==='smt-verify'?'problem':'sender_id',name==='smt-verify'?ui.$('problem').value+' ':'OTHER_SYNTHETIC');
   assert.match(ui.$('status').textContent,/Edited inputs/);
   ui.$('copy').click();await until(()=>ui.copied.length===1);
   const snapshot=JSON.parse(ui.copied[0]);assert.deepEqual(snapshot.input,ui.calls[0]);assert.deepEqual(snapshot.response,ui.data.responses[0].response);
   for(let i=0;i<6;i++)await run(ui);
   assert.equal(ui.$('history').options.length,6);assert.equal(ui.w.localStorage.length,0);assert.equal(ui.w.sessionStorage.length,0);
   ui.$('clear').click();assert.equal(ui.$('copy').disabled,true);assert.equal(ui.$('empty').hidden,false);assert.equal(ui.$('out').textContent,'');assert.equal(ui.errors.length,0);
  }finally{ui.close();}
 });
 test(`${name}: retry recovers failed preset loading`,async()=>{
  const ui=await setup(name,{bootFail:true});try{assert.equal(ui.$('go').disabled,true);assert.match(ui.$('error').textContent,/503/);ui.retryBoot();await until(()=>ui.$('status').textContent.includes('Ready'));assert.equal(ui.$('go').disabled,false);assert.equal(ui.calls.length,0);}finally{ui.close();}
 });
 test(`${name}: errors preserve input, do not create results and render hostile messages as text`,async()=>{
  const hostile='<img src=x onerror="globalThis.compromised=true">';const ui=await setup(name,{post:()=>({httpStatus:422,body:{detail:[{loc:['body','candidate'],msg:hostile}]}})});
  try{const before=ui.$(name==='smt-verify'?'candidate':'amount').value;await run(ui);assert.equal(ui.$(name==='smt-verify'?'candidate':'amount').value,before);assert.equal(ui.$('copy').disabled,true);assert.match(ui.$('error').textContent,/img/);assert.equal(ui.d.querySelector('img'),null);assert.equal(ui.w.compromised,undefined);}finally{ui.close();}
 });
}

test('SMT: guided edits reach request; invalid integers cannot silently submit previous values',async()=>{
 const ui=await setup('smt-verify');try{const key=Object.keys(ui.data.examples.examples[0].candidate.assignment)[0];const field=ui.$('answer-0');field.value='nope';field.dispatchEvent(new ui.w.Event('change'));ui.$('go').click();await tick();assert.equal(ui.calls.length,0);field.value='2';field.dispatchEvent(new ui.w.Event('change'));await run(ui);assert.equal(ui.calls[0].candidate.assignment[key],2);}finally{ui.close();}
});
test('SMT: returned witness loads matching problem without issuing a new request',async()=>{
 const data=fixture('smt-verify');const row=data.responses.find(x=>x.response.sat_witness);assert.ok(row);
 const ui=await setup('smt-verify',{post:()=>clone(row.response)});try{await run(ui);assert.equal(ui.$('witness').disabled,false);ui.$('witness').click();assert.deepEqual(JSON.parse(ui.$('candidate').value),{status:'sat',assignment:row.response.sat_witness});assert.equal(ui.calls.length,1);assert.match(ui.$('status').textContent,/Verify to make a new request/);}finally{ui.close();}
});
test('SMT: arbitrary variable names, API text and history never become executable markup',async()=>{
 const data=fixture('smt-verify');const name='x\"><img src=x onerror="globalThis.compromised=true">';const ex=data.examples.examples[0];ex.title=name;ex.candidate.assignment={[name]:1};ex.problem.variables=[{name,domain:'int'}];ex.problem.constraints=[];
 const response={...data.responses[0].response,explanation:name,certified_assignment:{[name]:1},unsat_core:[{constraint_id:name,constraint_text:name}]};
 const ui=await setup('smt-verify',{data,post:()=>clone(response)});try{assert.equal(ui.$('assignment').querySelector('label').textContent,name);assert.equal(ui.d.querySelector('img'),null);await run(ui);assert.ok(ui.$('out').textContent.includes(name));assert.equal(ui.d.querySelector('img'),null);assert.equal(ui.w.compromised,undefined);}finally{ui.close();}
});
test('SMT: busy requests lock edits and prevent duplicate submission',async()=>{
 let resolve;const data=fixture('smt-verify');const ui=await setup('smt-verify',{post:()=>new Promise(r=>resolve=r)});try{ui.$('go').click();await until(()=>ui.calls.length===1);assert.equal(ui.$('problem').disabled,true);assert.equal(ui.$('preset').disabled,true);ui.$('go').click();assert.equal(ui.calls.length,1);resolve(clone(data.responses[0].response));await until(()=>!ui.$('go').disabled);assert.equal(ui.$('problem').disabled,false);}finally{ui.close();}
});
test('Fraud: displays actual feature values and state-aware comparisons without importance bars or probability claims',async()=>{
 const data=fixture('fraud-graph');const ui=await setup('fraud-graph',{post:(_,n)=>clone(data.responses[Math.min(n-1,2)].response)});try{await run(ui);await run(ui);assert.match(ui.$('out').textContent,/not a controlled counterfactual/);assert.match(ui.$('out').textContent,/not comparable units or model importance/);assert.match(ui.$('out').textContent,/not a probability/);assert.equal(ui.$('out').querySelector('.bar'),null);assert.ok(ui.$('out').textContent.includes(data.responses[1].response.risk_score.toFixed(3)));input(ui,'sender_id','\"><img src=x onerror="globalThis.compromised=true">');await run(ui);assert.equal(ui.d.querySelector('img'),null);assert.equal(ui.w.compromised,undefined);}finally{ui.close();}
});
test('Fraud: network failure is uncertain, never automatically retried or added to history',async()=>{
 const ui=await setup('fraud-graph',{post:()=>{throw new Error('Connection interrupted');}});try{await run(ui);await tick();assert.equal(ui.calls.length,1);assert.match(ui.$('status').textContent,/may already have recorded/);assert.equal(ui.$('copy').disabled,true);}finally{ui.close();}
});
for(const name of ['smt-verify','fraud-graph'])test(`${name}: leaving clears retained run data`,async()=>{const ui=await setup(name);try{await run(ui);ui.w.dispatchEvent(new ui.w.Event('pagehide'));assert.equal(ui.$('out').textContent,'');assert.equal(ui.$('copy').disabled,true);assert.equal(ui.$('history').disabled,true);}finally{ui.close();}});
