import {env} from 'cloudflare:workers';
import {runDueCampaigns} from '../../../../lib/scheduler';
import {same} from '../../../../lib/webhook-security';
export async function POST(req:Request){const token=(env as any).SERVER_JOB_TOKEN;if(!token||!same(req.headers.get('authorization')||'','Bearer '+token))return new Response('Forbidden',{status:403});if(!env.DB)return new Response('Database unavailable',{status:503});return Response.json({results:await runDueCampaigns(env.DB)})}
