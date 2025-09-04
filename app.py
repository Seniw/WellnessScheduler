import os
import sys
import pandas as pd
import streamlit as st
from logic import (
    load_and_clean_schedule,
    load_and_parse_availability,
    calculate_free_slots,
    find_couples_slots,
    generate_pdf_report,
    extract_date_range_from_filename,
    FileProcessingError
)

# --- Helper function for asset paths ---
def get_asset_path(file_name):
    """Gets the absolute path to an asset, handling both development and frozen states."""
    if getattr(sys, 'frozen', False):
        # The path is relative to the executable
        application_path = os.path.dirname(sys.executable)
    else:
        # The path is relative to the script file
        application_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(application_path, file_name)

# --- UI Configuration ---
st.set_page_config(page_title="Wellness Scheduler", layout="centered")
st.title("Wellness Center - Weekly Availability Generator")

# --- Sidebar for Guide, FAQ, and Resources ---
with st.sidebar:
    st.header("📄 Guide & Resources")

    st.link_button("Convert XLS to XLSX", "https://www.freeconvert.com/xls-to-xlsx/")
    st.caption("Needed if your 'Trainer Availability' file is in the old .xls format.")
    st.markdown("---")

    with st.expander("View Guide & FAQ", expanded=True):
        # --- UPDATED: Text now matches the PDF exactly ---
        st.markdown("""
        **1. Go to Reports → Staff Schedule**
        * Select your start and end date (e.g., Monday-Friday or Thursday-Sunday)
        * Change "Late cancel - no charge" to "ALL" in the drop-down menu.
        * Export to excel
            * Save the file as is (don't change the default file name).
        """)
        
        image_path_trainer_avail = get_asset_path("trainierAvailguideimg.png")
        if os.path.exists(image_path_trainer_avail):
            st.image(image_path_trainer_avail)

        st.markdown("""
        **2. Go to Reports → Schedule at a Glance**
        * Select the same start and end dates as in the previous report.
        * Filters → Staff:
            * Deselect Waitlist
            * Deselect Late cancel - no charge
        * Export to excel
            * Save the file as is (don't change the default file name).
        """)

        image_path_schedule = get_asset_path("ScheduleAtAGlance.png")
        if os.path.exists(image_path_schedule):
            st.image(image_path_schedule)

        st.markdown("""
        **3. Convert the Trainer Availability file to .xlsx**
        * Use this link: [Excel to Excel - Convert your XLS to XLSX for Free Online](https://www.freeconvert.com/xls-to-xlsx/)
        * You only need to convert the Trainer Availability file.

        **4. Open "availability_creator.exe"**
        * Input the converted Trainer Availability and Schedule at a Glance files
        * Click 'Generate'
        * Download PDF Report
        
        ---
        ### FAQ
        **What if the file isn't converting properly when using the XLS to XLSX converter?**
        * Double-check that the file is properly downloaded and is an XLS file. If the issue persists, try uploading it again or use a different converter tool.
        * Try using one of the following resources:
            * [XLS to XLSX Converter - FreeConvert.com](https://www.freeconvert.com/xls-to-xlsx/)
            * [XLS (EXCEL) to XLSX (EXCEL) (Online & Free) - Convertio](https://convertio.co/xls-xlsx/)

        **What happens if I forget to deselect 'Waitlist' or 'Late cancel - no charge'?**
        * Leaving these options selected will cause inaccurate data to appear in the reports, such as "waitlist" or "late cancel" appearing on the weekly availability.

        **Error: "Please upload both files to generate the report."**
        * **What it means:** It appears if you click the "Generate" button before uploading both the Trainer Availability file and the ScheduleAtAGlance file.
        * **How to fix it:** Simply drag and drop both required Excel files into their upload boxes. Once both files are showing, click the "Generate Availability Report" button again.

        **Error: "The date ranges in the filenames do not match. Please upload files for the same week."**
        * **What it means:** The program checks that both files cover the same time period to prevent mistakes. This error means the dates in the two filenames are different.
        * **How to fix it:** Check the filenames of the spreadsheets you downloaded. Make sure you have the correct Trainer Availability and ScheduleAtAGlance reports for the same week. Re-upload the correct matching files. Do not change the filenames. Go to the reports screen in mindbody and re-download the report for the correct date range.

        **Error: "An error occurred... One or both files could not be processed. Please check the file formats and ensure they are not empty."**
        * **What it means:** This is a general-purpose error that can happen for a few reasons. It usually means the program couldn't read the inside of one of the files correctly, even if it uploaded fine.
        * **How to fix it:** This error can almost always be solved with one of these steps:
            * **Check if the Files are Empty:** Open both Excel files on your computer to make sure they contain the usual schedule and availability data. If one is blank, you will need to re-download it from the source.
            * **Check for Correct Files:** This is the most common cause. Double-check that you haven't accidentally uploaded the wrong file. For instance, uploading the "ScheduleAtAGlance" report into both upload slots will cause this error.
            * **Look for Strange Formatting:** Open the "Trainer Availability" file. Does it look normal? If there are any unusual changes, like deleted columns or all the text merged into one cell, the program might not be able to read it. Try re-downloading a fresh copy of the file.
        """)

# --- File Uploaders ---
st.markdown("Please upload the two weekly Excel files to generate the client-facing availability report.")

col1, col2 = st.columns(2)
with col1:
    uploaded_availability = st.file_uploader(
        "1. Trainer Availability",
        type=['xlsx']
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

    # --- Interactive Date Verification Display ---
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

        if st.button("Generate Report", type="primary"):
            with st.spinner("Processing schedules and generating report..."):
                try:
                    availability_df = load_and_parse_availability(uploaded_availability)
                    obligations_df = load_and_clean_schedule(uploaded_schedule)

                    st.session_state.report_generated = True
                    final_slots = calculate_free_slots(availability_df, obligations_df)
                    couples_slots = find_couples_slots(final_slots, obligations_df)
                    pdf_buffer = generate_pdf_report(final_slots, couples_slots)
                    st.session_state.pdf_report = pdf_buffer
                    st.session_state.pdf_filename = pdf_filename
                    st.success("Report generated successfully!")

                # --- User-Friendly, Dual-User Error Details ---
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