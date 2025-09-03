
import os
import sys
import pandas as pd
import streamlit as st
import webbrowser
from logic import (
    load_and_clean_schedule, 
    load_and_parse_availability,
    calculate_free_slots,
    find_couples_slots,
    generate_pdf_report,
    extract_date_range_from_filename
)

# --- UI Configuration ---
st.set_page_config(page_title="Wellness Scheduler", layout="centered")
st.title("Wellness Center - Weekly Availability Generator")
st.write("Please upload the two weekly Excel files to generate the client-facing availability report.")

st.markdown("---") # Adds a visual separator line

# Button 1: Link to the online converter
st.link_button("Convert XLS to XLSX", "https://www.freeconvert.com/xls-to-xlsx/")
st.caption("Use this if your Trainer Availability file is in the old .xls format.")

# Button 2: Open the Availability Guide PDF
def open_pdf():
    # Get the directory where the app is running from (either from .py or bundled .exe)
    if getattr(sys, 'frozen', False):
        # If running as a bundled .exe, this gives the path to the .exe
        app_path = sys._MEIPASS  # This is where PyInstaller extracts files in temporary folder
    else:
        # If running from the .py file, this gives the path to the source file
        app_path = os.path.dirname(os.path.abspath(__file__))
    
    # Construct the relative path to the PDF
    guide_path = os.path.join(app_path, "Availability Guide.pdf")
    
    if os.path.exists(guide_path):
        webbrowser.open(f'file:///{guide_path}')  # Opens PDF in default viewer
    else:
        st.warning("Could not find 'Availability Guide.pdf'. Make sure it's in the correct folder.")

st.button("View Availability Guide", on_click=open_pdf)
st.markdown("---") # Adds another visual separator line


# --- File Uploaders --- 
uploaded_availability = st.file_uploader( 
    "1. Upload Trainer Availability File",
    type=['xlsx']
) 

uploaded_schedule = st.file_uploader( 
    "2. Upload ScheduleAtAGlance Report", 
    type=['xlsx'] 
)

# --- Main Logic and Button ---
if uploaded_availability and uploaded_schedule:
    # 1. Extract and validate date ranges from filenames
    avail_name = uploaded_availability.name
    sched_name = uploaded_schedule.name

    start_date_avail, end_date_avail = extract_date_range_from_filename(avail_name)
    start_date_sched, end_date_sched = extract_date_range_from_filename(sched_name)

    dates_valid = (start_date_avail is not None and 
                   start_date_avail == start_date_sched and 
                   end_date_avail == end_date_sched)

    if not dates_valid:
        st.error("Date ranges in filenames do not match or could not be read. Please upload corresponding reports.")
    else:
        # 2. Create dynamic filename for the PDF download
        pdf_filename = f"Availability {start_date_avail} to {end_date_avail}.pdf"

        if st.button("Generate Report", type="primary"):
            with st.spinner("Processing schedules and generating report..."):
                try:
                    availability_df = load_and_parse_availability(uploaded_availability)
                    obligations_df = load_and_clean_schedule(uploaded_schedule)

                    # --- New, More Nuanced Error Handling ---
                    error_messages = []
                    if availability_df.empty:
                        error_messages.append(
                            "**'Trainer Availability' file could not be processed.**\n\n"
                            "Please check that:\n"
                            "- It is a valid, uncorrupted .xls or .xlsx file.\n"
                            "- The content contains the expected text, such as 'SCHEDULE FOR' followed by a therapist's name.\n"
                            "or\n- Consider using an alternative converter(see guide)"
                        )
                    if obligations_df.empty:
                        error_messages.append(
                            "**'ScheduleAtAGlance Report' could not be processed.**\n\n"
                            "Please check that:\n"
                            "- You have uploaded the correct .xlsx report.\n"
                            "- The file is not empty or corrupted."
                        )

                    if error_messages:
                        # Join all collected error messages into a single, detailed alert
                        full_error_message = "\n\n---\n\n".join(error_messages)
                        st.error(full_error_message)
                        st.session_state.report_generated = False
                    else:
                        # --- Success Case ---
                        st.session_state.report_generated = True
                        final_slots = calculate_free_slots(availability_df, obligations_df)
                        couples_slots = find_couples_slots(final_slots)
                        pdf_buffer = generate_pdf_report(final_slots, couples_slots)
                        st.session_state.pdf_report = pdf_buffer
                        st.session_state.pdf_filename = pdf_filename
                        st.success("Report generated successfully!")

                except Exception as e:
                    st.error(f"An unexpected error occurred: {e}")
                    st.session_state.report_generated = False

# --- Download Button ---
if 'report_generated' in st.session_state and st.session_state.report_generated:
    st.download_button(
        label="Download PDF Report",
        data=st.session_state.pdf_report,
        file_name=st.session_state.pdf_filename,
        mime="application/pdf"
    )