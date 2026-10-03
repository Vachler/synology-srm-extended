<a href="README.md">
  <img src="https://img.shields.io/badge/🇬🇧%20English-a3e635?style=for-the-badge" height="34">
</a>
<a href="README_CZ.md">
  <img src="https://img.shields.io/badge/🇨🇿%20Čeština-2563eb?style=for-the-badge" height="34">
</a>

# Synology SRM Extended

Synology SRM Extended is an unofficial Home Assistant integration for Synology SRM routers, including the RT6600ax. It provides client monitoring, device tracking, mesh information, CPU/RAM statistics, network status and Wake-on-LAN.

Configuration is handled through the user interface. For normal use, YAML, SSH, browser developer tools, or a separate dashboard card are not required.

**Current version: 0.1.12** · **Communication: local polling** · **28 languages**

## Contents

- [Features](#features)
- [Compatibility and requirements](#compatibility-and-requirements)
- [Installation](#installation)
- [Settings](#settings)
- [Usage](#usage)
- [Speeds and graphs](#speeds-and-graphs)
- [Updates](#updates)
- [Languages](#languages)
- [Diagnostics and troubleshooting](#diagnostics-and-troubleshooting)
- [Privacy and security](#privacy-and-security)
- [Known limitations](#known-limitations)
- [License and trademarks](#license-and-trademarks)

---

<a id="features"></a>
## ⚙️ Features

### Client overview

- Counts of known, online, and offline clients, online Wi-Fi and LAN clients, and online guest clients where SRM distinguishes them.
- Client table directly in the details of the corresponding sensor.
- Name, IP, MAC, connection status, and available information about network, SSID, band, signal, and traffic.
- Search by name, IP, or MAC.
- Sorting by name, IP, MAC, status, network, or signal, in ascending or descending order.
- Filtering by online/offline and visible/hidden clients.
- Sorting and filter settings are stored in HA for each user.
- Hide a client from the table without removing the device from the router.
- Client details are available by clicking the client name.

### Optional device tracking

Simply discovering a client **does not automatically create an entity for it**. The client list can be used without tracking individual devices.

For selected clients, the integration can create:

- A connection entity for displaying status and use in automations.
- A `device_tracker` for presence tracking and optional assignment to a person in HA.

Client entities are grouped under the **Integrated Clients** device within the integration. Client identity is based on the MAC address, not the client name or IP address.

### CPU, memory, and network

- Total, user, system, and other CPU usage in percent.
- RAM and swap usage as reported by SRM.
- Separate calculation of RAM usage excluding cache and buffers.
- Available memory breakdown: total, used, free, cache, buffers, and reserved.
- Larger circular CPU/RAM gauges and graphs suitable for mobile devices.
- WAN IPv4 and IPv6 status reported by SRM.
- Number of network interfaces.

### Mesh

The **Mesh node count** sensor details show available information including:

- Node names matched by their IDs from system, Ethernet, and client data.
- Node model and uptime.
- Online clients assigned to each node.
- Ports and their link speeds as reported by SRM.

Port link speed is not the current amount of transferred data. The SRM response used by the integration does not identify which port or wireless link connects individual nodes; the integration does not attempt to infer this information.

### Wake-on-LAN

The client detail view includes a **Wake via LAN (from HA)** button. Home Assistant sends a magic packet to the selected device's MAC address.

The target device must support WOL and have it enabled. The packet is sent from the HA environment to the local network; delivery across separated networks or VLANs is not guaranteed. Confirmation that the packet was sent does not confirm that the device actually woke up.

---

<a id="compatibility-and-requirements"></a>
## 🧩 Compatibility and requirements

| Component | Status |
| --- | --- |
| Home Assistant | Development and testing focused on Core 2026.9.3 |
| Router | Current functionality tested by the user on Synology RT6600ax |
| SRM | Reference version 1.3.2-9366 Update 2 |
| Other models | RT2600ac and MR2200ac have not been separately verified as the primary router for this integration |
| Multiple routers | Currently one router configuration entry |
| SRM account | Access to the APIs required for reading data |
| 2FA login | Interactive two-factor authentication flow is not implemented |

Home Assistant must have network access to the SRM address and port. Login and router requests are performed by the **HA server**, not by the computer or phone on which the browser is open.

Custom tables, details, and WOL are available to HA administrators. The integration uses SRM interfaces whose availability may vary depending on router model, firmware version, and account permissions.

---

<a id="installation"></a>
## 📦 Installation

Manual installation is currently documented. Installation through HACS is not yet prepared for this project.

1. Download the [installation ZIP for the latest release](https://github.com/Vachler/synology-srm-extended/releases/latest/download/synology_srm_extended.zip) and extract it.

2. Copy the `synology_srm_extended` folder from the extracted ZIP into `/config/custom_components/` in Home Assistant.

   The resulting path must be:

   `/config/custom_components/synology_srm_extended/`

3. Verify the resulting structure:

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

4. Restart **Home Assistant**.
5. Open **Settings → Devices & services → Add integration**.
6. Search for **Synology SRM Extended** and enter the connection details.

### Connecting to SRM

| Field | Description |
| --- | --- |
| Host | Router IP address or hostname, without `http://`, `https://`, or a port |
| Port | SRM web interface port; commonly `8001` for HTTPS and `8000` for HTTP |
| HTTPS | Use an encrypted connection; enabled by default |
| Certificate verification | Enabled by default |
| Username and password | SRM account credentials |

Use the actual port configured on your router. Port `8001` is commonly used for HTTPS and port `8000` for HTTP. If you use an untrusted custom certificate, certificate verification can be explicitly disabled; using a trusted certificate is preferable. The integration does not automatically switch from HTTPS to HTTP.

---

<a id="settings"></a>
## 🔧 Settings

Open the integration options under **Settings → Devices & services**.

| Option | Meaning |
| --- | --- |
| Client refresh interval | 5–3600 seconds, default 30 seconds |
| Enable selected connection entities | Activates entities only for clients selected in the corresponding list |
| Client entity selection | Devices whose connection status should be tracked individually |
| Tracker selection | Clients for which a `device_tracker` is created; an empty selection means no trackers |
| Traffic input unit | Unknown, B/s, KB/s, KiB/s, or bit/s |
| RX meaning | Whether RX means download or upload from the client perspective; it may be left unknown |
| Remove unselected client entities | Removes unselected entities created by this integration, including their registry settings |

Client selections are empty by default. Counts and tables work independently of individual client entity creation.

Removing unselected entities is optional and disabled by default. Before enabling it, check automations and persons that reference those entities. An offline state alone does not remove a selected client.

System data, WAN information, and mesh data are loaded separately every **5 minutes**. Reducing the client refresh interval does not speed up system data updates and increases the number of requests sent to the router.

---

<a id="usage"></a>
## 🖱️ Usage

- **Client list:** open the router device and click, for example, **Known clients in SRM**. It is also available through the **Visit** link.
- **Specific group:** click **Online clients**, **Offline clients**, **Online Wi-Fi clients**, **Online LAN clients**, or **Online guests** to open the corresponding selection.
- **Client details:** click the client name in the table. Details are also available from a created client entity.
- **WOL:** in the client details, select **Wake via LAN (from HA)**.
- **CPU and RAM:** open the corresponding sensor on the router device.
- **Mesh:** open the **Mesh node count** sensor.

The **Refresh table** button loads the latest data already available to the integration; it does not trigger an additional direct request to the router.

---

<a id="speeds-and-graphs"></a>
## 📈 Speeds and graphs

### Client traffic

The output unit is **KB/s**, where **1 KB/s = 1000 B/s**. DL means download and UL means upload from the client perspective.

Conversion depends on the selected input unit and the meaning of RX. Until both are configured, the integration does not convert traffic speeds. Missing values are displayed as a dash rather than zero.

The traffic graph is generated while the client details are open and stores up to **120 samples** in the browser. It is not intended as long-term traffic history or precise real-time measurement.

For wired clients, SRM may not provide usable traffic speed data. Local copying between a NAS and computer may not be included in the reported values. The integration displays available SRM data and does not calculate missing traffic information.

### CPU and RAM

Custom graphs store up to **288 samples over 24 hours**, refreshed every 5 minutes. The data is held in HA memory and begins collecting again after a restart or integration reload. The first point appears after data is loaded, and the timeline grows as additional samples are collected.

This in-memory history is separate from the standard HA entity history. Client lists and custom graph data are not stored as large attributes of counting sensors in Recorder.

### Meaning of additional values

- **Signal:** original numeric value reported by SRM; without verification it is not labeled as dBm or percent.
- **Speed / maximum Wi-Fi link:** Wi-Fi link information, not current download speed or maximum measured download throughput. The unit of the original value has not been confirmed.
- **Wi-Fi signal beamforming:** SRM information about directional transmission being used toward the device.
- **Name / device type set manually:** indicators that these values were manually configured in SRM.
- **WAN status:** status reported by the router, not an independent Internet availability test.

---

<a id="updates"></a>
## 🔄 Updates

1. Back up your HA configuration.
2. Replace the entire `custom_components/synology_srm_extended` folder with the new version, including the `frontend`, `translations`, and `brand` folders.
3. Restart Home Assistant.
4. Refresh the browser page; if the old interface remains visible, use `Ctrl+F5` or reopen the application.

The existing integration does not need to be removed and added again. Address or credential changes should be handled through **Reconfigure**; if login renewal is requested, use the provided form.

### Changes in version 0.1.12

- More detailed mesh information with names from Ethernet data, clients, and ports.
- Larger CPU/RAM gauges and custom history graphs.
- Traffic graph in the client detail view.
- Clearer technical labels.
- Removal of the temporary 90-second measurement and version label from the table.
- Removal of the extended diagnostic collection option and experimental queries; standard diagnostics remain available.

Version 0.1.11 added 28 languages and removed large client lists from sensor attributes that exceeded the Recorder limit.

---

<a id="languages"></a>
## 🌍 Languages

28 language variants are supported:

`cs`, `en`, `de`, `sk`, `pl`, `fr`, `es`, `hu`, `nl`, `pt`, `pt-BR`, `ro`, `uk`, `ru`, `tr`, `el`, `ja`, `ko`, `zh-Hans`, `zh-Hant`, `vi`, `th`, `id`, `ms`, `hi`, `ar`, `he`, `it`.

The custom interface uses the language of the HA user. English is used as a fallback for unsupported languages. Arabic and Hebrew support right-to-left layout. Client names and SSIDs are not translated.

Translations are included with the integration and do not use an online translation service during operation. Non-English texts were created with machine assistance; language corrections are welcome.

---

<a id="diagnostics-and-troubleshooting"></a>
## 🩺 Diagnostics and troubleshooting

Diagnostics can be downloaded from the integration menu under **Settings → Devices & services**. Extended diagnostic collection does not need to be enabled.

| Problem | What to check |
| --- | --- |
| Integration cannot be found | Location of `manifest.json` and whether HA was restarted after installation |
| Cannot connect | Router accessibility from the HA server, address, port, and HTTPS settings |
| Certificate error | Certificate trust and the hostname being used |
| Login error | Account, password, permissions, and any 2FA requirement |
| Clients appear in the table but have no entities | Entities are created only for manually selected clients |
| Speed is shown as a dash | Input unit, RX meaning, and availability of the value in SRM |
| WOL does not wake the device | WOL support and configuration, MAC address, and network path from HA |
| Graph does not yet show a timeline | Wait for additional samples; in-memory history resets after restart |
| Old interface remains after an update | Complete folder replacement, HA restart, and browser refresh |

When reporting an issue, include the integration version, HA version, router model, SRM version, reproduction steps, and the expected result. Attach a relevant log or diagnostic file. Before publishing screenshots, also check whether they contain device names, IP addresses, or MAC addresses.

---

<a id="privacy-and-security"></a>
## 🔒 Privacy and security

- Communication with the router is local. The integration does not require a cloud account or QuickConnect.
- Login credentials are stored using the standard HA configuration entry mechanism.
- The password is sent in the body of the login request, not in the URL.
- Diagnostics do not include full router responses. They export permitted data and anonymized structures without passwords, sessions, client names, MAC addresses, IP addresses, or SSIDs.
- Custom views and manual WOL actions verify HA administrator permissions.
- The integration does not change router settings. WOL is a separate action triggered manually from HA.

---

<a id="known-limitations"></a>
## ⚠️ Known limitations

- This is an unofficial integration and is not a Synology product.
- Data availability depends on the router model, SRM version, and account permissions.
- Router restart, traceroute, Wi-Fi changes, client blocking, Safe Access, and Threat Prevention are not implemented.
- Updates are performed by polling at intervals rather than by immediate SRM events.
- An offline phone does not necessarily mean that a person is absent. A private/random MAC address may create a new client identity.
- If communication fails, an unavailable state is used; the outage is not treated as all clients being disconnected.
- Custom detail views use the HA frontend; compatibility with other versions must be verified.

---

<a id="license-and-trademarks"></a>
## 📜 License and trademarks

The project is provided free of charge for personal and non-commercial use only. Full terms are available in the [LICENSE](LICENSE) file.

Synology and related logos are trademarks of their respective owners. Use of the name and logo indicates compatibility only and does not imply official support or affiliation with Synology.

---

![Visits](https://komarev.com/ghpvc/?username=Vachler-synology-srm-extended&color=green&style=square&label=VISITS)
