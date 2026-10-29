"""Kitchen Dashboard constants."""
DOMAIN = 'kitchen_dashboard'
DEFAULT_PORT = 8766
SLOTS = ('cooking', 'evening', 'night')
SLOT_NAMES = {slot: f'Custom Button {index}' for index, slot in enumerate(SLOTS, 1)}
PLATFORMS = ('binary_sensor', 'button', 'event')

LEGACY_APPEARANCE = {
    'cooking': {'icon': 'mdi:weather-sunny', 'color': [245, 247, 250], 'background': [34, 44, 56]},
    'evening': {'icon': 'mdi:weather-sunset', 'color': [239, 187, 121], 'background': [34, 44, 56]},
    'night': {'icon': 'mdi:weather-night', 'color': [188, 210, 255], 'background': [34, 44, 56]},
}

DEFAULT_APPEARANCE = {
    slot: {'icon': f'mdi:numeric-{index}-circle-outline',
           'color': [216, 216, 216], 'background': [36, 36, 36]}
    for index, slot in enumerate(SLOTS, 1)
}


def migrate_appearance_options(options):
    migrated = dict(options)
    for slot, legacy in LEGACY_APPEARANCE.items():
        if not any(f'{slot}_{field}' in options for field in legacy):
            continue
        style = {field: options.get(f'{slot}_{field}', value) for field, value in legacy.items()}
        chosen = DEFAULT_APPEARANCE[slot] if style == legacy else style
        for field, value in chosen.items():
            migrated[f'{slot}_{field}'] = value
    return migrated


def appearance_options(options):
    return {slot: {field: options.get(f'{slot}_{field}', default)
                   for field, default in defaults.items()}
            for slot, defaults in DEFAULT_APPEARANCE.items()}
