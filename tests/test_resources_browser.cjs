const assert=require('node:assert/strict');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/Milli/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try {
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.addScriptTag({path:'custom_components/synology_srm_extended/frontend/clients.js'});
  await page.evaluate(()=>{
   document.body.style.cssText='background:#172b36;color:white;margin:0;font:16px sans-serif';
   const resource=document.createElement('synology-srm-resource-info-v0112');
   resource.stateObj={state:'67',attributes:{srm_entry_id:'router',resource_kind:'ram_usage',friendly_name:'Využití RAM',unit_of_measurement:'%'}};
   resource.hass={language:'cs',callWS:async()=>({history:[{time:100,ram_usage:60},{time:400,ram_usage:67}],mesh:[{id:7,name:'Ložnice',model:'RT2600ac',uptime:30,clients:[{name:'Telefon',online:true}],ports:[{port:'LAN1',speed:100}]}]})};
   document.body.append(resource);
  });
  const card=page.locator('synology-srm-resource-info-v0112');
  await card.locator('svg').waitFor();
  assert((await card.locator('.ring').boundingBox()).width>=170);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=390),true);
  assert.equal(await card.locator('svg path[stroke="#29b6f6"]').count(),1);
  await page.screenshot({path:'dist/mobile-resources-0.1.12.png'});
  await page.evaluate(async()=>{const e=document.querySelector('synology-srm-resource-info-v0112');e.stateObj={state:'2',attributes:{srm_entry_id:'router',resource_kind:'mesh_nodes'}};await e.loadResources(true);});
  await card.getByRole('heading',{name:'Ložnice'}).waitFor();
  assert((await card.locator('#mesh').innerText()).includes('Telefon'));
  assert((await card.locator('#mesh').innerText()).includes('LAN1: 100'));
  assert.deepEqual(errors,[]);
  console.log('Mobile 390px: large gauge, history chart, no horizontal overflow, mesh names/clients/ports PASS');
 } finally {await browser.close();}
})();
