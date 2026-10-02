const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/Milli/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async () => {
 const browser = await chromium.launch({headless:true,channel:'msedge'});
 try {
  const page = await browser.newPage(); const errors=[];
  page.on('pageerror', e => errors.push(e.message));
  await page.addScriptTag({path:'custom_components/synology_srm_extended/frontend/clients.js'});
  await page.evaluate(() => {
   window.requests=[];
   const el=document.createElement('synology-srm-client-info-v0112');
   el.stateObj={state:'on',attributes:{friendly_name:'Test NAS',srm_entry_id:'test',srm_client_mac:'02:11:22:33:44:55',ip_addr:'192.0.2.10'}};
   el.hass={callWS:async r => {
    window.requests.push(r);
    if(r.type.endsWith('/wol')) return {sent:true};
    return {available:true,poll_interval:5,traffic_settings:{source_unit:'B/s',rx_direction:'download'},clients:[{name:'Test NAS',mac:'02:11:22:33:44:55',online:true,details:{ip_addr:'192.0.2.10',connection:'ethernet',is_manual_hostname:true,transferRXRate:100000,transferTXRate:2000}}]};
   }};
   document.body.append(el);
  });
  const detail=page.locator('synology-srm-client-info-v0112 section');
  await detail.getByText('192.0.2.10',{exact:true}).waitFor();
  await detail.getByText('02:11:22:33:44:55',{exact:true}).waitFor();
  await detail.getByText('Název nastaven ručně',{exact:true}).waitFor();
  assert.equal(await detail.locator('svg circle').count(),2);
  await detail.getByRole('button',{name:'Probudit přes LAN (z HA)',exact:true}).click();
  await detail.getByText(/Paket odeslán z HA/).waitFor();
  assert.equal(await page.evaluate(()=>window.requests.filter(r=>r.type.endsWith('/wol')).length),1);
  await page.evaluate(() => {
   const el = document.createElement('synology-srm-clients-info-v0112');
   el.stateObj = {attributes:{srm_entry_id:'test',srm_client_scope:'lan'}};
   el.hass = {callWS: async r => {
    window.requests.push(r);
    if(r.type.endsWith('/measurement')) return {interval_seconds:5};
    return {available:true,clients:[
     {name:'LAN NAS',mac:'02:11:22:33:44:55',online:true,wireless:false,details:{}},
     {name:'WiFi PC',mac:'02:11:22:33:44:66',online:true,wireless:true,details:{}},
     {name:'Offline PC',mac:'02:11:22:33:44:77',online:false,wireless:false,details:{}}
    ]};
   }};
   document.body.append(el);
  });
  const scoped=page.locator('synology-srm-clients-info-v0112');
  await scoped.getByRole('button',{name:'LAN NAS',exact:true}).waitFor();
  assert.equal(await scoped.locator('tbody tr').count(),1);
  await scoped.getByRole('button',{name:'LAN NAS',exact:true}).click();
  assert.equal(await scoped.locator('#measurement-phase').count(),0);
  assert.deepEqual(errors,[]);
  console.log('Edge: native element creation, IP, MAC, WOL click and response PASS (mock transport; no packet sent).');
 } finally {await browser.close();}
})();
