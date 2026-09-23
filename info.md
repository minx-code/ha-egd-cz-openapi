# EG.D OpenAPI for Home Assistant

![GitHub Actions Workflow Status](https://img.shields.io/github/actions/workflow/status/minx-code/ha-egd-cz-openapi/test.yaml?label=Tests)
![HACS Validation](https://img.shields.io/badge/HACS-Custom-orange.svg)

*(Česká verze níže / Czech version below)*

## 🇬🇧 English
This native community HACS integration for Home Assistant allows you to download 15-minute profile data for consumption and production from the Czech distributor EG.D (Distribuce24). Data is imported directly into Home Assistant's historical statistics and can be used in the Energy Dashboard.

### Features
- Support for measurement types A, B, and C1.
- Automatic synchronization of historical data (with unlimited history option).
- Reconfigure Flow (update credentials without deleting the integration).
- Native Home Assistant Services (`egd_cz_energy.fetch_history`) for manual data fetching (supports selecting specific devices and start dates).
- Diagnostics Support for safe and anonymized bug reporting.
- Options Flow for changing update time and **data profiles** (e.g. `ICQ2`, `ICC1` - automatically converting `kW` to `kWh`) via UI.
- Repairs API support to notify about expired credentials.
- Diagnostic Sensors to monitor API connection and **detailed synchronization status**.
- Perfect 15-minute resolution integration with the HA Energy Dashboard.
- Native Service `egd_cz_energy.remove_statistics` to completely wipe downloaded data and reset the sync checkpoint.

### Prerequisites
You need a `client_id` and `client_secret`, which you can generate on the [Distribuce24 portal](https://portal.distribuce24.cz) in the section **Account Management -> REMOTE ACCESS - OPENAPI**. You will also need the **EAN** of your supply point.

---

## 🇨🇿 Čeština
Tato nativní komunitní HACS integrace pro Home Assistant umožňuje stahovat čtvrthodinová profilová data spotřeby a přetoku od distributora EG.D (Distribuce24). Data se importují přímo do historických statistik Home Assistanta a lze je využít v Energy Dashboardu.

### Funkce
- Podpora typů měření A, B a C1.
- Automatická synchronizace historických dat (s možností neomezené historie).
- **Rekonfigurace hesla** (Reconfigure) bez nutnosti mazat integraci a senzory.
- Nativní HA Služba (`egd_cz_energy.fetch_history`) pro manuální stahování historie (podporuje volbu konkrétního elektroměru a data).
- Podpora **Diagnostiky** pro bezpečné stažení anonymizovaného stavu aplikace při chybách.
- **Možnosti (Options Flow)** pro jednoduchou změnu hodiny stahování dat a **výběr datového profilu** (např. `ICQ2`, `ICC1` – s automatickým přepočtem `kW` na `kWh`) přes uživatelské rozhraní.
- **Servisní tikety (Repairs API)** pro okamžité automatické upozornění při vypršení hesla k API.
- **Senzory stavu připojení a synchronizace** (např. `ok`, `waiting_for_data`), na které si můžete navázat automatizace a alerty.
- Dokonalé propojení s panelem Energie (Energy Dashboard) s **přesným 15minutovým rozlišením**.
- Nativní Služba `egd_cz_energy.remove_statistics` pro bezpečné promazání stažených dat z databáze a resetování kontrolního bodu.

### Požadavky
K získání dat potřebujete `client_id` a `client_secret`, které vygenerujete na portálu [Distribuce24](https://portal.distribuce24.cz) v sekci **Správa účtů -> VZDÁLENÝ PŘÍSTUP – OPENAPI**. Při přidávání integrace budete dále potřebovat **EAN** (18 číslic) vašeho odběrného místa.
