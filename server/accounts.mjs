// Read JSON from stdin: {email,name,password,disabled?}. Never pass passwords as arguments.
import {readFile,mkdir,writeFile,rename} from 'node:fs/promises';
import {dirname} from 'node:path';
import {passwordHash} from './auth.mjs';
let input='';for await(const part of process.stdin){input+=part;if(input.length>16384)throw new Error('Input too large')}
const update=JSON.parse(input);const email=String(update.email||'').trim().toLowerCase();if(!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email))throw new Error('A valid email is required');
const file=process.env.ACCOUNTS_FILE||'/config/accounts.json';let accounts=[];try{accounts=JSON.parse(await readFile(file,'utf8'))}catch(e){if(e.code!=='ENOENT')throw e}
const old=accounts.find(a=>a.email===email);if(!old&&!update.password)throw new Error('A password is required for a new account');
const record={email,name:String(update.name||old?.name||email).slice(0,120),hash:update.password?passwordHash(update.password):old.hash,disabled:update.disabled??old?.disabled??false,version:(old?.version||0)+1};
accounts=accounts.filter(a=>a.email!==email);accounts.push(record);await mkdir(dirname(file),{recursive:true,mode:0o700});const temp=file+'.'+process.pid+'.tmp';await writeFile(temp,JSON.stringify(accounts,null,2)+'\n',{mode:0o600});await rename(temp,file);console.log(`Saved account ${email}. Existing sessions for this account are invalidated.`);
