import { Miniflare } from '../node_modules/.pnpm/miniflare@4.20260515.0_@types+node@22.19.19/node_modules/miniflare/dist/src/index.js';
import {readFile,readdir} from 'node:fs/promises';
import assert from 'node:assert/strict';
const modulePaths=(await readdir('dist/server',{recursive:true})).filter(p=>p.endsWith('.js')&&p!=='index.js');
const mf=new Miniflare({modules:[{type:'ESModule',path:'dist/server/index.js'},...modulePaths.map(p=>({type:'ESModule',path:'dist/server/'+p}))],compatibilityDate:'2026-05-15',compatibilityFlags:['nodejs_compat'],d1Databases:['DB']});
let checks=0;function check(v,label){assert.ok(v,label);checks++;console.log('PASS',label)}
try{
 const db=await mf.getD1Database('DB');for(const file of (await readdir('drizzle')).filter(f=>f.endsWith('.sql')).sort()){const sql=await readFile('drizzle/'+file,'utf8');for(const stmt of sql.split('--> statement-breakpoint').map(s=>s.trim()).filter(Boolean))await db.prepare(stmt).run();}
 const headers={'oai-authenticated-user-id':'test-owner','oai-authenticated-user-email':'owner@example.test','Content-Type':'application/json'};
 async function get(tenant='',as=headers){const r=await mf.dispatchFetch('https://kakakin.test/api/workspace'+(tenant?'?tenant='+tenant:''),{headers:as});return {status:r.status,body:await r.json()}}
 async function post(body,tenant,as=headers){const r=await mf.dispatchFetch('https://kakakin.test/api/workspace?tenant='+tenant,{method:'POST',headers:as,body:JSON.stringify(body)});return {status:r.status,body:await r.json()}}
 check((await get('',{})).status===401,'Anonymous workspace access rejected');
 const boot=await get();assert.equal(boot.status,200,JSON.stringify(boot.body));check(boot.body.superadmin,'Owner bootstrap has super admin role');const tenant=boot.body.tenant;
 const synthetic=await post({action:'fixtures',data:{count:3}},tenant);check(synthetic.status===200,'Synthetic contacts generated');
 const campaign=await post({action:'save',resource:'campaigns',data:{name:'Integration campaign',channel:'SMS',message:'Hello sandbox',segment:'Sandbox',mode:'sandbox'}},tenant);check(campaign.status===200,'Campaign persisted');
 const result=await post({action:'send',id:campaign.body.id},tenant);check(result.status===200&&result.body.message.startsWith('3 simulated'),'Sandbox campaign simulates three messages');
 check((await post({action:'send',id:campaign.body.id},tenant)).status===409,'Duplicate dispatch rejected');
 const state=await get(tenant);check(state.body.deliveries.length===3&&state.body.deliveries.every(x=>x.status==='simulated'),'Message ledger persists sandbox results');
 const contact={name:'Test Person',phone:'+12025550101',consent:1,consent_source:'Integration test only',channel:'SMS',segment:'Test'};
 check((await post({action:'save',resource:'contacts',data:contact},tenant)).status===200,'Consented contact persisted');
 check((await post({action:'save',resource:'contacts',data:contact},tenant)).status===400,'Duplicate contact rejected');
 check((await post({action:'save',resource:'contacts',data:{...contact,phone:'+12025550102',consent_source:''}},tenant)).status===400,'Consent without evidence rejected');
 check((await post({action:'save',resource:'referrals',data:{name:'Unsafe',message:'test',url:'javascript:alert(1)'}},tenant)).status===400,'Unsafe referral destination rejected');
 const second=await post({action:'save',resource:'tenants',data:{name:'Second workspace'}},tenant);check(second.status===200,'Second tenant created');
 check((await get(second.body.id)).body.contacts.length===0,'Tenant contact data isolated');
 const viewer={'oai-authenticated-user-id':'test-viewer','oai-authenticated-user-email':'viewer@example.test','Content-Type':'application/json'};
 await post({action:'save',resource:'members',data:{email:'viewer@example.test',role:'viewer'}},tenant);
 check((await get(tenant,viewer)).status===200,'Invited viewer can read workspace');
 check((await post({action:'fixtures',data:{count:1}},tenant,viewer)).status===403,'Viewer mutations rejected');
 check((await get(second.body.id,viewer)).status===403,'Viewer cannot access another tenant');
 const live=await post({action:'save',resource:'campaigns',data:{name:'Live missing credentials',channel:'SMS',message:'No outbound',segment:'Test',mode:'live'}},tenant);
 check((await post({action:'send',id:live.body.id,confirmation:'SEND'},tenant)).status===400,'Live sending disabled by default');
 await post({action:'settings',data:{liveEnabled:true,dailyLimit:100}},tenant);
 check((await post({action:'send',id:live.body.id,confirmation:'SEND'},tenant)).status===400,'Unconfigured provider blocks live dispatch');
 const ref=await post({action:'save',resource:'referrals',data:{name:'Join us',message:'A test referral',url:'https://example.com'}},tenant);
 const landing=await mf.dispatchFetch('https://kakakin.test/api/referral?id='+ref.body.id);check(landing.status===200,'Referral landing API returns public share content');
 const request=await mf.dispatchFetch('https://kakakin.test/api/referral',{method:'POST',headers:{'Content-Type':'application/json',origin:'https://kakakin.test'},body:JSON.stringify({id:ref.body.id,name:'Referral tester',phone:'+12025550103',consent:'on'})});check(request.status===200,'Referral join request recorded');
 const current=await get(tenant);check(current.body.contacts.find(c=>c.phone==='+12025550103')?.consent===0,'Public signup remains non-sendable pending verification');
 const webhook=await mf.dispatchFetch('https://kakakin.test/api/webhooks/meta',{method:'POST',body:'{}'});check(webhook.status===503,'Unconfigured webhook fails closed');
 console.log(`\n${checks} integration checks passed. No external messages sent.`);
}finally{await mf.dispose()}
