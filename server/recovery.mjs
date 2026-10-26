// Retire a stale service worker from a site previously routed to this origin.
export const recoveryWorker=`'use strict';
self.addEventListener('install',event=>{self.skipWaiting()});
self.addEventListener('activate',event=>{event.waitUntil((async()=>{
 for(const name of await caches.keys())if(name.startsWith('africa-media-shell-'))await caches.delete(name);
 await self.clients.claim();
 await self.registration.unregister();
})())});
self.addEventListener('fetch',event=>{event.respondWith(fetch(new Request(event.request,{cache:'no-store'}))) });
`;
export const recoveryHTML=`<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Restore Kakakin</title><style>body{font:16px system-ui;background:#f5f7f1;color:#174e40;margin:0;padding:30px}main{max-width:480px;margin:10vh auto;background:white;padding:35px;border-radius:16px}p{line-height:1.7;color:#71806a}button{background:#174e40;color:white;border:0;border-radius:8px;padding:15px 22px;font:inherit;cursor:pointer}</style><main><h1>Restore Kakakin</h1><p>If this address previously displayed another app, clear its saved offline pages and reopen Kakakin. Your server account and campaign data are preserved.</p><button id="restore">Clear saved pages &amp; open Kakakin</button><p id="status" role="status"></p></main><script>
document.getElementById('restore').addEventListener('click',async()=>{
 const status=document.getElementById('status');status.textContent='Restoring this browser…';
 try{if('serviceWorker' in navigator)for(const r of await navigator.serviceWorker.getRegistrations())await r.unregister();
 if('caches' in window)for(const key of await caches.keys())await caches.delete(key);
 location.replace('/signin-with-chatgpt?return_to=%2F');
 }catch{status.textContent='Close this tab and reopen Kakakin, or clear saved site data for this hostname in your browser.'}
});
</script></html>`;
