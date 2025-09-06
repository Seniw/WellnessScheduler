# This file is now simplified to only provide the default settings.
# All file I/O and platformdirs logic has been removed as it is
# incompatible with Streamlit Community Cloud's ephemeral filesystem.
# User-customized settings will be stored in st.session_state per-session.

def get_default_settings():
    """Returns a dictionary with the default PDF styling settings."""
    return {
        'title': {
            'font_family': 'Helvetica', 'font_size': 16, 'bold': True, 'italic': False,
            'color_hex': '#da6342'  
        },
        'day_of_week': {
            'font_family': 'Helvetica', 'font_size': 14, 'bold': True, 'italic': False,
            'color_hex': '#da6342'  
        },
        'therapist': {
            'font_family': 'Helvetica', 'font_size': 12, 'bold': True, 'italic': False,
            'color_hex': '#779f72'  
        },
        'times': {
            'font_family': 'Helvetica', 'font_size': 12, 'bold': False, 'italic': False,
            'color_hex': '#779f72'  
        },
        'couples_header': {
            'font_family': 'Helvetica', 'font_size': 14, 'bold': True, 'italic': False,
            'color_hex': '#da6342'  
        },
        'couples_body': {
            'font_family': 'Helvetica', 'font_size': 12, 'bold': False, 'italic': False,
            'color_hex': '#779f72'  
        }
    }

def get_initial_settings():
    """
    Loads the initial settings. In this cloud-compatible version,
    this just returns the defaults, as there is no persistent settings file to read.
    """
    return get_default_settings()