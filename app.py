import os
import sys
import pandas as pd
import streamlit as st
import configparser
import settings_manager  # <-- IMPORT THE NEW SETTINGS MANAGER
from logic import (
    load_and_clean_schedule,
    load_and_parse_availability,
    calculate_availability,
    find_couples_slots,
    generate_pdf_report,
    extract_date_range_from_filename,
    FileProcessingError
)

# --- Helper function for asset paths ---
def get_asset_path(file_name):
    """Gets the absolute path to an asset, handling both development and frozen states."""
    if getattr(sys, 'frozen', False):
        application_path = os.path.dirname(sys.executable)
    else:
        application_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(application_path, file_name)

def load_app_config():
    """Loads application settings from config.ini."""
    config = configparser.ConfigParser()
    config_path = get_asset_path('config.ini')
    config.read(config_path)
    settings = config['settings']
    return {
        'session_duration_minutes': settings.getint('session_duration_minutes', 75),
        'tolerance_minutes': settings.getint('tolerance_minutes', 30),
        'min_gap_hours': settings.getint('min_gap_hours', 1)
    }

# --- UI Configuration ---
st.set_page_config(page_title="Wellness Scheduler", layout="centered")

# Load operational configuration and persistent PDF settings
config = load_app_config()
if 'pdf_settings' not in st.session_state:
    st.session_state.pdf_settings = settings_manager.load_settings()

st.title("Wellness Center - Weekly Availability Generator")

# --- Sidebar for Guide, FAQ, and NEW PDF Settings ---
with st.sidebar:
    st.header("📄 Guide & Settings")

    # --- New PDF Styling Section ---
    with st.expander("Customize PDF Styles"):
        st.markdown("Changes are saved automatically.")
        
        # Helper function to create a row of style controls
        def style_editor(label, key):
            st.subheader(label)
            settings = st.session_state.pdf_settings[key]
            c1, c2, c3 = st.columns(3)
            settings['font_size'] = c1.number_input("Size", min_value=6, max_value=36, value=settings['font_size'], key=f"{key}_size")
            settings['color_hex'] = c2.color_picker("Color", value=settings['color_hex'], key=f"{key}_color")
            settings['bold'] = c3.checkbox("Bold", value=settings['bold'], key=f"{key}_bold")
            settings['italic'] = c3.checkbox("Italic", value=settings['italic'], key=f"{key}_italic")
            # Save settings on any change
            settings_manager.save_settings(st.session_state.pdf_settings)
            st.divider()

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

    with st.expander("View Guide & FAQ"):
        # The Guide & FAQ markdown content remains the same as before...
        st.markdown("""
        **1. Go to Reports → Staff Schedule**
        * Select your start and end date (e.g., Monday-Friday or Thursday-Sunday).
        * Change "Late cancel - no charge" to "ALL" in the drop-down menu.
        * Export to excel.
            * Save the file as is (don't change the default file name).
        """)
        
        image_path_trainer_avail = get_asset_path("trainierAvailguideimg.png")
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

        image_path_schedule = get_asset_path("ScheduleAtAGlance.png")
        if os.path.exists(image_path_schedule):
            st.image(image_path_schedule)

        st.markdown("""
        **3. Generate the Report in This App**
        * Upload the 'Staff Schedule' and 'Schedule at a Glance' files into the main window.
        * Click the 'Generate Report' button.
        * Click 'Download PDF Report'.
        
        ---
        ### FAQ

        **What happens if I forget to deselect 'Waitlist' or 'Late cancel - no charge' from the 'Schedule at a Glance' report?**
        * Leaving these options selected will cause inaccurate data to appear in the reports, such as "waitlist" or "late cancel" appearing on the weekly availability, since the program cannot differentiate them from a therapist.

        **Error: "Please upload both files to generate the report."**
        * **What it means:** You clicked the "Generate" button before uploading both the 'Trainer Availability' and the 'ScheduleAtAGlance' files.
        * **How to fix it:** Simply upload both required Excel files into their designated boxes.

        **Error: "The date ranges in the filenames do not match. Please upload files for the same week."**
        * **What it means:** To prevent mistakes, the program checks that both reports cover the exact same date range. This error means the dates found in the two filenames are different.
        * **How to fix it:** Check the filenames of your reports. Download the correct reports for the matching week and re-upload them. Do not change the filenames manually.

        **Error: "The 'Trainer Availability' file was read, but no schedules were found inside."**
        * **What it means:** The application successfully opened the file but could not find any recognizable staff schedules. This is almost always caused by generating the 'Staff Schedule' report with the wrong filter settings (i.e., not set to "ALL").
        * **How to fix it:** Go back to your scheduling software. Re-download the **Staff Schedule** report, ensuring you set the status filter dropdown to **"ALL"**. Before uploading, you can open the file to confirm it contains `SCHEDULE FOR [Staff Name]` sections.

        **Error: "The 'ScheduleAtAGlance' file has an unexpected format. It may be missing a required column..."**
        * **What it means:** The 'ScheduleAtAGlance' report is missing essential data columns (like 'Date', 'Start time', or 'Staff'). This can happen if the report format was changed or if you uploaded the wrong report by accident.
        * **How to fix it:** Re-download the correct 'Schedule at a Glance' report and try again. Double-check that you are uploading it to the second input box.

        **Error: "An error occurred... One or both files could not be processed." OR "An unexpected system error occurred."**
        * **What it means:** This is a general error that can happen for a few reasons, usually meaning the program couldn't read a file correctly.
        * **How to fix it:**
            * **Check for Correct Files:** Make sure you haven't uploaded the wrong file or the same file into both slots.
            * **Check if Files are Empty:** Open the Excel files on your computer to ensure they contain data. If one is blank, re-download it.
            * **Check if Files are Open:** Make sure the files are not open in Microsoft Excel or another program, then try uploading them again.
        """)

# --- File Uploaders ---
st.markdown("Please upload the two weekly Excel files to generate the client-facing availability report.")

col1, col2 = st.columns(2)
with col1:
    uploaded_availability = st.file_uploader(
        "1. Trainer Availability",
        type=['xls']
    )
with col2:
    uploaded_schedule = st.file_uploader(
        "2. ScheduleAtAGlance",
        type=['xlsx']
    )

# --- Main Logic and Button ---
if uploaded_availability and uploaded_schedule:
    avail_name = uploaded_availability.name
    sched_name = uploaded_schedule.name

    start_date_avail, end_date_avail = extract_date_range_from_filename(avail_name)
    start_date_sched, end_date_sched = extract_date_range_from_filename(sched_name)

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
        
        # --- New Sorting Option ---
        sort_order = st.radio(
            "**Sort therapists by:**",
            ("Alphabetical", "By First Availability"),
            horizontal=True,
            help="Choose how to order therapists for each day in the PDF report."
        )

        if st.button("Generate Report", type="primary"):
            with st.spinner("Processing schedules and generating report..."):
                try:
                    availability_df, name_map = load_and_parse_availability(uploaded_availability)
                    obligations_df = load_and_clean_schedule(uploaded_schedule)
                    
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
                    
                    # Pass settings and sort order to the PDF generator
                    pdf_buffer = generate_pdf_report(
                        individual_slots, 
                        couples_slots,
                        name_map,
                        st.session_state.pdf_settings, 
                        sort_order
                    )
                    
                    st.session_state.report_generated = True
                    st.session_state.pdf_report = pdf_buffer
                    st.session_state.pdf_filename = pdf_filename
                    st.success("Report generated successfully!")

                except FileProcessingError as e:
                    st.session_state.report_generated = False
                    error_str = str(e)
                    user_message = "A file could not be processed. Please check that it is the correct, uncorrupted report from the booking system."

                    if "missing the following required column" in error_str:
                        user_message = "The 'ScheduleAtAGlance' file has an unexpected format. It may be missing a required column (like 'Date' or 'Staff'). Please re-download it."
                    elif "could not find any valid availability entries" in error_str:
                        user_message = "The 'Trainer Availability' file was read, but no schedules were found inside. Please check that the file contains 'SCHEDULE FOR' sections and time ranges."
                    elif "appears to be empty" in error_str:
                        user_message = "The 'Trainer Availability' file appears to be empty. Please open it to check for content and re-download if necessary."

                    st.error(f"**Processing Failed:** {user_message}", icon="️⚠️")
                    with st.expander("Show Technical Details"):
                        st.code(error_str)

                except Exception as e:
                    st.session_state.report_generated = False
                    st.error("An unexpected system error occurred. Please ensure the files are not open elsewhere and try again.", icon="🚨")
                    with st.expander("Show Technical Details"):
                        st.code(e)

# --- Download Button ---
if st.session_state.get('report_generated', False):
    st.download_button(
        label="Download PDF Report",
        data=st.session_state.pdf_report,
        file_name=st.session_state.pdf_filename,
        mime="application/pdf"
    )