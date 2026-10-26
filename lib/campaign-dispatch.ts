import {env} from 'cloudflare:workers';
const now=()=>new Date().toISOString(); const uid=()=>crypto.randomUUID();
function fail(message:string,status=400){return Response.json({error:message},{status})}
async function dispatchCampaignImpl(c:{db:D1Database,tenant:string,profile:{email:string}},id:string,b:any){
 const audit=async(text:string)=>c.db.prepare('INSERT INTO events (id,tenant,actor,action,created) VALUES (?,?,?,?,?)').bind(uid(),c.tenant,c.profile.email,text,now()).run();
 const campaign:any=await c.db.prepare('SELECT * FROM campaigns WHERE id=? AND tenant=?').bind(id,c.tenant).first();if(!campaign)return fail('Campaign not found.',404);if(campaign.status==='completed'||campaign.status==='sending')return fail('This campaign was already dispatched.',409);
 const settings=JSON.parse((await c.db.prepare('SELECT value FROM settings WHERE id=?').bind(c.tenant).first<any>())?.value||'{}');if(settings.paused)return fail('Sending is paused for this workspace.');
 const live=campaign.mode==='live';if(live&&(!settings.liveEnabled||b.confirmation!=='SEND'))return fail('Enable live sending in settings and confirm with SEND.');
 if(campaign.scheduled&&Date.parse(campaign.scheduled)>Date.now())return fail('This campaign is scheduled for a future time. Dispatch when due.');
 const all:any[]=(await c.db.prepare('SELECT * FROM contacts WHERE tenant=? AND consent=1 AND status=?').bind(c.tenant,'active').all()).results;
 const contacts=all.filter((x:any)=>(campaign.segment==='All contacts'||campaign.segment===x.segment)&&(x.channel==='Both'||x.channel===campaign.channel)&&(!live||!x.test));if(!contacts.length)return fail('No eligible opted-in contacts match this audience.');if(contacts.length>50)return fail('Split this audience into batches of up to 50 recipients.');
 const vars=env as any;let template:any=null;if(live&&campaign.channel==='WhatsApp'){if(!vars.WHATSAPP_TOKEN||!vars.WHATSAPP_PHONE_ID||!vars.WHATSAPP_API_VERSION)return fail('WhatsApp credentials are not configured.');template=await c.db.prepare('SELECT * FROM templates WHERE id=? AND tenant=?').bind(campaign.template||'',c.tenant).first();if(!template?.provider_name)return fail('Select a template approved in your WhatsApp Business account.');}
 if(live&&campaign.channel==='SMS'&&(!vars.TWILIO_ACCOUNT_SID||!vars.TWILIO_AUTH_TOKEN||!vars.TWILIO_FROM))return fail('SMS provider credentials are not configured.');
 const day=now().slice(0,10);const sent:any=await c.db.prepare("SELECT COUNT(*) n FROM deliveries WHERE tenant=? AND status!='simulated' AND created LIKE ?").bind(c.tenant,day+'%').first();if(live&&sent.n+contacts.length>(settings.dailyLimit||100))return fail('Daily sending limit would be exceeded.');
 const claim=await c.db.prepare("UPDATE campaigns SET status='sending' WHERE id=? AND tenant=? AND status IN ('draft','scheduled','paused')").bind(id,c.tenant).run();if(!claim.meta.changes)return fail('Campaign cannot be sent from its current state.',409);
 let accepted=0,failed=0;for(const contact of contacts){let status=live?'accepted':'simulated',providerId=null,err=null;try{if(live){const current:any=await c.db.prepare('SELECT consent,status FROM contacts WHERE id=? AND tenant=?').bind(contact.id,c.tenant).first();if(!current?.consent||current.status!=='active')throw new Error('Consent withdrawn');const cutoff=new Date(Date.now()-(settings.frequencyDays||1)*86400000).toISOString();const recent=await c.db.prepare("SELECT id FROM deliveries WHERE contact=? AND tenant=? AND status IN ('accepted','delivered','read') AND created>? LIMIT 1").bind(contact.id,c.tenant,cutoff).first();if(recent)throw new Error('Frequency limit: recipient contacted recently');let response:Response;
 if(campaign.channel==='WhatsApp')response=await fetch(`https://graph.facebook.com/${vars.WHATSAPP_API_VERSION}/${vars.WHATSAPP_PHONE_ID}/messages`,{method:'POST',signal:AbortSignal.timeout(10000),headers:{Authorization:`Bearer ${vars.WHATSAPP_TOKEN}`,'Content-Type':'application/json'},body:JSON.stringify({messaging_product:'whatsapp',to:contact.phone.replace('+',''),type:'template',template:{name:template.provider_name,language:{code:template.language}}})});
 else response=await fetch(`https://api.twilio.com/2010-04-01/Accounts/${vars.TWILIO_ACCOUNT_SID}/Messages.json`,{method:'POST',signal:AbortSignal.timeout(10000),headers:{Authorization:'Basic '+btoa(vars.TWILIO_ACCOUNT_SID+':'+vars.TWILIO_AUTH_TOKEN),'Content-Type':'application/x-www-form-urlencoded'},body:new URLSearchParams({To:contact.phone,From:vars.TWILIO_FROM,Body:campaign.message+'\n'+(settings.unsubscribeText||'Reply STOP to unsubscribe.')})});
 const result:any=await response.json();if(!response.ok)throw new Error(result.error?.message||result.message||'Provider rejected the message');providerId=result.sid||result.messages?.[0]?.id||null;
 }accepted++;}catch(e:any){status='failed';err=String(e.message).slice(0,300);failed++;}
 await c.db.prepare('INSERT INTO deliveries (id,tenant,campaign,contact,status,provider_id,error,created) VALUES (?,?,?,?,?,?,?,?)').bind(uid(),c.tenant,id,contact.id,status,providerId,err,now()).run();}
 await c.db.prepare("UPDATE campaigns SET status='completed' WHERE id=? AND tenant=?").bind(id,c.tenant).run();await audit(`${live?'Dispatched':'Simulated'} campaign: ${campaign.name} (${accepted} accepted, ${failed} failed)`);return Response.json({ok:true,message:`${accepted} ${live?'accepted by provider':'simulated'}, ${failed} failed. Provider acceptance is not confirmed delivery.`});

}

export async function dispatchCampaign(c:{db:D1Database,tenant:string,profile:{email:string}},id:string,b:any){
 const token=crypto.randomUUID();
 await c.db.prepare('DELETE FROM dispatch_locks WHERE tenant=? AND created<?').bind(c.tenant,new Date(Date.now()-15*60000).toISOString()).run();
 const lock=await c.db.prepare('INSERT OR IGNORE INTO dispatch_locks (tenant,token,created) VALUES (?,?,?)').bind(c.tenant,token,now()).run();
 if(!lock.meta.changes)return fail('A campaign is already being dispatched in this workspace. Try again after it finishes.',409);
 try{return await dispatchCampaignImpl(c,id,b)}finally{await c.db.prepare('DELETE FROM dispatch_locks WHERE tenant=? AND token=?').bind(c.tenant,token).run()}
}
