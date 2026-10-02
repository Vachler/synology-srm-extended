// Test zobrazení bez běžícího Home Assistantu; minimální DOM.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor() { this.style = {setProperty(name,value) { this[name]=value; }}; this.children = []; this.value = ''; this.textContent = ''; }
  append(child) { this.children.push(child); }
  replaceChildren(...children) { this.children = children; }
  addEventListener() {}
  showModal() { this.open = true; }
  close() { this.open = false; }
}
const elements = new Map();
let Panel;
const classes = new Map();
const storage = new Map();
const context = {
  localStorage:{ getItem:key => storage.get(key) ?? null, setItem:(key,value) => storage.set(key,value) },
  HTMLElement: class {
    constructor() { this.style = {}; }
    attachShadow() {
      this.shadowRoot = { append() {}, querySelector: selector => {
        if (!elements.has(selector)) elements.set(selector, new Element());
        return elements.get(selector);
      }};
    }
  },
  document: { createElement: () => new Element() },
  customElements: { get: name => classes.get(name), define: (name, cls) => { classes.set(name,cls); if (name === "synology-srm-clients-v0112") Panel = cls; } },
  setInterval, clearInterval,
};
vm.runInNewContext(fs.readFileSync('custom_components/synology_srm_extended/frontend/clients.js', 'utf8'), context);
(async () => {
  const panel = new Panel();
  panel.panel = { config: { entry_id: 'router' } };
  panel.hass = { callWS: async request => {
    assert.equal(request.entry_id, 'router');
    return { available: false, clients: [
      { name: '<img src=x onerror=alert(1)>', ip: '192.168.1.2', mac: '02:11:22:33:44:55', online: true },
      { name: 'Telefon', ip: null, mac: '02:11:22:33:44:56', online: false },
    ]};
  }};
  await panel.load();
  assert.equal(elements.get('tbody').children.length, 2);
  assert.equal(elements.get('tbody').children[0].children[0].children[0].textContent, '<img src=x onerror=alert(1)>');
  assert.equal(elements.get('tbody').children[1].children[1].textContent, '—');
  assert.match(elements.get('#status').textContent, /zastaralé/);
  elements.get('#search').value = 'telefon';
  panel.renderRows();
  assert.equal(elements.get('tbody').children.length, 1);
  elements.get('#search').value = '';
  panel.traffic = {source_unit:'B/s', rx_direction:'download'};
  const trafficRow = {online:true, details:{transferRXRate:12000, transferTXRate:3000}};
  assert.equal(panel.speed(trafficRow,'download'), '12');
  assert.equal(panel.speed(trafficRow,'upload'), '3');
  panel.traffic.rx_direction = 'upload';
  assert.equal(panel.speed(trafficRow,'download'), '3');
  panel.traffic.source_unit = 'unknown';
  assert.equal(panel.speed(trafficRow,'download'), '—');
  panel.rows = [
    {name:'Zeta',mac:'02:11:22:33:44:55',ip:'192.168.1.2',online:true},
    {name:'Alfa',mac:'02:11:22:33:44:56',ip:'192.168.1.10',online:false},
  ];
  panel.renderRows();
  assert.equal(elements.get('tbody').children[0].children[0].children[0].textContent, 'Alfa');
  elements.get('#sort').value = 'state'; panel.renderRows();
  assert.equal(elements.get('tbody').children[0].children[0].children[0].textContent, 'Zeta');
  elements.get('#filter').value = 'offline'; panel.renderRows();
  assert.equal(elements.get('tbody').children.length,1);
  elements.get('#filter').value = 'all';
  panel._hass.callWS = async request => ({hidden:request.hidden});
  await panel.setHidden(panel.rows[0],true,new Element());
  assert.equal(elements.get('tbody').children.length,1);
  elements.get('#visibility').value = 'hidden'; panel.renderRows();
  assert.equal(elements.get('tbody').children[0].children[0].children[0].textContent, 'Zeta');
  panel.openDetails(panel.rows[0]);
  assert.equal(elements.get('#details').open,true);
  assert.equal(elements.get('#details-title').textContent,'Zeta');
  await panel.setHidden(panel.rows[0],false,new Element());
  assert.equal(elements.get('tbody').children.length,0);
  panel._hass.callWS = async () => { throw new Error('offline'); };
  await panel.load();
  assert.match(elements.get('#status').textContent, /nepodařilo/);
  assert.equal(elements.get('#refresh').disabled, false);
  const Info = classes.get('synology-srm-clients-info-v0112');
  const info = new Info();
  info.stateObj = { attributes: { srm_entry_id:'from-sensor' } };
  assert.equal(info._panel.config.entry_id, 'from-sensor');
  assert.equal(classes.has('synology-srm-clients-card'), false);
  const saved = {sort:'signal',filter:'online',visibility:'visible',descending:true};
  const reopened = new Panel();
  reopened.panel = {config:{entry_id:'router'}};
  // HA dodá identitu na serveru; frontend nepotřebuje hass.user ani localStorage.
  reopened.hass = {callWS:async request => {
    if(request.type.endsWith('/view')) { Object.assign(saved,request.view); return {saved:true}; }
    return {clients:[],available:true,view:saved,poll_interval:5};
  }};
  await reopened.load();
  assert.equal(elements.get('#sort').value,'signal');
  assert.equal(elements.get('#filter').value,'online');
  assert.equal(reopened.descending,true);
  assert.equal(reopened.pollSeconds,5);
  elements.get('#sort').value='name';
  await reopened.saveView();
  assert.equal(saved.sort,'name');
  assert.match(elements.get('#view-status').textContent,/uloženo/);
  assert.equal(reopened.networkLabel({details:{connection:'ethernet',network:'lbr0'}}),'Ethernet (kabel)');
  assert.equal(reopened.networkLabel({details:{connection:'wifi',network:'lbr0',wifi_ssid:'Moje Wi-Fi'}}),'Moje Wi-Fi');
  reopened.traffic={source_unit:'B/s',rx_direction:'download'};
  assert.equal(reopened.speed({online:true,details:{connection:'ethernet'}},'download'),'—');
  assert.equal(reopened.speed({online:true,details:{connection:'ethernet',transferRXRate:5000}},'download'),'5');
  assert.equal(reopened.networkLabel({details:{network:'lbr0'}}), 'Místní síť (LAN)');
  assert.equal(reopened.networkLabel({details:{connection:'Ethernet',network:'lbr0'}}), 'Ethernet (kabel)');
  const Resource = classes.get('synology-srm-resource-info-v0112');
  const resource = new Resource();
  resource.stateObj = {state:'63.8',attributes:{resource_kind:'ram_calculated'}};
  assert.equal(elements.get('.ring').style['--used'], '63.8%');
  assert.match(elements.get('.inside').textContent, /63,8 %/);
  resource.stateObj = {state:'unavailable',attributes:{resource_kind:'ram_calculated'}};
  assert.equal(elements.get('.inside').textContent, '—');
  const Detail = classes.get('synology-srm-client-info-v0112');
  const detail = new Detail();
  detail.stateObj = {attributes:{srm_entry_id:'router',srm_client_mac:'02:11:22:33:44:55'}};
  detail.hass = {callWS:async () => ({available:true, clients:[{name:'Test',mac:'02:11:22:33:44:55',online:true,details:{wifi_ssid:'Test WiFi',transferRXRate:12000}}],traffic_settings:{source_unit:'B/s',rx_direction:'download'}})};
  await detail.load();
  assert.equal(detail.status.textContent,'Online');
  assert(detail.values.children.some(child => child.textContent === 'Test WiFi'));
  assert(detail.values.children.some(child => child.textContent === '12'));
  console.log('Tabulka: načtení, bezpečný text, chybějící IP, filtr a výpadek ověřeny.');
})();
