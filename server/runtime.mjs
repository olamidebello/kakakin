import {createRequire} from 'node:module';
import {readFile,readdir,mkdir} from 'node:fs/promises';
import {resolve,join} from 'node:path';
import {createHash} from 'node:crypto';
// Resolve the exact transitive runtime pinned by the repository lockfile.
const require=createRequire(import.meta.url);const wranglerRequire=createRequire(require.resolve('wrangler/package.json'));
const {Miniflare}=wranglerRequire('miniflare');
export async function createRuntime({root=process.cwd(),state=process.env.DATA_DIR||'/data',bindings={}}={}){
 await mkdir(state,{recursive:true});const server=resolve(root,'dist/server');const paths=(await readdir(server,{recursive:true})).filter(p=>p.endsWith('.js')&&p!=='index.js');
 const mf=new Miniflare({modules:[{type:'ESModule',path:join(server,'index.js')},...paths.map(p=>({type:'ESModule',path:join(server,p)}))],compatibilityDate:'2026-05-15',compatibilityFlags:['nodejs_compat'],d1Databases:['DB'],d1Persist:join(state,'d1'),bindings,host:'127.0.0.1',port:0});
 try{const db=await mf.getD1Database('DB');await db.prepare('CREATE TABLE IF NOT EXISTS kakakin_migrations (name TEXT PRIMARY KEY,checksum TEXT NOT NULL,applied_at TEXT NOT NULL)').run();
 for(const name of (await readdir(join(root,'drizzle'))).filter(f=>f.endsWith('.sql')).sort()){const sql=await readFile(join(root,'drizzle',name),'utf8');const hash=createHash('sha256').update(sql).digest('hex');const old=await db.prepare('SELECT checksum FROM kakakin_migrations WHERE name=?').bind(name).first();if(old){if(old.checksum!==hash)throw new Error('Applied migration changed: '+name);continue}const statements=sql.split('--> statement-breakpoint').map(s=>s.trim()).filter(Boolean);await db.batch([...statements.map(s=>db.prepare(s)),db.prepare('INSERT INTO kakakin_migrations VALUES(?,?,?)').bind(name,hash,new Date().toISOString())]);console.log('Applied migration',name)}
 return {mf,db,fetch:(url,init)=>mf.dispatchFetch(url,init),close:()=>mf.dispose()};
 }catch(e){await mf.dispose();throw e}
}
