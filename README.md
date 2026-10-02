[![Čeština](https://img.shields.io/badge/🇨🇿-Čeština-blue)](README.md)
[![English](https://img.shields.io/badge/🇬🇧-English-blue)](README_EN.md)

# Synology SRM Extended

Neoficiální integrace routerů Synology se systémem **SRM** do **Home Assistantu**. Nabízí přehled klientů, sledování vybraných zařízení, systémové údaje, informace o mesh síti a Wake-on-LAN přímo v rozhraní integrace.

Konfigurace probíhá přes uživatelské rozhraní. Pro běžné používání není potřeba YAML, SSH, vývojářské nástroje prohlížeče ani samostatná karta dashboardu.

**Aktuální verze: 0.1.12** · **Komunikace: lokální dotazování (local polling)** · **28 jazyků**

## Obsah

- [Funkce](#funkce)
- [Kompatibilita a požadavky](#kompatibilita-a-požadavky)
- [Instalace](#instalace)
- [Nastavení](#nastavení)
- [Používání](#používání)
- [Rychlosti a grafy](#rychlosti-a-grafy)
- [Aktualizace](#aktualizace)
- [Jazyky](#jazyky)
- [Diagnostika a řešení problémů](#diagnostika-a-řešení-problémů)
- [Soukromí a zabezpečení](#soukromí-a-zabezpečení)
- [Známá omezení](#známá-omezení)
- [Licence a značky](#Licence-a-značky)

## Funkce

### Přehled klientů

- Počty známých, online a offline klientů, online Wi-Fi a LAN klientů a online hostů, pokud je SRM rozlišuje.
- Tabulka klientů přímo v detailu příslušného senzoru.
- Název, IP, MAC, stav připojení a dostupné údaje o síti, SSID, pásmu, signálu a provozu.
- Vyhledávání podle názvu, IP nebo MAC.
- Řazení podle názvu, IP, MAC, stavu, sítě nebo signálu, vzestupně i sestupně.
- Filtrování online/offline a zobrazených/skrytých klientů.
- Uložení řazení a filtrů v HA pro konkrétního uživatele.
- Skrytí klienta z tabulky bez odstranění zařízení z routeru.
- Podrobnosti klienta po kliknutí na jeho název.

### Volitelné sledování zařízení

Samotné nalezení klienta **nevytvoří automaticky jeho entitu**. Seznam klientů lze používat bez sledování jednotlivých zařízení.

Pro vybrané klienty lze vytvořit:

- Entitu připojení pro zobrazení stavu a použití v automatizacích.
- `device_tracker` pro sledování přítomnosti a případné přiřazení k osobě v HA.

Klientské entity jsou seskupené pod zařízením **Integrovaní klienti** v rámci integrace. Identita klienta vychází z MAC adresy, nikoli z jeho názvu nebo IP.

### CPU, paměť a síť

- Celkové, uživatelské, systémové a ostatní využití CPU v procentech.
- Využití RAM a swapu podle SRM.
- Samostatný výpočet využití RAM bez cache a bufferů.
- Dostupný rozpis paměti: celkem, využito, volno, cache, buffery a rezervováno.
- Větší kruhové ukazatele a grafy CPU/RAM použitelné i na mobilu.
- Stav WAN IPv4 a IPv6 hlášený SRM.
- Počet síťových rozhraní.

### Mesh

Detail senzoru **Počet uzlů mesh** zobrazuje dostupné informace:

- Názvy uzlů spojené podle jejich ID ze systémových, ethernetových a klientských údajů.
- Model a dobu běhu uzlu.
- Online klienty přiřazené k uzlu.
- Porty a rychlosti jejich spojení hlášené SRM.

Rychlost spojení portu není aktuální objem přenášených dat. Použitá odpověď SRM neurčuje, který port nebo bezdrátové spojení propojuje jednotlivé uzly; integrace tuto informaci neodhaduje.

### Wake-on-LAN

V detailu klienta je tlačítko **Probudit přes LAN (z HA)**. Home Assistant odešle magic packet pro MAC adresu zvoleného zařízení.

Cílové zařízení musí WOL podporovat a mít jej povolený. Paket odchází z prostředí HA do místní sítě; průchod mezi oddělenými sítěmi či VLAN není zaručen. Potvrzení odeslání paketu není potvrzením probuzení zařízení.

## Kompatibilita a požadavky

| Součást | Stav |
| --- | --- |
| Home Assistant | Vývoj a ověřování zaměřené na Core 2026.9.3 |
| Router | Dosavadní funkčnost ověřována uživatelem na Synology RT6600ax |
| SRM | Referenční verze 1.3.2-9366 Update 2 |
| Další modely | RT2600ac a MR2200ac nejsou samostatně ověřené jako hlavní router integrace |
| Více routerů | Aktuálně jedna konfigurační položka routeru |
| Účet SRM | Přístup k API potřebným pro čtení údajů |
| Přihlášení s 2FA | Interaktivní tok dvoufázového přihlášení není implementován |

Home Assistant musí mít síťový přístup k adrese a portu SRM. Přihlášení a dotazy na router provádí **server HA**, nikoli počítač nebo telefon, na kterém máte otevřený prohlížeč.

Vlastní tabulky, detaily a WOL jsou dostupné správci HA. Integrace využívá rozhraní SRM, jehož dostupnost se může lišit podle modelu, firmwaru a oprávnění účtu.

## Instalace

Aktuálně je zdokumentovaná ruční instalace. Instalace přes HACS není v tomto projektu připravená.

1. Stáhněte [instalační ZIP nejnovější verze](https://github.com/Vachler/synology-srm-extended/releases/latest/download/synology_srm_extended.zip) a rozbalte jej.

2. Z rozbaleného ZIPu zkopírujte složku `synology_srm_extended` do složky `/config/custom_components/` v Home Assistantu.

   Výsledná cesta musí být:

   `/config/custom_components/synology_srm_extended/`

3. Ověřte výslednou strukturu:


   ```text
   /config/
   └── custom_components/
       └── synology_srm_extended/
           ├── manifest.json
           ├── __init__.py
           ├── frontend/
           ├── translations/
           ├── brand/
           └── ...
   ```

4. Restartujte **Home Assistant**.
5. Otevřete **Nastavení → Zařízení a služby → Přidat integraci**.
6. Vyhledejte **Synology SRM Extended** a vyplňte připojení.

### Připojení k SRM

| Pole | Popis |
| --- | --- |
| Host | IP adresa nebo hostname routeru, bez `http://`, `https://` a portu |
| Port | Port webového rozhraní SRM; běžně `8001` pro HTTPS a `8000` pro HTTP |
| HTTPS | Použití šifrovaného připojení; standardně zapnuté |
| Ověřování certifikátu | Standardně zapnuté |
| Uživatelské jméno a heslo | Přihlašovací údaje účtu SRM |

Použijte skutečný port nastavený ve vašem routeru. Pro HTTPS se běžně používá port `8001`, pro HTTP port `8000`. Pokud používáte vlastní nedůvěryhodný certifikát, lze jeho ověřování výslovně vypnout; vhodnější je důvěryhodný certifikát. Integrace sama nepřepíná z HTTPS na HTTP.

## Nastavení

Možnosti otevřete u integrace v **Nastavení → Zařízení a služby**.

| Možnost | Význam |
| --- | --- |
| Interval obnovy klientů | 5–3600 sekund, výchozí hodnota 30 sekund |
| Povolení vybraných entit připojení | Aktivuje entity pouze pro klienty vybrané v příslušném seznamu |
| Výběr klientských entit | Zařízení, jejichž připojení chcete sledovat samostatně |
| Výběr trackerů | Klienti, pro které se vytvoří `device_tracker`; prázdný výběr znamená žádné trackery |
| Vstupní jednotka provozu | Neznámá, B/s, KB/s, KiB/s nebo bit/s |
| Význam RX | Zda RX znamená download nebo upload z pohledu klienta; lze ponechat neznámý |
| Odstranit nevybrané klientské entity | Odstraní nevybrané entity této integrace včetně jejich nastavení v registru |

Výběry klientů jsou ve výchozím stavu prázdné. Počty a tabulky fungují nezávisle na vytváření klientských entit.

Odstranění nevybraných entit je volitelné a standardně vypnuté. Před jeho použitím zkontrolujte automatizace a osoby, které na tyto entity odkazují. Offline stav sám o sobě vybraného klienta neodstraní.

Systémové údaje, WAN a mesh se načítají samostatně každých **5 minut**. Zkrácení intervalu klientů nezrychlí obnovu systémových údajů a zvyšuje počet požadavků na router.

## Používání

- **Seznam klientů:** otevřete zařízení routeru a klikněte například na **Známí klienti v SRM**. Dostupný je také přes odkaz **Navštívit**.
- **Konkrétní skupina:** kliknutím na **Online klienti**, **Offline klienti**, **Online Wi-Fi klienti**, **Online LAN klienti** nebo **Online hosté** otevřete odpovídající výběr.
- **Detail klienta:** klikněte na jeho název v tabulce. Detail je dostupný také u vytvořené klientské entity.
- **WOL:** v detailu klienta zvolte **Probudit přes LAN (z HA)**.
- **CPU a RAM:** otevřete příslušný senzor na zařízení routeru.
- **Mesh:** otevřete senzor **Počet uzlů mesh**.

Tlačítko **Obnovit tabulku** načte poslední data integrace; nevyvolává dodatečný dotaz přímo na router.

## Rychlosti a grafy

### Provoz klientů

Výstupní jednotka je **KB/s**, kde **1 KB/s = 1000 B/s**. DL označuje download a UL upload z pohledu klienta.

Přepočet závisí na nastavené vstupní jednotce a významu RX. Dokud nejsou zvolené, integrace rychlost nepřevádí. Chybějící údaj se zobrazuje pomlčkou, nikoli nulou.

Graf provozu se tvoří během otevření detailu klienta a uchovává nejvýše **120 vzorků** v prohlížeči. Nenahrazuje dlouhodobý záznam provozu ani přesné měření v reálném čase.

U kabelových klientů nemusí SRM poskytovat použitelné rychlosti. Lokální kopírování mezi NAS a počítačem nemusí být zahrnuté do sledovaných hodnot. Integrace zobrazuje dostupná data SRM a nedopočítává chybějící provoz.

### CPU a RAM

Vlastní grafy uchovávají nejvýše **288 vzorků za 24 hodin**, s obnovou po 5 minutách. Data jsou v paměti HA a po restartu nebo znovunačtení integrace se začnou sbírat znovu. První bod se zobrazí po načtení dat; časový průběh přibývá s dalšími vzorky.

Tato paměťová historie je oddělená od standardní historie entit v HA. Seznamy klientů ani data vlastních grafů se nevkládají jako rozsáhlé atributy počítacích senzorů do Recorderu.

### Význam dalších údajů

- **Signál:** původní číselná hodnota SRM; bez ověření ji neoznačujeme jako dBm ani procenta.
- **Rychlost / maximum Wi-Fi spojení:** údaje o Wi-Fi lince, nikoli aktuální download ani maximum naměřeného stahování. Jednotka původního údaje není potvrzená.
- **Směrování Wi-Fi signálu (beamforming):** informace SRM o použití směrování vysílání k zařízení.
- **Název / typ zařízení nastaven ručně:** příznaky ručního nastavení v SRM.
- **Stav WAN:** stav hlášený routerem, nikoli nezávislý test dostupnosti internetu.

## Aktualizace

1. Zálohujte konfiguraci HA.
2. Přepište celou složku `custom_components/synology_srm_extended` novou verzí, včetně složek `frontend`, `translations` a `brand`.
3. Restartujte Home Assistant.
4. Obnovte stránku prohlížeče; pokud zůstává staré rozhraní, použijte `Ctrl+F5` nebo znovu otevřete aplikaci.

Existující integraci není nutné odstraňovat a znovu přidávat. Změnu adresy nebo přihlašovacích údajů řešte přes **Překonfigurovat**; při vyžádaném obnovení přihlášení použijte nabídnutý formulář.

### Změny ve verzi 0.1.12

- Podrobnější mesh s názvy z ethernetových údajů, klienty a porty.
- Větší ukazatele CPU/RAM a vlastní grafy historie.
- Graf provozu v detailu klienta.
- Srozumitelnější technické popisky.
- Odstranění dočasného 90sekundového měření a označení verze z tabulky.
- Odstranění volby rozšířeného diagnostického sběru a experimentálních dotazů; běžná diagnostika zůstává.

Verze 0.1.11 přidala 28 jazyků a odstranila velké seznamy klientů z atributů senzorů, které překračovaly limit Recorderu.

## Jazyky

Podporováno je 28 jazykových variant:

`cs`, `en`, `de`, `sk`, `pl`, `fr`, `es`, `hu`, `nl`, `pt`, `pt-BR`, `ro`, `uk`, `ru`, `tr`, `el`, `ja`, `ko`, `zh-Hans`, `zh-Hant`, `vi`, `th`, `id`, `ms`, `hi`, `ar`, `he`, `it`.

Vlastní rozhraní používá jazyk uživatele HA. Pro nepodporovaný jazyk se použije angličtina. Arabština a hebrejština podporují směr zprava doleva. Názvy klientů a SSID se nepřekládají.

Překlady jsou součástí integrace a za provozu nevyužívají online překladač. Cizojazyčné texty vznikly se strojovou podporou; jazykové opravy jsou vítané.

## Diagnostika a řešení problémů

Diagnostiku stáhnete z nabídky integrace v **Nastavení → Zařízení a služby**. Není potřeba zapínat rozšířený sběr.

| Problém | Co zkontrolovat |
| --- | --- |
| Integraci nelze najít | Umístění `manifest.json` a restart HA po instalaci |
| Nelze se připojit | Dostupnost routeru ze serveru HA, adresu, port a nastavení HTTPS |
| Chyba certifikátu | Důvěryhodnost certifikátu a použitý hostname |
| Chyba přihlášení | Účet, heslo, oprávnění a případný požadavek 2FA |
| Klienti jsou v tabulce, ale nemají entity | Entity se vytvářejí jen pro ručně vybrané klienty |
| Rychlost je pomlčka | Vstupní jednotku, význam RX a dostupnost údaje v SRM |
| WOL neprobudí zařízení | Podporu a povolení WOL, MAC adresu a síťovou cestu z HA |
| Graf zatím nemá průběh | Počkejte na další vzorky; paměťová historie se po restartu resetuje |
| Po aktualizaci vidíte staré rozhraní | Úplnost zkopírované složky, restart HA a obnovení prohlížeče |

Při hlášení chyby uveďte verzi integrace a HA, model routeru, verzi SRM, postup reprodukce a očekávaný výsledek. Přiložte relevantní log nebo diagnostiku. Před zveřejněním zkontrolujte také snímky obrazovky, které mohou obsahovat názvy zařízení, IP a MAC adresy.

## Soukromí a zabezpečení

- Komunikace s routerem probíhá lokálně. Integrace nevyžaduje cloudový účet ani QuickConnect.
- Přihlašovací údaje jsou uložené standardním mechanismem konfiguračních položek HA.
- Heslo se posílá v těle přihlašovacího požadavku, nikoli v URL.
- Diagnostika nepřebírá celé odpovědi routeru. Exportuje povolené údaje a anonymizované struktury bez hesel, relací, klientských jmen, MAC, IP a SSID.
- Vlastní přehledy a ruční odeslání WOL kontrolují oprávnění správce HA.
- Integrace nemění nastavení routeru. WOL je samostatná ručně vyvolaná akce z HA.

## Známá omezení

- Jde o neoficiální integraci, která není produktem společnosti Synology.
- Dostupnost údajů závisí na modelu, verzi SRM a oprávnění účtu.
- Restart routeru, traceroute, změny Wi-Fi, blokování klientů, Safe Access a Threat Prevention nejsou implementované.
- Aktualizace probíhá dotazováním v intervalech, nikoli okamžitými událostmi ze SRM.
- Offline telefon nemusí znamenat nepřítomnost člověka. Soukromá/náhodná MAC může vytvořit novou identitu klienta.
- Při výpadku komunikace se používá stav nedostupnosti; výpadek se nepovažuje za odpojení všech klientů.
- Vlastní detaily využívají frontend HA; kompatibilitu s jinými verzemi je nutné ověřit.

## Licence a značky

Projekt je poskytován zdarma pouze pro osobní a nekomerční použití. Podrobné podmínky jsou uvedeny v souboru [LICENSE](LICENSE).

Synology a související loga jsou značkami jejich vlastníka. Použití názvu a loga označuje kompatibilitu a neznamená oficiální podporu nebo spojení se společností Synology.
