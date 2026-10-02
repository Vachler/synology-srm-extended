const assert=require('node:assert/strict');
const fs=require('node:fs');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'C:/Users/Milli/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 try {
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.addScriptTag({path:'custom_components/synology_srm_extended/frontend/clients.js'});
  const dir='custom_components/synology_srm_extended/frontend/locales';
  for(const file of fs.readdirSync(dir).filter(f=>f.endsWith('.json'))) {
   const language=file.slice(0,-5);const labels=JSON.parse(fs.readFileSync(`${dir}/${file}`,'utf8'));
   await page.evaluate(({language})=>{
    document.body.replaceChildren();
    const el=document.createElement('synology-srm-clients-v0112');
    el.panel={config:{entry_id:'test'}};
    el.hass={language,callWS:async r=>({available:true,clients:[{name:'Název',mac:'02:11:22:33:44:55',online:true,details:{wifi_ssid:'Moje síť'}}],poll_interval:5})};
    document.body.append(el);
   },{language});
   const el=page.locator('synology-srm-clients-v0112');
   await el.getByRole('button',{name:'Název',exact:true}).waitFor();
   assert.equal(await el.locator('#refresh').innerText(),labels['Obnovit tabulku'],language);
   await el.getByRole('button',{name:'Název',exact:true}).click();
   assert.equal(await el.locator('#wol').innerText(),labels['Probudit přes LAN (z HA)'],language);
   assert.equal(await el.getAttribute('dir'),['ar','he'].includes(language)?'rtl':'ltr',language);
   assert((await el.locator('#details-values').innerText()).includes('Moje síť'),language+' user SSID preserved');
  }
  // Switch language on an existing node without resetting controls.
  await page.evaluate(()=>{const e=document.querySelector('synology-srm-clients-v0112'); e.shadowRoot.querySelector('#sort').value='signal';e.hass={...e._hass,language:'en'};});
  assert.equal(await page.locator('synology-srm-clients-v0112 #refresh').innerText(),'Refresh the table');
  assert.equal(await page.locator('synology-srm-clients-v0112 #sort').inputValue(),'signal');
  await page.evaluate(()=>{const e=document.querySelector('synology-srm-clients-v0112');e.hass={...e._hass,language:'unsupported'};});
  assert.equal(await page.locator('synology-srm-clients-v0112 #wol').innerText(),'Wake on LAN (from HA)');
  assert.deepEqual(errors,[]);
  console.log('28 locales: labels, WOL, RTL, user text, language switch and fallback PASS');
 } finally {await browser.close();}
})();
