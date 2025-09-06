# Wellness Scheduler
Wellness Scheduler is an automation tool designed to streamline the manual process of finding therapist availability. By parsing schedule and availability reports from booking software, it identifies open appointment slots, finds opportunities for couples' massages, and generates a client-facing PDF report.

## Problem Statement
Staff previously had to manually cross-reference multiple schedules to determine when therapists were free. This was time-consuming and error-prone. This application automates that workflow to reduce administrative effort and improve booking accuracy.

## Features
- **Automated Report Parsing**  
  Ingests two reports (Staff Schedule and Schedule at a Glance) directly from the booking software.
- **Availability Calculation**  
  Determines open appointment slots by analyzing therapist work hours and subtracting existing obligations.
- **Optimized Slot Placement**  
  Attempts to place new appointments adjacent to existing ones to minimize unpaid gaps in the day.
- **Couples' Massage Detection**  
  Identifies overlapping availability across therapists for scheduling couples' massages.
- **PDF Report Generation**  
  Produces a weekly availability report in PDF format for client distribution.

### Customization Options
- **PDF Styling**  
  Users can configure font, size, color, and emphasis (bold/italic) for titles, headers, and body text.
- **Therapist Name Formatting**  
  Display names can be adjusted for client readability.
- **Sort Order**  
  Therapists can be sorted alphabetically or by earliest availability.

## Usage Overview
The application provides a step-by-step interface:

1. **Export Reports**  
   Export the following from the booking software:  
   - *Staff Schedule* (`.xls`, structured as HTML)  
   - *Schedule at a Glance* (`.xlsx`)  
2. **Upload Files**  
   Upload both files into the application. The tool checks that the filenames contain matching date ranges.  
3. **Customize Output (Optional)**  
   Use the sidebar to configure PDF styles or modify therapist names.  
4. **Generate Report**  
   Process the data and download the resulting PDF.

## Technical Details
The application is written in Python and uses the following libraries:  
- `Streamlit` — Web interface  
- `Pandas` — Data handling  
- `BeautifulSoup` — Parsing HTML-formatted `.xls` files  
- `FPDF2` — PDF generation  


## Project Structure
```
.
├── app.py                  # Main Streamlit UI and application logic
├── logic.py                # Core data processing: file parsing, availability calculation, PDF generation
├── settings_manager.py     # Handles loading and saving of custom PDF style settings
├── run_app.py             # Wrapper script for launching the bundled executable
├── config.ini             # Configuration for session duration, time tolerances, etc.
├── requirements.txt       # Project dependencies
└── README.md              # This file
```

## Installation (For Developers)
To run the application locally:

1. **Clone the repository**  
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Set up a virtual environment**  
   **Windows**  
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```  
   **macOS/Linux**  
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**  
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**  
   ```bash
   streamlit run app.py
   ```

## Author
Developed by Alexander Seniw.

## License
This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.