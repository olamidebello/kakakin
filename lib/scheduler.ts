import {dispatchCampaign} from './campaign-dispatch';
export async function runDueCampaigns(db:D1Database){
 const due=await db.prepare("SELECT c.id,c.tenant FROM campaigns c JOIN tenants t ON t.id=c.tenant WHERE c.status='scheduled' AND c.automatic=1 AND c.scheduled<=? AND t.status='active' ORDER BY c.scheduled LIMIT 10").bind(new Date().toISOString()).all<{id:string,tenant:string}>();
 const results=[];for(const campaign of due.results){try{const response=await dispatchCampaign({db,tenant:campaign.tenant,profile:{email:'system:scheduler'}},campaign.id,{confirmation:'SEND'});results.push({id:campaign.id,status:response.status});if(!response.ok)await db.prepare('INSERT INTO events(id,tenant,actor,action,created) VALUES(?,?,?,?,?)').bind(crypto.randomUUID(),campaign.tenant,'system:scheduler','Scheduled dispatch blocked: '+JSON.stringify(await response.json()),new Date().toISOString()).run();}catch(e){results.push({id:campaign.id,error:String(e)})}}return results;
}
