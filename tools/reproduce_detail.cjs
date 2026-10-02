const { chromium } = require('C:/Users/Milli/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{ const b=await chromium.launch({headless:true,channel:"msedge"});const p=await b.newPage();p.on('pageerror',e=>console.log('BROWSER ERROR:',e.message));await p.addScriptTag({path:'custom_components/synology_srm_extended/frontend/clients.js'});console.log(await p.evaluate(()=>{const e=document.createElement('synology-srm-client-info-v019');document.body.append(e);return {constructor:e.constructor.name,shadow:!!e.shadowRoot}}));await b.close();})();

