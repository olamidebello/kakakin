import {dispatchCampaign} from '../../../lib/campaign-dispatch';
import { env } from 'cloudflare:workers';
import { getChatGPTUser } from '../../chatgpt-auth';
export const dynamic='force-dynamic';
const now=()=>new Date().toISOString(); const uid=()=>crypto.randomUUID();
const tables=['contacts','campaigns','templates','referrals','members','deliveries','events'];
const fields:Record<string,string[]>={contacts:['name','phone','email','segment','consent','consent_source','channel','status'],campaigns:['name','channel','message','segment','mode','scheduled','template','automatic'],templates:['name','channel','body','provider_name','language'],referrals:['name','message','url'],members:['email','role'],tenants:['name','status','plan'],users:['name','status','role']};
function fail(message:string,status=400){return Response.json({error:message},{status})}
async function context(req:Request){
 const user=await getChatGPTUser();if(!user)throw new Error('401:Sign in to open your workspace.');
 const db=env.DB;if(!db)throw new Error("Database binding unavailable");let profile:any=await db.prepare('SELECT * FROM users WHERE id=?').bind(user.userId).first();
 if(!profile){const count:any=await db.prepare("SELECT COUNT(*) n FROM users WHERE role='superadmin'").first();await db.prepare('INSERT OR IGNORE INTO users (id,email,name,role,status,created) VALUES (?,?,?,?,?,?)').bind(user.userId,user.email.toLowerCase(),user.displayName,count.n===0&&(!(env as any).BOOTSTRAP_ADMIN_EMAIL||user.email.toLowerCase()===(env as any).BOOTSTRAP_ADMIN_EMAIL.toLowerCase())?'superadmin':'member','active',now()).run();profile=await db.prepare('SELECT * FROM users WHERE id=?').bind(user.userId).first();}
 if(profile.status!=='active')throw new Error('403:Your account is suspended.');
 const superadmin=profile.role==='superadmin';
 let tenants=superadmin?(await db.prepare('SELECT * FROM tenants ORDER BY created').all()).results:(await db.prepare('SELECT t.* FROM tenants t JOIN members m ON m.tenant=t.id WHERE lower(m.email)=?').bind(profile.email.toLowerCase()).all()).results;
 if(superadmin&&!tenants.length){const id=uid();await db.prepare('INSERT INTO tenants (id,name,status,plan,created) VALUES (?,?,?,?,?)').bind(id,'My workspace','active','Starter',now()).run();tenants=(await db.prepare('SELECT * FROM tenants ORDER BY created').all()).results;}
 const target=new URL(req.url).searchParams.get('tenant')||String(tenants[0]?.id||'');const tenant:any=tenants.find((t:any)=>t.id===target);if(!tenant)throw new Error('403:No access to this workspace. Ask an administrator for an invitation.');
 const membership:any=superadmin?{role:'owner'}:await db.prepare('SELECT role FROM members WHERE tenant=? AND lower(email)=?').bind(target,profile.email.toLowerCase()).first();
 if(tenant.status!=='active'&&!superadmin)throw new Error('403:Workspace is suspended.');
 return {db,profile,superadmin,tenants,tenant:target,role:membership?.role||'viewer'};
}
function error(e:any){const m=String(e.message||e);const match=m.match(/^(401|403|409):/);return fail(match?m.slice(4):m,match?Number(match[1]):400)}
export async function GET(req:Request){try{const c=await context(req);const data:any={scheduler:(env as any).SERVER_JOB_TOKEN?'server-active':'host-trigger-required',user:c.profile,superadmin:c.superadmin,role:c.role,tenants:c.tenants,tenant:c.tenant,provider:{whatsapp:!!((env as any).WHATSAPP_TOKEN&&(env as any).WHATSAPP_PHONE_ID&&(env as any).WHATSAPP_API_VERSION),sms:!!((env as any).TWILIO_ACCOUNT_SID&&(env as any).TWILIO_AUTH_TOKEN&&(env as any).TWILIO_FROM)}};for(const table of tables)data[table]=(await c.db.prepare(`SELECT * FROM ${table} WHERE tenant=? ORDER BY ${table==='members'?'id':'created'} DESC LIMIT 500`).bind(c.tenant).all()).results;data.settings=JSON.parse((await c.db.prepare('SELECT value FROM settings WHERE id=?').bind(c.tenant).first<any>())?.value||'{}');if(c.superadmin)data.users=(await c.db.prepare('SELECT * FROM users ORDER BY created DESC LIMIT 500').all()).results;return Response.json(data)}catch(e){return error(e)}}
export async function POST(req:Request){try{
 const c=await context(req);if(c.role==='viewer')return fail('Viewer accounts cannot change data.',403);
 if(req.headers.get('origin')&&req.headers.get('origin')!==new URL(req.url).origin)return fail('Invalid request origin.',403);
 const b:any=await req.json();const {action,resource}=b;const data=b.data||{};const id=b.id||uid();
 const audit=async(text:string)=>c.db.prepare('INSERT INTO events (id,tenant,actor,action,created) VALUES (?,?,?,?,?)').bind(uid(),c.tenant,c.profile.email,text,now()).run();
 if(resource==='tenants'||resource==='users'){if(!c.superadmin)return fail('Super admin access required.',403);}
 if(resource==='members'&&!['owner','admin'].includes(c.role))return fail('Workspace admin access required.',403);
 if(action==='settings'){if(!['owner','admin'].includes(c.role))return fail('Workspace admin access required.',403);const v={dailyLimit:Math.max(1,Math.min(1000,Number(data.dailyLimit)||100)),frequencyDays:Math.max(1,Number(data.frequencyDays)||1),liveEnabled:!!data.liveEnabled,paused:!!data.paused,timezone:String(data.timezone||'UTC'),unsubscribeText:String(data.unsubscribeText||'Reply STOP to unsubscribe.').slice(0,200)};await c.db.prepare('INSERT INTO settings (id,tenant,value) VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET value=excluded.value').bind(c.tenant,c.tenant,JSON.stringify(v)).run();await audit('Updated workspace sending controls');return Response.json({ok:true});}
 if(action==='fixtures'){const n=Math.min(50,Math.max(1,Number(data.count)||5));for(let i=0;i<n;i++)await c.db.prepare('INSERT INTO contacts (id,tenant,name,phone,email,segment,consent,consent_source,channel,status,test,created) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)').bind(uid(),c.tenant,`Test contact ${i+1}`,`test:${uid().slice(0,8)}`,'','Sandbox',1,'Synthetic test record','Both','active',1,now()).run();await audit(`Generated ${n} non-routable test contacts`);return Response.json({ok:true});}
 if(action==='send')return await dispatchCampaign(c,id,b);
 if(action==='pause'){await c.db.prepare("UPDATE campaigns SET status='paused' WHERE id=? AND tenant=? AND status IN ('draft','scheduled')").bind(id,c.tenant).run();await audit('Paused campaign');return Response.json({ok:true});}
 if(!fields[resource])return fail('Unknown resource.');
 if(action==='delete'){
 if(resource==='users'&&id===c.profile.id)return fail('You cannot delete your own administrator account.');
 if(resource==='tenants')return fail('Suspend a workspace to preserve its audit history.');
 if(resource==='campaigns'){const current:any=await c.db.prepare('SELECT status FROM campaigns WHERE id=? AND tenant=?').bind(id,c.tenant).first();if(current?.status==='sending')return fail('An active dispatch cannot be deleted.');}
 if(resource==='users'){await c.db.prepare('UPDATE users SET status=? WHERE id=?').bind('suspended',id).run();}
 else await c.db.prepare(`DELETE FROM ${resource} WHERE id=? ${resource==='users'?'':'AND tenant=?'}`).bind(...(resource==='users'?[id]:[id,c.tenant])).run();await audit(`Removed ${resource} record`);return Response.json({ok:true});}
 if(action!=='save')return fail('Unknown action.');
 const clean:any={};for(const key of fields[resource])if(data[key]!==undefined)clean[key]=typeof data[key]==='string'?data[key].trim().slice(0,4000):data[key];
 if(clean.name!==undefined&&!clean.name)return fail('Name is required.');
 if(resource==='contacts'){const oldContact:any=await c.db.prepare('SELECT phone,test FROM contacts WHERE id=? AND tenant=?').bind(id,c.tenant).first();if(!(oldContact?.test&&oldContact.phone===clean.phone)&&!/^\+[1-9]\d{7,14}$/.test(clean.phone||''))return fail('Enter a valid international phone number, starting with +.');clean.consent=clean.consent?1:0;if(clean.consent&&!clean.consent_source)return fail('Record how the contact opted in.');clean.consent_at=clean.consent?now():null;if(clean.channel&&!['WhatsApp','SMS','Both'].includes(clean.channel))return fail('Invalid channel.');const duplicate:any=await c.db.prepare('SELECT id FROM contacts WHERE tenant=? AND phone=? AND id!=?').bind(c.tenant,clean.phone,id).first();if(duplicate)return fail('This number already exists in this workspace.');}
 if(resource==='referrals'){try{const u=new URL(clean.url||'');if(!['http:','https:'].includes(u.protocol))return fail('Use an http or https destination.');}catch{return fail('Enter a valid destination URL.');}}
 if(resource==='members'){clean.email=String(clean.email||'').toLowerCase();if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(clean.email))return fail('Enter a valid email.');if(!['admin','manager','viewer'].includes(clean.role))return fail('Invalid role.');}
 if(resource==='users'&&clean.role&&!['superadmin','member'].includes(clean.role))return fail('Invalid platform role.');
 if(resource==='users'&&id===c.profile.id&&(clean.role==='member'||clean.status==='suspended'))return fail('You cannot remove your own admin access.');
 if(resource==='campaigns'){clean.automatic=clean.automatic?1:0;if(clean.automatic&&!clean.scheduled)return fail('Choose a time for automatic dispatch.');if(clean.automatic&&clean.mode==='live'&&data.liveAuthorization!=='SEND')return fail('Type SEND to authorize automatic live delivery.');if(!['WhatsApp','SMS'].includes(clean.channel)||!['sandbox','live'].includes(clean.mode))return fail('Choose a valid channel and mode.');if(!clean.message)return fail('Message is required.');if(clean.scheduled&&!Number.isFinite(Date.parse(clean.scheduled)))return fail('Invalid scheduled date.');}
 if(clean.status&&!['active','suspended','unsubscribed'].includes(clean.status))return fail('Invalid status.');
 const existing=await c.db.prepare(`SELECT id FROM ${resource} WHERE id=? ${['users','tenants'].includes(resource)?'':'AND tenant=?'}`).bind(...(['users','tenants'].includes(resource)?[id]:[id,c.tenant])).first();
 if(resource==='users'&&!existing)return fail('Users must sign in before their account can be managed.');
 if(existing){if(resource==='campaigns'){const old:any=await c.db.prepare('SELECT status FROM campaigns WHERE id=?').bind(id).first();if(['completed','sending'].includes(old.status))return fail('Completed campaigns cannot be edited.');}const keys=Object.keys(clean);await c.db.prepare(`UPDATE ${resource} SET ${keys.map(k=>k+'=?').join(',')} WHERE id=?`).bind(...keys.map(k=>clean[k]),id).run();}
 else{if(resource==='contacts'){clean.test=0;clean.status=clean.status||'active';}if(resource==='campaigns')clean.status=clean.scheduled?'scheduled':'draft';if(!['members'].includes(resource))clean.created=now();if(!['users','tenants'].includes(resource))clean.tenant=c.tenant;clean.id=id;const keys=Object.keys(clean);await c.db.prepare(`INSERT INTO ${resource} (${keys.join(',')}) VALUES (${keys.map(()=>'?').join(',')})`).bind(...keys.map(k=>clean[k]??null)).run();}
 await audit(`${existing?'Updated':'Created'} ${resource}: ${clean.name||clean.email||id}`);return Response.json({ok:true,id});
 }catch(e){return error(e)}}
