# Voice Agent Router

Home Assistant custom conversation agent for a private Voice Agent Router service.

This integration forwards a Home Assistant Assist conversation turn to a router
service that can handle local device-control misses, deterministic Home Assistant
tools, and advanced Hermes requests.

## Installation

1. Add this repository to HACS as a custom repository.
2. Select category `Integration`.
3. Install `Voice Agent Router`.
4. Restart Home Assistant.
5. Add the `Voice Agent Router` integration from Home Assistant settings.
6. Enter your router URL, for example `http://router-host.local:8088`.
7. Enter the shared router API key if your router is configured with one.

Keep Home Assistant's local Assist handling enabled so normal smart-home
commands stay local before this router is used.
