# Kitchen Dashboard for Home Assistant

Connect your Kitchen Dashboard and customize its three shortcut buttons in Home Assistant. Assign a scene or script to each button, choose its icon, and set the icon and background colors. The defaults are neutral gray circles numbered 1, 2, and 3 on charcoal tiles.

This repository contains the Home Assistant integration. Dashboard firmware is distributed separately through the display's **Update Firmware** button. Installing this integration does not install or update the display firmware.

## Install with HACS

Requires Home Assistant Core **2026.9.2 or newer**, HACS, and a Kitchen Dashboard with the Home Assistant feature installed.

1. Open **HACS → three-dot menu → Custom repositories**.
2. Paste `https://github.com/TheCaveman135/kitchen-dashboard-integration`.
3. Choose type **Integration**, then **Add**.
4. Find **Kitchen Dashboard** in HACS and download it.
5. Restart Home Assistant.
6. Go to **Settings → Devices & services → Add integration → Kitchen Dashboard**.
7. Enter the dashboard's IP address or hostname and port **8766**. No pairing key is needed.

Use HACS Custom repositories, not the Home Assistant add-on store's repository list. GitHub collaborator access is not required for this public repository.

If the dashboard still shows its initial **Update Now** screen, finish that update first so its connection service is running.

## Customize the buttons

Open **Settings → Devices & services → Kitchen Dashboard → Configure**. For each **Custom Button 1**, **2**, or **3**, choose an existing scene or script, icon, icon color, and background color, then submit.

An empty action keeps the display's original local lighting preset. This integration does not create or modify your scenes, scripts, or automations. Icons and colors are saved on the display and remain visible when Home Assistant is disconnected.

The icon picker supports Material Design Icons 7.4.47. Unsupported icons are rejected. The neutral defaults replace untouched older sun/sunset/moon defaults; customized appearances and action assignments are preserved.

## Updating

Use **HACS** to update this integration, then restart Home Assistant when prompted. Use **Update Firmware** on the display to update the dashboard itself. The two update channels are independent.

Already installed manually? Back up Home Assistant, add this repository in HACS, download the integration, and restart. Keep the existing Kitchen Dashboard entry: its identity, button assignments, and appearance options are retained.

## Manual installation

Download `kitchen_dashboard.zip` from the [latest release](https://github.com/TheCaveman135/kitchen-dashboard-integration/releases/latest). Extract its `kitchen_dashboard` folder into your Home Assistant configuration's `custom_components` directory, then restart Home Assistant. The resulting path must be `custom_components/kitchen_dashboard/manifest.json`.

## Connection and offline behavior

The dashboard and Home Assistant must be able to reach each other on your LAN or private VPN. The display listens on port **8766**. Its API is designed for a trusted local network; do not forward this port to the internet. One Home Assistant instance can manage a dashboard at a time.

When disconnected, the display keeps its local power, brightness, color, and lighting preset controls. Home Assistant scene actions are not cached or replayed after reconnecting. The integration also provides button-press events, remote button activation, a wake-screen button, and connectivity diagnostics.

## Development

The 12 integration tests use an isolated Home Assistant instance and a fake dashboard; they do not operate physical devices. Run them inside the supported Home Assistant Python environment:

```sh
python3 tests/ha/test_integration.py
```

CI runs these tests plus the official HACS repository validator. The global Home Assistant Brands check is excluded because this is a custom HACS repository. No listing in the default HACS catalog is claimed.

For a release, update `custom_components/kitchen_dashboard/manifest.json`, commit, and publish a matching `vX.Y.Z` GitHub release. The release workflow validates the integration and uploads its installable ZIP. It has no access to dashboard firmware or its update feed.

The supported icon-name catalog comes from Material Design Icons by Pictogrammers. See [third-party notices](THIRD_PARTY.md).
