Wellness Scheduler
Wellness Scheduler is an automation tool designed to streamline the manual process of finding therapist availability. By parsing schedule and availability reports from booking software, it identifies open appointment slots, finds opportunities for couples' massages, and generates a client-facing PDF report.

The Problem It Solves
Previously, staff had to manually cross-reference multiple schedules to determine when therapists were free. This was a time-consuming and error-prone process. This application automates this workflow, helping to reduce administrative overhead and improve booking accuracy.

Key Features
Automated Report Parsing: Ingests two core reports (Staff Schedule and Schedule at a Glance) directly from your booking software.

Availability Calculation: Determines open appointment slots by analyzing therapist work hours and subtracting existing obligations.

Optimized Slot Placement: Prioritizes placing new appointments adjacent to existing ones to minimize unpaid gaps in a therapist's day.

Couples' Massage Finder: Analyzes simultaneous availability across all therapists to find overlapping times for couples' massages.

PDF Report Generation: Generates an easy-to-read PDF of the week's availability, ready to be shared with clients.

Customizable UI:

PDF Styling: Users can modify the font, size, color, and style (bold/italic) of titles, headers, and body text in the final report.

Name Formatting: Alter therapist names to ensure they are client-friendly.

Sort Order: Arrange therapists on the report alphabetically or by their first available time of the day.

How It Works
The application provides a step-by-step user interface:

Export Reports: Following the in-app guide, users export two required reports from the booking software:

Staff Schedule (an .xls file, which is an HTML report in disguise)

Schedule at a Glance (an .xlsx file)

Upload Files: Users upload these two files into the application. The app verifies that the date ranges in the filenames match.

Customize (Optional): Through the sidebar, users can adjust PDF styling or edit therapist display names for the final report.

Generate & Download: With a single click, the program processes the data and generates the availability report. The final PDF is then available for download.

Technical Overview
The application is built in Python and leverages several key libraries:

Streamlit: For the interactive web-based user interface.

Pandas: For data manipulation and analysis.

BeautifulSoup: For parsing the HTML content of the .xls availability report.

FPDF2: For generating the final PDF report.

Platformdirs: To save user-defined style settings in the correct, cross-platform user configuration directory, ensuring preferences persist between sessions.

Project Structure
.
├── app.py              # Main Streamlit UI and application logic
├── logic.py            # Core data processing: file parsing, availability calculation, PDF generation
├── settings_manager.py # Handles loading and saving of custom PDF style settings
├── run_app.py          # Wrapper script for launching the bundled executable
├── config.ini          # Configuration for session duration, time tolerances, etc.
├── requirements.txt    # Project dependencies
└── README.md           # This file

Installation and Local Usage (For Developers)
To run the application locally, follow these steps:

Clone the repository:

git clone <repository-url>
cd <repository-directory>

Create and activate a virtual environment:

# For Windows
python -m venv venv
.\venv\Scripts\activate

# For macOS/Linux
python3 -m venv venv
source venv/bin/activate

Install the required dependencies:

pip install -r requirements.txt

Run the Streamlit application:

streamlit run app.py

Author
This application was created by Alexander Seniw.

License
This project is licensed under the MIT License. See the LICENSE file for details.