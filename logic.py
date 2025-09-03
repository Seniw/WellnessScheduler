import pandas as pd
import re
from datetime import datetime, timedelta
from fpdf import FPDF
from io import BytesIO
#V2
# --- Section 1: Data Ingestion Pipeline ---

def normalize_name(name):
    """Standardizes therapist names for consistent matching."""
    if not isinstance(name, str):
        return None
    match = re.search(r'^\s*([a-zA-Z]+)', name)
    return match.group(1).lower().strip() if match else None

def load_and_clean_schedule(file_path):
    """Loads and processes the 'ScheduleAtAGlance' report."""
    try:
        df = pd.read_excel(file_path, engine='openpyxl')

        required_cols = ['Date', 'Start time', 'End time', 'Description', 'Staff']
        df = df[required_cols]
        df.columns = ['date', 'start_time', 'end_time', 'description', 'therapist']

        df['therapist'] = df['therapist'].apply(normalize_name)
        df.dropna(subset=['therapist', 'date', 'start_time', 'end_time'], inplace=True)

        df['start_datetime'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['start_time'].astype(str), errors='coerce')
        df['end_datetime'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['end_time'].astype(str), errors='coerce')

        df.dropna(subset=['start_datetime', 'end_datetime'], inplace=True)

        obligations_df = df[['therapist', 'start_datetime', 'end_datetime']].copy()
        obligations_df.drop_duplicates(inplace=True)

        return obligations_df.sort_values(by=['therapist', 'start_datetime']).reset_index(drop=True)
    except Exception:
        return pd.DataFrame()

def load_and_parse_availability(file_object):
    """
    Loads and parses the semi-structured 'Trainer Availability' report.
    This function is now robust and can handle .xlsx, .xls (binary), and HTML-as-.xls files.
    """
    df = None
    # Attempt 1: Try reading as a modern Excel file (.xlsx)
    try:
        file_object.seek(0)
        df = pd.read_excel(file_object, header=None, engine='openpyxl')
    except Exception:
        # Attempt 2: Try reading as a legacy Excel file (.xls)
        try:
            file_object.seek(0)
            df = pd.read_excel(file_object, header=None, engine='xlrd')
        except Exception:
            # Attempt 3: Try reading as an HTML table (for disguised files)
            try:
                file_object.seek(0)
                html_dfs = pd.read_html(file_object, header=None)
                if html_dfs:
                    df = html_dfs[0]
            except Exception:
                # If all attempts fail, return an empty DataFrame
                return pd.DataFrame()

    if df is None or df.empty:
        return pd.DataFrame()

    # --- Proceed with parsing the successfully loaded DataFrame ---
    try:
        df.columns = ['col1', 'col2', 'col3'][:len(df.columns)]
        lines = df.apply(lambda row: ' '.join(row.dropna().astype(str)), axis=1)

        availability_data = []
        current_therapist = None
        current_date = None

        for line in lines:
            if line.strip().upper().startswith('SCHEDULE FOR'):
                name_part = line.split('SCHEDULE FOR')[-1]
                current_therapist = normalize_name(name_part)
                continue

            date_match = re.search(r'\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s(January|February|March|April|May|June|July|August|September|October|November|December)\s\d{1,2},\s\d{4}', line)
            if date_match:
                current_date = pd.to_datetime(date_match.group(0)).date()
                continue

            if current_therapist and current_date and 'Appointments' in line:
                time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:am|pm))\s*-\s*(\d{1,2}:\d{2}\s*(?:am|pm))', line, re.IGNORECASE)
                if time_match:
                    start_str, end_str = time_match.groups()
                    start_dt = datetime.combine(current_date, datetime.strptime(start_str.strip(), '%I:%M %p').time())
                    end_dt = datetime.combine(current_date, datetime.strptime(end_str.strip(), '%I:%M %p').time())

                    availability_data.append({
                        'therapist': current_therapist,
                        'start_datetime': start_dt,
                        'end_datetime': end_dt
                    })
        return pd.DataFrame(availability_data)
    except Exception:
        return pd.DataFrame()


# --- Section 2: Availability Calculation Engine ---

def calculate_free_slots(availability_df, obligations_df):
    """Main function to calculate all available slots for all therapists."""
    all_slots = []
    therapists = availability_df['therapist'].unique()

    for therapist in therapists:
        therapist_avail = availability_df[availability_df['therapist'] == therapist]
        therapist_obs = obligations_df[obligations_df['therapist'] == therapist]

        for _, avail_row in therapist_avail.iterrows():
            day_start = avail_row['start_datetime']
            day_end = avail_row['end_datetime']

            day_obs = therapist_obs[
                (therapist_obs['start_datetime'] >= day_start) &
                (therapist_obs['end_datetime'] <= day_end)
            ].sort_values('start_datetime').to_dict('records')

            if not day_obs:
                merged_obs = []
            else:
                merged_obs = [day_obs[0]]
                for current in day_obs[1:]:
                    last = merged_obs[-1]
                    if current['start_datetime'] <= last['end_datetime']:
                        last['end_datetime'] = max(last['end_datetime'], current['end_datetime'])
                    else:
                        merged_obs.append(current)

            free_time = []
            current_start = day_start
            for obs in merged_obs:
                if current_start < obs['start_datetime']:
                    free_time.append({'start': current_start, 'end': obs['start_datetime']})
                current_start = obs['end_datetime']
            if current_start < day_end:
                free_time.append({'start': current_start, 'end': day_end})

            for free_block in free_time:
                block_start = free_block['start']
                block_end = free_block['end']

                while block_start + timedelta(minutes=75) <= block_end:
                    all_slots.append({'therapist': therapist, 'start': block_start})
                    block_start += timedelta(minutes=75)
    return all_slots

def find_couples_slots(individual_slots):
    """Identifies overlapping slots for couples massages."""
    couples_opportunities = []
    slots_by_time = {}

    for slot in individual_slots:
        start_time = slot['start']
        if start_time not in slots_by_time:
            slots_by_time[start_time] = []
        slots_by_time[start_time].append(slot['therapist'])

    for start_time, therapists in slots_by_time.items():
        if len(therapists) >= 2:
            couples_opportunities.append({'start': start_time, 'therapists': therapists})

    return sorted(couples_opportunities, key=lambda x: x['start'])

# --- Section 3: PDF Report Generation ---

class AvailabilityPDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'Weekly Availability Report', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', 0, 0, 'C')

    def add_couples_section(self, couples_slots):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, "Available Times for Couple's Massages", 0, 1, 'C')
        self.set_font('Arial', '', 12)
        if not couples_slots:
            self.cell(0, 10, "  No couples massage opportunities found for this period.", 0, 1, 'C')
        else:
            slots_by_day = {}
            for slot in couples_slots:
                day_str = slot['start'].strftime('%A')
                if day_str not in slots_by_day:
                    slots_by_day[day_str] = []
                time_str = slot['start'].strftime('%I:%M %p').lstrip('0').lower()
                if time_str not in slots_by_day[day_str]:
                    slots_by_day[day_str].append(time_str)

            for day, times in slots_by_day.items():
                self.cell(0, 8, f"  {day}: {', '.join(times)}", 0, 1, 'C')
        self.ln(10)

    def add_daily_availability(self, date, slots_for_day):
        self.set_font('Arial', 'B', 14)
        day_str = date.strftime('%A, %B %d')
        self.cell(0, 10, day_str, 0, 1, 'C')

        if not slots_for_day:
            self.cell(0, 8, "  No availability.", 0, 1, 'C')
            return

        therapist_slots = {}
        for slot in slots_for_day:
            therapist = slot['therapist'].title()
            if therapist not in therapist_slots:
                therapist_slots[therapist] = []
            time_str = slot['start'].strftime('%I:%M %p').lstrip('0').lower()
            therapist_slots[therapist].append(time_str)

        for therapist, times in sorted(therapist_slots.items()):
            times_str = ', '.join(sorted(times, key=lambda x: datetime.strptime(x, '%I:%M %p')))

            self.set_font('Arial', 'B', 12)
            self.cell(0, 8, f"{therapist}", 0, 1, 'C')
            self.set_font('Arial', '', 12)
            self.cell(0, 8, times_str, 0, 1, 'C')
        self.ln(5)

def generate_pdf_report(individual_slots, couples_slots):
    """Generates the final PDF report in memory."""
    pdf = AvailabilityPDF()
    pdf.add_page()

    pdf.add_couples_section(couples_slots)

    slots_by_date = {}
    for slot in individual_slots:
        date = slot['start'].date()
        if date not in slots_by_date:
            slots_by_date[date] = []
        slots_by_date[date].append(slot)

    sorted_dates = sorted(slots_by_date.keys())
    for date in sorted_dates:
        pdf.add_daily_availability(date, slots_by_date[date])

    pdf_buffer = BytesIO(pdf.output(dest='S'))
    return pdf_buffer

def extract_date_range_from_filename(filename):
    """Extracts date range from filenames using regex."""
    pattern1 = re.search(r'(\d{1,2}-\d{1,2}-\d{4})\s+to\s+(\d{1,2}-\d{1,2}-\d{4})', filename)
    if pattern1:
        return pattern1.groups()

    pattern2 = re.search(r'(\d{1,2}-\d{1,2}-\d{4})\s+-\s+(\d{1,2}-\d{1,2}-\d{4})', filename)
    if pattern2:
        return pattern2.groups()

    return None, None