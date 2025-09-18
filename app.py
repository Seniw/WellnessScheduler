import os
import sys
import pandas as pd
import streamlit as st
import configparser
import settings_manager
from logic import (
    load_and_clean_schedule,
    load_and_parse_availability,
    calculate_availability,
    find_couples_slots,
    generate_pdf_report,
    extract_date_range_from_filename,
    FileProcessingError,
    format_therapist_name  # <-- Import the translator function
)


def load_app_config():
    """Loads operational application settings (tolerances, durations) from config.ini."""
    config = configparser.ConfigParser()
    # Use a simple relative path, Streamlit runs from the repo root
    config.read('config.ini')
    settings = config['settings']
    return {
        'session_duration_minutes': settings.getint('session_duration_minutes', 75),
        'tolerance_minutes': settings.getint('tolerance_minutes', 30),
        'min_gap_hours': settings.getint('min_gap_hours', 1)
    }

# --- Caching Wrappers for Logic Functions ---
# These functions wrap the core logic from logic.py in Streamlit's cache
# to prevent re-parsing the same file on every UI interaction.

@st.cache_data(show_spinner="Parsing Trainer Availability file...")
def get_availability_data(uploaded_file):
    """Cached wrapper for load_and_parse_availability."""
    try:
        # Pass file-like object directly to logic function
        availability_df, name_map = load_and_parse_availability(uploaded_file)
        return availability_df, name_map, None
    except FileProcessingError as e:
        return None, None, str(e)
    except Exception as e:
        return None, None, f"An unexpected error occurred reading the availability file: {e}"

@st.cache_data(show_spinner="Parsing ScheduleAtAGlance file...")
def get_schedule_data(uploaded_file):
    """Cached wrapper for load_and_clean_schedule."""
    try:
        obligations_df, elite_therapists = load_and_clean_schedule(uploaded_file)
        return obligations_df, elite_therapists, None
    except FileProcessingError as e:
        return None, None, str(e)
    except Exception as e:
        return None, None, f"An unexpected error occurred reading the schedule file: {e}"


# --- UI Configuration ---
# This must be the first Streamlit command.
st.set_page_config(
    page_title="Wellness Scheduler", 
    page_icon="assets/favicon.ico", # <-- ADD THIS (use your .ico file's name)
    layout="centered"
)

# Load operational configuration and persistent PDF settings
config = load_app_config()
if 'pdf_settings' not in st.session_state:
    # Load the default styles once per session
    st.session_state.pdf_settings = settings_manager.get_initial_settings() # <-- Use new function
    
# --- Initialize Session State Keys ---
if 'show_guide_toggle' not in st.session_state:
    st.session_state.show_guide_toggle = True
if 'expand_styles' not in st.session_state:
    st.session_state.expand_styles = False
# State keys for the multi-stage therapist name mapping logic
if 'map_id_to_acronym_ACTIVE' not in st.session_state:
    st.session_state.map_id_to_acronym_ACTIVE = None # Stores {id: acronym_name} FOR ACTIVE THERAPISTS ONLY (e.g., {'jane': 'Jane (3) Hss'})
if 'original_editor_map' not in st.session_state:
    st.session_state.original_editor_map = None      # Stores {acronym_name: friendly_name} for resetting the editor (e.g., {'Jane (3) Hss': 'Jane (Light to Medium)'})
if 'editable_editor_map' not in st.session_state:
    st.session_state.editable_editor_map = None      # Stores the user-edited {acronym_name: final_name} (this is bound to the st.data_editor)
if 'processed_files_tuple' not in st.session_state:
    st.session_state.processed_files_tuple = None    # Tracks (avail_id, sched_id) to know when to re-parse names

# --- Callback to trigger the style editor expander ---
def open_style_editor():
    """Callback function to expand the PDF style editor in the sidebar."""
    st.session_state.expand_styles = True


st.title("Wellness Center - Weekly Availability Generator")
st.caption("This tool processes 'Staff Schedule' and 'Schedule at a Glance' reports to find and format therapist availability.")

# --- Sidebar ---
with st.sidebar:
    # CSS Injection to style sidebar expanders for a cleaner look
    st.markdown("""
    <style>
        [data-testid="stSidebar"] [data-testid="stExpander"] summary {
            background-color: #d0e0c1;
            border-radius: 5px;
            margin-bottom: 5px;
        }
        [data-testid="stSidebar"] [data-testid="stExpander"] summary p {
            color: #38565c;
            font-weight: 600;
        }
        [data-testid="stSidebar"] [data-testid="stExpander"] summary svg {
            color: #38565c;
        }
    </style>
    """, unsafe_allow_html=True)

    st.header("📄 Guide & Settings")

    # Logic to control PDF Style Expander state (so it closes after opening via button)
    expand_style_now = st.session_state.get("expand_styles", False)
    
    with st.expander("Customize PDF Styles", expanded=expand_style_now):
        if expand_style_now:
            # Reset the trigger so it doesn't stay open on reruns
            st.session_state.expand_styles = False
        
        st.markdown("Changes are saved automatically. Previews appear below.")
        
        # Helper function to create a row of style controls
        def style_editor(label, key):
            st.subheader(label)
            settings = st.session_state.pdf_settings[key]
            c1, c2, c3 = st.columns(3)
            settings['font_size'] = c1.number_input("Size", min_value=6, max_value=36, value=settings['font_size'], key=f"{key}_size")
            settings['color_hex'] = c2.color_picker("Color", value=settings['color_hex'], key=f"{key}_color")
            settings['bold'] = c3.checkbox("Bold", value=settings['bold'], key=f"{key}_bold")
            settings['italic'] = c3.checkbox("Italic", value=settings['italic'], key=f"{key}_italic")
            
            # --- Live Style Preview ---
            # Show the user the immediate effect of their style changes
            st.markdown("**Preview:**")
            style_str = (
                f"font-family:Helvetica; "
                f"font-size:{settings['font_size']}px; "
                f"color:{settings['color_hex']}; "
                f"font-weight:{'bold' if settings['bold'] else 'normal'}; "
                f"font-style:{'italic' if settings['italic'] else 'normal'};"
            )
            preview_html = f'''
                <div style="padding: 10px; border-radius: 5px; background-color: var(--streamlit-theme-backgroundColor);">
                    <span style="{style_str}">{label} Preview Text</span>
                </div>
            '''
            st.markdown(preview_html, unsafe_allow_html=True)
            # --- End Preview ---
            
            st.divider()

        # Create the UI for each styleable PDF element
        style_editor("Report Title", 'title')
        style_editor("Couples Section Header", 'couples_header')
        style_editor("Couples Section Body", 'couples_body')
        style_editor("Day of the Week", 'day_of_week')
        style_editor("Therapist Name", 'therapist')
        style_editor("Availability Times", 'times')
        if st.button("Reset Styles to Default"):
            st.session_state.pdf_settings = settings_manager.get_default_settings()
            settings_manager.save_settings(st.session_state.pdf_settings)
            st.rerun()

    # --- FULL GUIDE & FAQ CONTENT ---
    # Guide Expander controlled by main page toggle
    with st.expander("View Guide & FAQ", expanded=st.session_state.show_guide_toggle):
        st.markdown("""
        **1. Go to Reports → Staff Schedule**
        * Select your start and end date (e.g., Monday-Friday or Thursday-Sunday).
        * Change "Late cancel - no charge" to "ALL" in the drop-down menu.
        * Export to excel.
            * Save the file as is (don't change the default file name).
        """)
        
        image_path_trainer_avail = "assets/trainierAvailguideimg.png"
        if os.path.exists(image_path_trainer_avail):
            st.image(image_path_trainer_avail)

        st.markdown("""
        **2. Go to Reports → Schedule at a Glance**
        * Select the same start and end dates as in the previous report.
        * Filters → Staff:
            * Deselect Waitlist.
            * Deselect Late cancel - no charge.
        * Export to excel.
            * Save the file as is (don't change the default file name).
        """)

        image_path_schedule = "assets/ScheduleAtAGlance.png"
        if os.path.exists(image_path_schedule):
            st.image(image_path_schedule)

        st.markdown("""
        **3. Generate the Report in This App**
        * Upload the 'Staff Schedule' and 'Schedule at a Glance' files into the main window.
        * Click the 'Generate Report' button.
        * Click 'Download PDF Report'.
        
        ---
        ### FAQ

        **Why does "Waitlist" or "Late Cancel" appear as a therapist on my final report?**
        * This happens when 'Waitlist' or 'Late cancel - no charge' are left selected when generating the 'Schedule at a Glance' report. The program sees them as valid schedule items.
        * **How to fix it:** Follow Step 2 in the guide *exactly*. Re-download the 'Schedule at a Glance' report, making sure to de-select those two items from the Staff filter.

        **Error: "Please upload both files to generate the report."**
        * **What it means:** You clicked "Generate Report" before two files were successfully uploaded.
        * **How to fix it:** Simply upload both required Excel files into their designated boxes.

        **Error: "The date ranges in the filenames do not match..."**
        * **What it means:** The program checks the filenames to ensure you are comparing matching reports. This error means the dates (e.g., "01-01-2024 to 01-07-2024") found in the two filenames are different.
        * **How to fix it:** Check the files you downloaded. Ensure you exported both reports using the exact same date range. Do not change the filenames manually.

        **Error: "The 'Trainer Availability' file... no schedules were found inside" OR "no valid schedule blocks were found."**
        * **What it means:** The application successfully opened the file but could not find any recognizable staff schedules (i.e., rows marked "Appointments"). This is almost always caused by generating the 'Staff Schedule' report with the wrong filter settings.
        * **How to fix it:** Go back to your scheduling software. [cite_start]Re-download the **Staff Schedule** report, ensuring you follow Step 1 and set the status filter dropdown to **"ALL"**[cite: 2].

        **Error: "The 'ScheduleAtAGlance' file... missing a required column..." OR "Could not parse some dates or times..."**
        * **What it means:** The 'ScheduleAtAGlance' report is in an unexpected format. This can mean a required column (like 'Date', 'Start time', or 'Staff') is missing, or the data inside (like the 'Start time') is in a format the program cannot read.
        * **How to fix it:** Re-download the correct 'Schedule at a Glance' report. Ensure no columns have been manually deleted or altered. Verify you are uploading the correct file to the second input box.

        **Error: "Name maps not found in session. Please re-upload files..."**
        * **What it means:** This technical error usually means the 'Trainer Availability' file was parsed but contained **zero active therapists** for the selected date range (e.g., you ran a report for a weekend when no one is working). Without any therapists, the name editor and report generator cannot start.
        * **How to fix it:** Verify that the 'Trainer Availability' file you uploaded actually contains "SCHEDULE FOR" sections for therapists who are working that week. If it doesn't, run the report for the correct week.

        **Error: "An unexpected system error occurred..." OR an error mentioning "lxml" or "parsing".**
        * **What it means:** This is a general error that can happen for several reasons, typically meaning the program couldn't even read a file, or one of the files is fundamentally wrong.
        * **How to fix it:**
            * **1. Check if Files are Open:** Make sure the Excel files are not open in Microsoft Excel or another program. Excel "locks" files when they are open, preventing this tool from reading them. Close the file and try again.
            * **2. Check for Correct Files:** Did you accidentally upload the wrong file (like a PDF) or the same file into both slots?
            * **3. Check for a Permanent Report Format Change (Developer Fix Required)** This error can occur if your scheduling software provider updates the structure, format, or file type of their exported reports. Think of this application as a custom-made key designed to fit the specific format of those reports—if the provider changes the "lock," the key no longer works. This means the application can no longer recognize or process the updated files without a code update. Common signs include renamed columns, a different layout, or a new file type. If you suspect this is the case, please contact the developer and include a sample of the updated report.

        **My PDF style settings (colors, fonts) reset every time I close the app. Why?**
        * This is the expected behavior for this type of web application. Your custom styles are stored only for your current browser session. Because the app runs in a cloud environment with a temporary file system, it cannot save settings permanently. When you close the browser tab, the session ends, and the custom styles are cleared.
        * **How to fix it:** You will need to re-apply your desired style customizations at the beginning of each new session. The app will always load with the default styles.

                    
        ### Contact & Support
        Have a feature request or encounter a persistent issue? Please contact the developer at: alexanderseniw.5.pro@gmail.com
        """)
    # --- END FULL GUIDE CONTENT ---

    # --- Advanced Name Map Editor ---
    with st.expander("Advanced: Edit Therapist Names"):
        st.markdown(
            "This panel lists **active therapists** found in the file. Use the 'Display_Name' column "
            "to set the exact name you want printed on the final PDF."
        )
        
        # This editor only activates after the Trainer Availability file is uploaded and parsed
        if 'editable_editor_map' not in st.session_state or st.session_state.editable_editor_map is None:
            st.caption("Upload a 'Trainer Availability' file in the main window to activate the name editor.")
        else:
            st.info("Edit the names in the **Display_Name** column. This is what will appear on the report.", icon="✏️")
            
            try:
                # Build DataFrame from the {acronym_name: friendly_name} map
                map_df = pd.DataFrame.from_dict(
                    st.session_state.editable_editor_map,
                    orient='index',
                    columns=['Display_Name']
                )
                map_df.index.name = "Original_Name (from file)" # This is the key, e.g., "Jane (3) Hss"
                
                # Create the data editor, bound to this dataframe
                edited_df = st.data_editor(
                    map_df,
                    width='stretch',
                    disabled=["Original_Name (from file)"] # Lock the "key" column so only values are editable
                )
                
                # On any edit, save the resulting dataframe (as a dict) back to the session state variable
                if edited_df is not None:
                    # The new map is {acronym_name: final_edited_name}
                    st.session_state.editable_editor_map = edited_df['Display_Name'].to_dict()

                if st.button("Reset Names to Friendly Default"):
                    # Reset editable map back to the original auto-formatted {acronym_name: friendly_name} map
                    st.session_state.editable_editor_map = st.session_state.original_editor_map.copy()
                    st.rerun()

            except Exception as e:
                st.error(f"Could not display name editor: {e}")
    # --- End Name Editor ---

# --- Welcome Message & Guided Flow Toggle ---
st.info("👋 **Welcome!** This tool generates a client-facing PDF of weekly therapist availability based on two reports from your scheduling system.", icon="📄")

st.toggle(
    "Show step-by-step guide (for first-time users)", 
    key="show_guide_toggle",
    help="If you are a returning user, toggle this off to use the faster compact upload view."
)
st.divider()

# Initialize upload variables
uploaded_availability = None
uploaded_schedule = None

# This logic displays either the detailed step-by-step guide or the compact "expert" view
if st.session_state.show_guide_toggle:
    # --- Step-by-Step Guided Flow ---
    st.subheader("Step 1: Get Your Files")
    st.markdown("Open the **'📄 Guide & Settings'** in the sidebar (it should already be open). Follow the instructions in **'View Guide & FAQ'** *exactly* to download your two reports.")
    st.warning("You must follow the guide's instructions (like setting the filter to 'ALL') and use the reference images, or the report will fail.", icon="❗")
    with st.container(border=True):
        st.subheader("Step 2: Upload 'Trainer Availability'")
        uploaded_availability = st.file_uploader(
            "Upload Staff Schedule (.xls)", type=['xls'], key="guide_uploader_avail",
            help="Upload the 'Staff Schedule' Excel file (.xls) downloaded from your system per Step 1 in the guide. Do not change the filename."
        )
    with st.container(border=True):
        st.subheader("Step 3: Upload 'ScheduleAtAGlance'")
        uploaded_schedule = st.file_uploader(
            "Upload Schedule at a Glance (.xlsx)", type=['xlsx'], key="guide_uploader_sched",
            help="Upload the 'Schedule at a Glance' Excel file (.xlsx) downloaded from your system per Step 2 in the guide. Do not change the filename."
        )
    st.subheader("Step 4: (Optional) Customize Styles & Names")
    st.markdown("You can customize PDF fonts in the sidebar. Advanced users can also edit therapist names (see the 'Advanced' panel in the sidebar).")
    st.button("Open PDF Style Editor ➡️", on_click=open_style_editor, help="This will open the 'Customize PDF Styles' panel in the sidebar.")
    
    st.subheader("Step 5: Generate Report")
    st.markdown("Once both files are uploaded, verify the dates below and click **'Generate Report'**.")
else:
    # --- Compact "Expert" Flow ---
    st.markdown("Please upload the two weekly Excel files to generate the client-facing availability report.")
    col1, col2 = st.columns(2)
    with col1:
        uploaded_availability = st.file_uploader(
            "1. Trainer Availability (.xls)", type=['xls'], key="expert_uploader_avail",
            help="Upload the 'Staff Schedule' Excel file (.xls). Do not change the filename."
        )
    with col2:
        uploaded_schedule = st.file_uploader(
            "2. ScheduleAtAGlance (.xlsx)", type=['xlsx'], key="expert_uploader_sched",
            help="Upload the 'Schedule at a Glance' Excel file (.xlsx). Do not change the filename."
        )

st.divider()

# --- Main Processing Logic ---
# This block runs only after BOTH files have been uploaded.
if uploaded_availability and uploaded_schedule:
    avail_name = uploaded_availability.name
    sched_name = uploaded_schedule.name

    # --- Therapist Name Map Generation ---
    # This logic block runs whenever the combination of files changes.
    # It parses both files ONCE (using the cache) and builds all necessary maps for the Name Editor.
    current_files_tuple = (uploaded_availability.file_id, uploaded_schedule.file_id)
    if current_files_tuple != st.session_state.get('processed_files_tuple'):
        # A new file or combination of files has been uploaded. Re-parse and build all name maps.
        
        # 1. Parse schedule file to get the list of elite therapists
        _, elite_therapists, sched_parse_error = get_schedule_data(uploaded_schedule)
        
        # 2. Parse availability file
        availability_df, map_id_to_acronym_FULL, avail_parse_error = get_availability_data(uploaded_availability)
        
        # 3. Handle any parsing errors
        if avail_parse_error or sched_parse_error:
            if avail_parse_error: st.error(f"Error parsing Trainer Availability: {avail_parse_error}")
            if sched_parse_error: st.error(f"Error parsing ScheduleAtAGlance: {sched_parse_error}")
            # Clear all maps on error
            st.session_state.map_id_to_acronym_ACTIVE = None
            st.session_state.original_editor_map = None
            st.session_state.editable_editor_map = None
            st.session_state.processed_files_tuple = None # Mark as not processed so it tries again
        elif map_id_to_acronym_FULL and availability_df is not None and not availability_df.empty:
            
            # 4. Filter the full name map to include ONLY therapists with actual schedule data in this file
            active_therapist_ids = set(availability_df['therapist'].unique())
            active_map_id_to_acronym = {
                id_key: acronym_val for id_key, acronym_val in map_id_to_acronym_FULL.items() 
                if id_key in active_therapist_ids
            }
            
            # 5. Build the two maps needed for the sidebar editor
            # Use the imported format_therapist_name function, passing the elite list
            editor_map_acronym_to_friendly = {}
            for acronym_val in active_map_id_to_acronym.values():
                # Translate "Jeni (4)..." -> "Jeni Elite Therapist (Medium to Deep)"
                friendly_name = format_therapist_name(acronym_val, elite_therapists=elite_therapists) 
                editor_map_acronym_to_friendly[acronym_val] = friendly_name

            # 6. Store all maps in session state
            st.session_state.map_id_to_acronym_ACTIVE = active_map_id_to_acronym # {id: acronym}
            st.session_state.original_editor_map = editor_map_acronym_to_friendly # {acronym: friendly} (for reset)
            st.session_state.editable_editor_map = editor_map_acronym_to_friendly.copy() # {acronym: friendly_or_edited} (for editor)
            st.session_state.processed_files_tuple = current_files_tuple
            st.rerun() # Rerun to make the sidebar editor populate with the new data
        elif availability_df is not None and availability_df.empty:
             # This handles the edge case where the file parses but contains no actual schedules
             st.error("Trainer Availability file was read, but no valid schedule blocks were found. Cannot populate therapist editor.")
             st.session_state.processed_files_tuple = current_files_tuple # Mark as processed to avoid loops


    # --- Date verification logic ---
    start_date_avail, end_date_avail = extract_date_range_from_filename(avail_name)
    start_date_sched, end_date_sched = extract_date_range_from_filename(sched_name)
    # Check that filenames were parsed AND that the dates match exactly
    dates_valid = (start_date_avail is not None and
                   start_date_avail == start_date_sched and
                   end_date_avail == end_date_sched)

    with st.container(border=True):
        st.write("**File Date Verification**")
        c1, c2 = st.columns(2)
        date_range_avail_str = f"{start_date_avail} to {end_date_avail}" if start_date_avail and end_date_avail else "N/A"
        date_range_sched_str = f"{start_date_sched} to {end_date_sched}" if start_date_sched and end_date_sched else "N/A"
        c1.metric("Trainer Availability Dates", date_range_avail_str, help=avail_name)
        c2.metric("ScheduleAtAGlance Dates", date_range_sched_str, help=sched_name)
        if dates_valid:
            st.success(f"✅ Dates match: **{date_range_avail_str}**.")
        else:
            st.error("❌ Date ranges in filenames do not match or could not be read.")


    if dates_valid:
        pdf_filename = f"Availability {start_date_avail} to {end_date_avail}.pdf"
        sort_order = st.radio(
            "**Sort therapists by:**",
            ("Alphabetical", "By First Availability"),
            horizontal=True,
            help="Choose how to order therapists for each day in the PDF report."
        )

        if st.button("Generate Report", type="primary"):
            # --- Report Generation Workflow ---
            # This logic runs when the user clicks the generate button
            with st.spinner("Processing schedules and generating report..."):
                try:
                    # 1. Get base data from cache (or re-run if files changed)
                    availability_df, _, avail_err = get_availability_data(uploaded_availability)
                    obligations_df, _, sched_err = get_schedule_data(uploaded_schedule)

                    if avail_err or sched_err:
                        if avail_err: st.error(f"Availability File Error: {avail_err}", icon="️⚠️")
                        if sched_err: st.error(f"Schedule File Error: {sched_err}", icon="️⚠️")
                        raise FileProcessingError("Could not process one or both files.")

                    if availability_df is None or obligations_df is None:
                         raise FileProcessingError("One or both data files returned empty.")
                         
                    # 2. Get the required name maps from session state (which were built above)
                    map_id_to_acronym = st.session_state.get('map_id_to_acronym_ACTIVE') # {id: acronym}
                    map_acronym_to_final = st.session_state.get('editable_editor_map') # {acronym: final_edited_name}

                    if not map_id_to_acronym or not map_acronym_to_final:
                        raise FileProcessingError("Name maps not found in session. Please re-upload files or ensure the availability file contains active schedules.")

                    # 3. Create the FINAL composite map to pass to the PDF generator.
                    # This translates the internal {ID -> Final_Display_Name}
                    # e.g., {'jane': 'Jane Doe (Light)'}
                    final_map_for_pdf = {}
                    for id_key, acronym_val in map_id_to_acronym.items():
                        # Find the final edited name from the editor map
                        final_display_name = map_acronym_to_final.get(acronym_val, acronym_val)
                        final_map_for_pdf[id_key] = final_display_name
                         
                    # 4. Run calculations using the core logic functions
                    continuous_blocks, individual_slots = calculate_availability(
                        availability_df,
                        obligations_df,
                        session_duration_minutes=config['session_duration_minutes']
                    )
                    
                    couples_slots = find_couples_slots(
                        continuous_blocks,
                        obligations_df,
                        tolerance_minutes=config['tolerance_minutes'],
                        session_duration_minutes=config['session_duration_minutes']
                    )
                    
                    # 5. Pass the FINAL composite map to the PDF generator
                    pdf_buffer = generate_pdf_report(
                        individual_slots, 
                        couples_slots,
                        final_map_for_pdf,  # <-- Pass the final, user-edited map
                        st.session_state.pdf_settings, 
                        sort_order
                    )
                    
                    st.session_state.report_generated = True
                    st.session_state.pdf_report = pdf_buffer
                    st.session_state.pdf_filename = pdf_filename
                    st.success("Report generated successfully! - Be sure upload it to google docs to preserve formatting.", icon="✅")

                except FileProcessingError as e:
                    st.session_state.report_generated = False
                    error_str = str(e)
                    # Custom error matching logic to provide user-friendly help from the FAQ
                    user_message = "A file could not be processed. Please check that it is the correct, uncorrupted report from the booking system."
                    if "missing the following required column" in error_str:
                         user_message = "The 'ScheduleAtAGlance' file has an unexpected format. It may be missing a required column (like 'Date' or 'Staff'). Please re-download it."
                    elif "could not find any valid availability entries" in error_str:
                         user_message = "The 'Trainer Availability' file was read, but no schedules were found inside. Please check that the file contains 'SCHEDULE FOR' sections and time ranges."
                    elif "appears to be empty" in error_str:
                         user_message = "The 'Trainer Availability' file appears to be empty. Please open it to check for content and re-download if necessary."
                    
                    st.error(f"**Processing Failed:** {user_message}", icon="️⚠️")
                    if str(e) != user_message: # Only show technical details if they add new info
                        with st.expander("Show Technical Details"):
                            st.code(error_str)


                except Exception as e:
                    # General catch-all for any other unexpected system error
                    st.session_state.report_generated = False
                    st.error(f"An unexpected system error occurred. Please ensure the files are not open elsewhere and try again.", icon="🚨")
                    with st.expander("Show Technical Details"):
                        st.code(e)


# Download Button appears only after a report is successfully generated
if st.session_state.get('report_generated', False):
    st.download_button(
        label="Download PDF Report",
        data=st.session_state.pdf_report,
        file_name=st.session_state.pdf_filename,
        mime="application/pdf"
    )