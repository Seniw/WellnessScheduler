import os
import json
import platformdirs

# Define application details for platformdirs
APP_NAME = "WellnessScheduler"
APP_AUTHOR = "WellnessCenter"

def get_settings_path():
    """Gets the path to the settings.json file in the user's config directory."""
    config_dir = platformdirs.user_config_dir(APP_NAME, APP_AUTHOR)
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, 'settings.json')

def get_default_settings():
    """Returns a dictionary with the default PDF styling settings."""
    return {
        'title': {
            'font_family': 'Helvetica', 'font_size': 16, 'bold': True, 'italic': False,
            'color_hex': '#000000'
        },
        'day_of_week': {
            'font_family': 'Helvetica', 'font_size': 14, 'bold': True, 'italic': False,
            'color_hex': '#000000'
        },
        'therapist': {
            'font_family': 'Helvetica', 'font_size': 12, 'bold': True, 'italic': False,
            'color_hex': '#333333'
        },
        'times': {
            'font_family': 'Helvetica', 'font_size': 12, 'bold': False, 'italic': False,
            'color_hex': '#555555'
        },
        'couples_header': {
            'font_family': 'Helvetica', 'font_size': 14, 'bold': True, 'italic': False,
            'color_hex': '#000000'
        },
        'couples_body': {
            'font_family': 'Helvetica', 'font_size': 12, 'bold': False, 'italic': False,
            'color_hex': '#555555'
        }
    }

def load_settings():
    """Loads settings from the JSON file, returning defaults if it doesn't exist."""
    settings_path = get_settings_path()
    if not os.path.exists(settings_path):
        return get_default_settings()
    try:
        with open(settings_path, 'r') as f:
            # Merge loaded settings with defaults to handle new keys in future updates
            settings = get_default_settings()
            settings.update(json.load(f))
            return settings
    except (json.JSONDecodeError, IOError):
        return get_default_settings()

def save_settings(settings):
    """Saves the settings dictionary to the JSON file."""
    settings_path = get_settings_path()
    with open(settings_path, 'w') as f:
        json.dump(settings, f, indent=4)