// Localization is entirely local. Only integration-owned labels are translated.
class SrmLocalizedElement extends HTMLElement {
  t(source, params = {}) {
    const language = this.language || 'cs';
    let text = SRM_TRANSLATIONS[language]?.[source] ?? SRM_TRANSLATIONS.en?.[source] ?? source;
    // Dynamic backend mesh labels retain identifiers and model names verbatim.
    if (text === source && /^Uzel \d+$/.test(source)) return this.t('Uzel {p0}', {p0: source.slice(5)});
    const missing = /^Název není dostupný \(model (.*)\)$/.exec(source);
    if (text === source && missing) return this.t('Název není dostupný (model {p0})', {p0:missing[1]});
    return text.replace(/\{(\w+)\}/g, (match, key) => Object.hasOwn(params, key) ? String(params[key]) : match);
  }
  captureStaticText() {
    this.staticText = [];
    if (!document.createTreeWalker) return;
    const walker = document.createTreeWalker(this.shadowRoot, 4);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      if (node.parentElement?.tagName === 'STYLE') continue;
      const source = node.textContent.trim();
      if (source && Object.hasOwn(SRM_TRANSLATIONS.cs, source)) this.staticText.push({node,source});
    }
    this.staticAttrs = [];
    for (const node of this.shadowRoot.querySelectorAll('[title],[placeholder],[aria-label]')) {
      for (const attr of ['title','placeholder','aria-label']) {
        const source=node.getAttribute(attr);
        if(source && Object.hasOwn(SRM_TRANSLATIONS.cs,source)) this.staticAttrs.push({node,attr,source});
      }
    }
  }
  updateLanguage(hass) {
    const requested = (hass?.locale?.language || hass?.language || 'cs').replaceAll('_','-').toLowerCase();
    const alias = {'zh-cn':'zh-Hans','zh-sg':'zh-Hans','zh-tw':'zh-Hant','zh-hk':'zh-Hant','zh-hans':'zh-Hans','zh-hant':'zh-Hant','pt-br':'pt-BR','iw':'he'};
    const exact=Object.keys(SRM_TRANSLATIONS).find(key=>key.toLowerCase()===requested);
    const resolved = alias[requested] || exact || requested.split('-')[0];
    const language = Object.hasOwn(SRM_TRANSLATIONS,resolved) ? resolved : 'en';
    const changed = this.language !== language;
    this.language=language;
    // Never add attributes in a custom-element constructor.
    if(this.shadowRoot?.host?.isConnected) this.shadowRoot.host.setAttribute('dir',['ar','he'].includes(language)?'rtl':'ltr');
    if(!changed) return false;
    for(const item of this.staticText || []) item.node.textContent=this.t(item.source);
    for(const item of this.staticAttrs || []) item.node.setAttribute(item.attr,this.t(item.source));
    const direction = this.shadowRoot?.querySelector("#direction");
    if(direction) direction.textContent=this.t(this.descending ? "Sestupně ↓" : "Vzestupně ↑");
    if(this.wolButton) this.wolButton.textContent=this.t('Probudit přes LAN (z HA)');
    return true;
  }
}
