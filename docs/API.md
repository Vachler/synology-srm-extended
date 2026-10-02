# Hranice ověření API

## Podklady

- Uživatel potvrdil `SYNO.Core.Network.NSM.Device`, v5, `get` a seznam klientských polí
  na RT6600ax / SRM 1.3.2-9366 Update 2. Úplný JSON zatím nepředal.
- Seznam ostatních čtecích specifikací pochází z uživatelem zachyceného compound požadavku.
- Obálka `success/data` a seznam `data.devices`, přihlášení `SYNO.API.Auth` v2 `Login`
  a katalog `SYNO.API.Info` pocházejí také z veřejného SRM klienta:
  https://github.com/aerialls/synology-srm
  https://raw.githubusercontent.com/aerialls/synology-srm/master/synology_srm/http.py
  https://raw.githubusercontent.com/aerialls/synology-srm/master/synology_srm/api/core.py
  https://raw.githubusercontent.com/aerialls/synology-srm/master/synology_srm/api/mesh.py
- Veřejný klient používá GET login; zde je bezpečnější POST, který dosud čeká na ověření
  u uživatele. Při odmítnutí nepřecházíme automaticky na GET s heslem v URL.
- Pole `ipv4/ipv6.conn_status`, `ip`, `ifname`, `pppoe` byla publikována v přímém záznamu
  SRM na jiném routeru. Parser je strukturálně podmíněný, hodnotu stavu nepřekládá na
  domnělou dostupnost internetu a kompatibilitu na cílovém firmwaru neslibuje:
  https://community.synology.com/enu/forum/2/post/158175

Všechna provozní API jsou interní/reverzně zjištěná, bez záruky stabilního veřejného
kontraktu Synology. Nepřebíráme jednotky ani reboot API z DSM.

## Chování

`srm/specs.py` je jediný seznam povolených datových požadavků. Volání lze vybrat pouze
klíčem, nikoli doplněním metody nebo libovolných parametrů. Neexistuje obecná HA akce
pro volání API. Výjimkami mimo datový seznam jsou pouze přihlášení, odhlášení a čtení katalogu.

Katalog neslouží k automatickému přechodu na jinou verzi ani ke zkoušení zápisových metod.
Cesta z katalogu nesmí změnit host nebo opustit `/webapi/`. HTTP přesměrování je zakázáno,
aby nemohlo přeposlat přihlašovací údaje. Proxy z prostředí se nepoužívají.

Změna hesla nebo IP se provádí přes reauth/reconfigure se zachováním config entry.
Všechny API chyby obsahují nanejvýš kód, nikdy odpověď serveru. Odpovědi 106/107 mohou
způsobit jednu obnovu relace a opakování čtení. Ostatní chyby se neopakují naslepo.

## Co je třeba ověřit na routeru

1. Přijetí POST přihlášení a předání relace v těle požadavku jako `_sid`.
2. Přesná klientská obálka `data.devices` a datové typy příznaků.
3. Návrat zařízení po odpojení, offline záznam, dočasný výpadek SRM.
4. Struktura CPU/RAM, rozhraní, provozu, Wi-Fi a mesh v očištěné diagnostice.
5. Jednotky metrik proti běžnému zobrazení SRM; zatím se nepředpokládají.
6. Funkce config flow, options flow a načtení platform v HA Core 2026.9.3.

Testovací data v repozitáři jsou **syntetická**, nikoli vydávaná za zachycené odpovědi
tohoto routeru. Provozní metriky čekají na ověření skutečné odpovědi i ve verzi 0.1.1.


## Diagnostika 0.1.5

Zachycená diagnostika uživatele z verze 0.1.4 potvrdila úspěšné čtení všech 22
specifikací. Monitoring nyní publikuje původní položky CPU user_load/system_load/
other_load a memory real_usage/swap_usage bez předpokládané jednotky. Dále počítá
uzly system_info.nodes a pojmenovaná rozhraní utilization.network mimo `total`.
Neodvozuje procenta CPU ze součtu ani nepřevádí velikosti paměti podle DSM.

Rozšířený export je stále založený na pevném seznamu povolených technických klíčů,
nikoli na pravidle „všechny názvy vypadající jako identifikátor“. To brání úniku
uživatelských názvů, tokenů a adres použitých jako klíče objektu.
