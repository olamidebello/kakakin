import assert from 'node:assert/strict';
import {mkdtemp,mkdir,writeFile,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawn} from 'node:child_process';
import {createServer} from 'node:net';
import {passwordHash} from '../server/auth.mjs';
const folder=await mkdtemp(join(tmpdir(),'kakakin-gateway-test-'));const probe=createServer();await new Promise(r=>probe.listen(0,'127.0.0.1',r));const port=probe.address().port;await new Promise(r=>probe.close(r));const origin='http://127.0.0.1:'+port;
const accounts=join(folder,'accounts.json');await writeFile(accounts,JSON.stringify([{email:'owner@example.test',name:'Test owner',hash:passwordHash('Gateway-test-password-123'),version:1,disabled:false}]));
let logs='';const child=spawn(process.execPath,['server/gateway.mjs'],{cwd:process.cwd(),env:{...process.env,APP_ORIGIN:origin,SESSION_SECRET:'testing-only-session-secret-'.repeat(3),BOOTSTRAP_ADMIN_EMAIL:'owner@example.test',ACCOUNTS_FILE:accounts,DATA_DIR:join(folder,'data'),PORT:String(port)},stdio:['ignore','pipe','pipe']});child.stdout.on('data',x=>logs+=x);child.stderr.on('data',x=>logs+=x);
let checks=0;function check(v,label){assert.ok(v,label);checks++;console.log('PASS',label)}
try{
 for(let i=0;i<100;i++){if(child.exitCode!==null)throw Error(logs);try{const r=await fetch(origin+'/healthz');if(r.ok)break}catch{}await new Promise(r=>setTimeout(r,100));}
 check((await fetch(origin+'/healthz')).ok,'Server starts with migrated persistent database');
 check((await fetch(origin+'/',{redirect:'manual'})).status===303,'Dashboard requires login');
 check((await fetch(origin+'/favicon.svg')).ok,'Brand assets served without login');
 for(const path of ['/terms','/privacy','/copyright','/install']){const response=await fetch(origin+path,{redirect:'manual'});check(response.status===200&&(await response.text()).includes('Olamide Olatayo Bello Corporation'),'Public '+path+' page works without login')}
 const apk=await fetch(origin+'/downloads/kakakin.apk');check(apk.ok&&apk.headers.get('content-type')==='application/vnd.android.package-archive'&&new Uint8Array(await apk.arrayBuffer())[0]===80,'Signed Android APK served with correct MIME type');
 const recovery=await fetch(origin+'/__kakakin_recover');check(recovery.ok&&(await recovery.text()).includes('Restore Kakakin'),'Browser recovery page is available without login');
 const oldWorker=await fetch(origin+'/sw.js');check(oldWorker.ok&&oldWorker.headers.get('content-type').includes('javascript')&&(await oldWorker.text()).includes('registration.unregister'),'Stale media service worker can update to an unregistering replacement');
 check(oldWorker.headers.get('x-kakakin-app')==='kakakin','Gateway responses carry the Kakakin identity marker');
 const forged=await fetch(origin+'/api/workspace',{headers:{'oai-authenticated-user-id':'attacker','oai-authenticated-user-email':'owner@example.test'}});check(forged.status===401,'Forged identity headers do not authenticate requests');
 const rejected=await fetch(origin+'/signin-with-chatgpt',{method:'POST',headers:{origin:'https://attacker.example'},body:new URLSearchParams({email:'owner@example.test',password:'Gateway-test-password-123'})});check(rejected.status===403,'Cross-origin login rejected');
 const login=await fetch(origin+'/signin-with-chatgpt',{method:'POST',redirect:'manual',headers:{origin},body:new URLSearchParams({email:'owner@example.test',password:'Gateway-test-password-123',return_to:'/'})});check(login.status===303,'Administrator can log in');const cookie=login.headers.get('set-cookie').split(';')[0];check(login.headers.get('set-cookie').includes('HttpOnly'),'Session cookie is HttpOnly');
 const dashboard=await fetch(origin+'/',{headers:{cookie}});check(dashboard.ok&&(await dashboard.text()).includes('Every connection starts here.'),'Actual dashboard renders after server login');
 const workspace=await fetch(origin+'/api/workspace',{headers:{cookie,'oai-authenticated-user-id':'forged-user'}});const data=await workspace.json();check(workspace.ok&&data.superadmin&&data.user.email==='owner@example.test','Trusted gateway injects administrator identity and strips supplied headers');
 const post=async body=>{const r=await fetch(origin+'/api/workspace?tenant='+data.tenant,{method:'POST',headers:{cookie,origin,'content-type':'application/json'},body:JSON.stringify(body)});const j=await r.json();assert.equal(r.status,200,JSON.stringify(j));return j};
 await post({action:'fixtures',data:{count:2}});const campaign=await post({action:'save',resource:'campaigns',data:{name:'Server sandbox',channel:'SMS',message:'Local test',segment:'Sandbox',mode:'sandbox'}});const sent=await post({action:'send',id:campaign.id});check(sent.message.startsWith('2 simulated'),'Server runtime executes sandbox campaigns without external delivery');
 const scheduled=await post({action:'save',resource:'campaigns',data:{name:'Automatic server sandbox',channel:'SMS',message:'Scheduled local test',segment:'Sandbox',mode:'sandbox',automatic:true,scheduled:new Date(Date.now()-60000).toISOString()}});
 let complete=false;for(let i=0;i<145;i++){const r=await fetch(origin+'/api/workspace?tenant='+data.tenant,{headers:{cookie}});const state=await r.json();if(state.campaigns.find(c=>c.id===scheduled.id)?.status==='completed'){complete=true;break}await new Promise(r=>setTimeout(r,500))}check(complete,'Background scheduler dispatches a due authorized sandbox campaign');
 check((await fetch(origin+'/api/jobs/run',{method:'POST',headers:{cookie}})).status===404,'Internal scheduler endpoint is not exposed by gateway');
 const logout=await fetch(origin+'/signout-with-chatgpt',{redirect:'manual',headers:{cookie}});check(logout.headers.get('set-cookie').includes('Max-Age=0'),'Sign out clears session cookie');
 console.log(`\n${checks} server gateway integration checks passed. No external messages sent.`);
}finally{child.kill('SIGTERM');await new Promise(resolve=>{const timer=setTimeout(()=>{child.kill('SIGKILL');resolve()},10000);child.once('exit',()=>{clearTimeout(timer);resolve()})});await rm(folder,{recursive:true,force:true});if(child.exitCode!==0&&logs)console.log(logs)}
