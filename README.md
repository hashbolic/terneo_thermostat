# Terneo Thermostat
[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

Terneo Thermostat component for Home Assistant

This fork includes recovery fixes for intermittently unavailable thermostats.
Devices remain registered when offline at startup and recover on a successful
poll. Invalid responses mark the entity unavailable; requests to each device
are serialized. Existing YAML configuration and entity IDs are preserved.

## Install or update with HACS

[Open this repository in HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=hashbolic&repository=terneo_thermostat&category=integration)

1. Open **HACS → menu → Custom repositories**.
2. Add `https://github.com/hashbolic/terneo_thermostat` with type **Integration**.
3. Open **Terneo Thermostat** and download the latest release (`1.0.2` or later).
4. Keep your existing YAML configuration, then restart Home Assistant.

If you already installed this fork, update it from its existing HACS entry.
If you installed a different Terneo repository, back up `custom_components/terneo`
and switch the HACS repository to this fork. Manage only one repository for the
`terneo` domain. HACS updates from another fork can overwrite these fixes.

This is a HACS **custom repository**; it is not listed in HACS's default catalog.

## Device requirements

required device firmware version 2.3

https://terneo-api.readthedocs.io/ru/latest/

>In firmware version 2.3, the ability to control the local network by default blocked for security reasons.

block removing - https://terneo-api.readthedocs.io/ru/latest/en/safety.html

Two possibilities for installation:
 - put `terneo` folder to the `custom_components` folder and reboot HA.
 - With HACS: go in HACS, click on Integrations, click on the three little dots at top of the screen and selection "custom repositories", add this github url, select "Integration" as repository, and click ADD. Then go to the Integrations tab of HACS, and install the "Terneo Thermostat" integration.

config example (`configuration.yaml`):

```
climate:
  - platform: terneo
    serial: 'DEVICE_SERIALNUMBER'
    host: 'DEVICE_IP'
```
serial number can be found on the page  http://`{device_ip}`/index.html

## Validation

Tested with Home Assistant Core 2026.10.2 and Terneo ax firmware
`2.24.1.Y.20.2.20.12.43`. Legacy firmware power-state handling is covered by
automated tests. Network connectivity problems still require network diagnosis.

Run the regression tests in a virtual environment:

```sh
python -m pip install requests pytest
python -m pytest -q
```

See [CHANGELOG.md](CHANGELOG.md) for release details.
