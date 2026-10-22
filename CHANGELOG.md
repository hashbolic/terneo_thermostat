# Changelog

## 1.0.2 — 2026-10-23

- Register offline thermostats so normal polling can restore availability.
- Remove extra network requests from cached entity properties.
- Handle HTTP errors, malformed JSON, API timeouts and incomplete status safely.
- Preserve the last complete snapshot until a valid poll restores availability.
- Serialize requests per thermostat with a one-second minimum interval.
- Preserve legacy firmware support without interpreting a failed power query as OFF.
- Accept valid HTTP basic-auth credential pairs.
- Avoid modifying outgoing payloads while logging errors.
- Add 21 regression tests and HACS installation instructions.

Existing YAML keys, unique IDs, temperature scaling and command payloads remain
unchanged. Write commands are not automatically retried. Restart Home Assistant
after updating. To roll back, restore a backup of `custom_components/terneo` and
restart Home Assistant.
