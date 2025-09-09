import pandas as pd
import re
from datetime import datetime, timedelta
from fpdf import FPDF
from io import BytesIO
from bs4 import BeautifulSoup
import platform

# --- Section 0: Custom Exception Definitions ---
class FileProcessingError(Exception):
    """Base class for custom exceptions in this module."""
    pass

class ScheduleParsingError(FileProcessingError):
    """Exception for errors parsing the ScheduleAtAGlance report."""
    pass

class AvailabilityParsingError(FileProcessingError):
    """Exception for errors parsing the Trainer Availability report."""
    pass


# --- Section 1: Data Ingestion Pipeline ---

def normalize_name(name):
    """Standardizes therapist names for consistent matching."""
    if not isinstance(name, str):
        return None
    match = re.search(r'^\s*([a-zA-Z]+)', name)
    return match.group(1).lower().strip() if match else None

def format_therapist_name(raw_name_string, elite_therapists=None):
    """Formats the therapist's raw name to include a pressure description and elite status."""
    if not isinstance(raw_name_string, str):
        return ""

    if elite_therapists is None:
        elite_therapists = set()

    # 1. Extract the primary name (first alphabetical word)
    name_match = re.search(r'^\s*([a-zA-Z]+)', raw_name_string)
    name = name_match.group(1).title() if name_match else raw_name_string

    # 2. Check for Elite Status
    normalized_name = normalize_name(raw_name_string)
    elite_tag = " Elite Therapist" if normalized_name in elite_therapists else ""

    # 3. Find the pressure level indicator
    level = None
    # Prioritize '3+' as it contains '3'
    if '3+' in raw_name_string:
        level = '3+'
    else:
        pressure_match = re.search(r'\b([34])\b', raw_name_string)
        if pressure_match:
            level = pressure_match.group(1)
    
    suffix = ""
    if level:
        if level == "3":
            suffix = " (Light to Medium)"
        elif level == "3+":
            suffix = " (Light to Medium+)"
        elif level == "4":
            suffix = " (Medium to Deep)"
    
    return f"{name}{elite_tag}{suffix}"

def load_and_clean_schedule(file_path):
    """Loads and processes the 'ScheduleAtAGlance' report."""
    try:
        df = pd.read_excel(file_path, engine='openpyxl')
        
        required_cols = ['Date', 'Start time', 'End time', 'Description', 'Staff']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ScheduleParsingError(f"The 'ScheduleAtAGlance' report is missing the following required column(s): {', '.join(missing_cols)}.")

        # --- Identify Elite Therapists ---
        # This is done before columns are renamed/dropped for efficiency.
        elite_df = df[df['Description'].str.contains("Elite Level", na=False)]
        elite_therapists = set(elite_df['Staff'].apply(normalize_name).dropna())
        
        df = df[required_cols]
        df.columns = ['date', 'start_time', 'end_time', 'description', 'therapist']

        df['therapist'] = df['therapist'].apply(normalize_name)
        df.dropna(subset=['therapist', 'date', 'start_time', 'end_time'], inplace=True)

        df['start_datetime'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['start_time'].astype(str), errors='coerce')
        df['end_datetime'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['end_time'].astype(str), errors='coerce')

        if df['start_datetime'].isnull().any() or df['end_datetime'].isnull().any():
            raise ScheduleParsingError("Could not parse some dates or times in the 'ScheduleAtAGlance' report. Please ensure they are in a standard format (e.g., 'HH:MM AM/PM').")

        df.dropna(subset=['start_datetime', 'end_datetime'], inplace=True)

        obligations_df = df[['therapist', 'start_datetime', 'end_datetime']].copy()
        obligations_df.drop_duplicates(inplace=True)

        return obligations_df.sort_values(by=['therapist', 'start_datetime']).reset_index(drop=True)
    except FileProcessingError as e:
        raise e
    except Exception as e:
        raise ScheduleParsingError(f"An unexpected error occurred while processing the 'ScheduleAtAGlance' report: {e}")


def load_and_parse_availability(file_object):
    """
    Loads and parses the 'Trainer Availability' report by navigating its
    specific HTML structure using BeautifulSoup.
    """
    try:
        file_object.seek(0)
        content = file_object.read()
        soup = BeautifulSoup(content, 'lxml')

        availability_data = []
        display_name_map = {}
        
        # Find all <strong> tags, which contain the staff names
        schedule_headers = soup.find_all('strong')

        for header in schedule_headers:
            header_text = header.get_text(strip=True).upper()
            
            if header_text.startswith('SCHEDULE FOR'):
                # Extract the therapist's name
                name_part = header_text.replace('SCHEDULE FOR', '').strip()
                current_therapist = normalize_name(name_part)
                if not current_therapist:
                    continue # Skip entries like '*WAITLIST*' or '*LATE CANCEL*'

                # Populate the name map for later display formatting
                if current_therapist not in display_name_map:
                    display_name_map[current_therapist] = name_part.title()

                # Find the parent table of the header, then find the schedule table within it
                parent_table = header.find_parent('table')
                schedule_table = parent_table.find('table', id='staffScheduleReport')

                if not schedule_table:
                    continue # This therapist has no schedule table (e.g., Heidi, MBO)

                current_date = None
                # Process the rows within this specific therapist's schedule table
                for row in schedule_table.find_all('tr'):
                    cells = row.find_all('td')
                    
                    # A row with a single, bolded cell is a date header
                    if len(cells) == 1 and cells[0].find('strong'):
                        date_text = cells[0].get_text(strip=True)
                        date_match = re.search(r'\b(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s(January|February|March|April|May|June|July|August|September|October|November|December)\s\d{1,2},\s\d{4}', date_text)
                        if date_match:
                            current_date = pd.to_datetime(date_match.group(0)).date()
                        continue

                    # A row with multiple cells is a time entry
                    if current_date and len(cells) > 2:
                        time_text = cells[1].get_text(strip=True)
                        description_text = cells[2].get_text(strip=True)
                        
                        # Only process rows marked as "Appointments"
                        if 'Appointments' in description_text:
                            time_match = re.search(r'(\d{1,2}:\d{2}\s*(?:am|pm))\s*-\s*(\d{1,2}:\d{2}\s*(?:am|pm))', time_text, re.IGNORECASE)
                            if time_match:
                                start_str, end_str = time_match.groups()
                                start_dt = datetime.combine(current_date, datetime.strptime(start_str.strip(), '%I:%M %p').time())
                                end_dt = datetime.combine(current_date, datetime.strptime(end_str.strip(), '%I:%M %p').time())

                                availability_data.append({
                                    'therapist': current_therapist,
                                    'start_datetime': start_dt,
                                    'end_datetime': end_dt
                                })
        
        if not availability_data:
            raise AvailabilityParsingError("Successfully read the file, but could not find any valid availability entries. Please check the file content.")

        return pd.DataFrame(availability_data), display_name_map
    except Exception as e:
        raise AvailabilityParsingError(f"An unexpected error occurred while parsing the 'Trainer Availability' data: {e}")

# --- Section 2: Availability Calculation Engine ---

def calculate_availability(availability_df, obligations_df, session_duration_minutes=75):
    """
    Calculates all available slots and continuous free blocks for all therapists.
    This function serves as the core availability engine, producing two outputs:
    1. A list of continuous free time blocks for all therapists.
    2. A list of discrete, bookable slots for individual appointments.
    """
    all_slots = []
    all_continuous_blocks = []
    therapists = availability_df['therapist'].unique()
    session_duration = timedelta(minutes=session_duration_minutes)

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

            # Merge overlapping or back-to-back obligations
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

            # Determine the continuous free time blocks between obligations
            free_time = []
            current_start = day_start
            for obs in merged_obs:
                if current_start < obs['start_datetime']:
                    free_time.append({'start': current_start, 'end': obs['start_datetime']})
                current_start = obs['end_datetime']
            if current_start < day_end:
                free_time.append({'start': current_start, 'end': day_end})

            # Process each continuous free block
            for free_block in free_time:
                block_start = free_block['start']
                block_end = free_block['end']
                
                # First, save the entire continuous block for couples analysis
                if block_end - block_start >= session_duration:
                    all_continuous_blocks.append({
                        'therapist': therapist,
                        'start': block_start,
                        'end': block_end
                    })

                # Second, generate discrete slots for individual appointments from this block
                is_first_gap_of_day = (block_start == day_start)
                day_has_appointments = bool(merged_obs)
                use_flush_right_strategy = is_first_gap_of_day and day_has_appointments

                total_free_duration = block_end - block_start
                if total_free_duration >= session_duration:
                    num_sessions = total_free_duration // session_duration
                    
                    start_point = block_start
                    if use_flush_right_strategy:
                        total_sessions_duration = num_sessions * session_duration
                        start_point = block_end - total_sessions_duration

                    for _ in range(num_sessions):
                        all_slots.append({
                            'therapist': therapist,
                            'start': start_point,
                            'end': start_point + session_duration
                        })
                        start_point += session_duration
    
    # Return both the continuous blocks and the sorted individual slots
    return all_continuous_blocks, sorted(all_slots, key=lambda x: (x['therapist'], x['start']))


def find_couples_slots(continuous_blocks, obligations_df, tolerance_minutes=30, session_duration_minutes=75, min_gap_hours=1):
    """
    Identifies overlapping slots for couples massages using a hybrid approach.

    This function prioritizes "perfect matches" where therapists have discrete
    slots starting at the exact same time. It then finds "near miss"
    opportunities by calculating the actual intersection of two therapists'
    continuous availability blocks.
    """
    if not continuous_blocks:
        return []

    final_opportunities = {}
    session_duration = timedelta(minutes=session_duration_minutes)
    conflict_gap = timedelta(hours=min_gap_hours)

    # --- Preparation: Generate discrete slots from continuous blocks to find perfect matches ---
    individual_slots = []
    for block in continuous_blocks:
        num_sessions = (block['end'] - block['start']) // session_duration
        start_point = block['start']
        for _ in range(num_sessions):
            individual_slots.append({
                'therapist': block['therapist'],
                'start': start_point,
                'end': start_point + session_duration
            })
            start_point += session_duration

    # --- Phase 1: Find and store all "Perfect Matches" ---
    slots_by_exact_time = {}
    for slot in individual_slots:
        start_time = slot['start']
        if start_time not in slots_by_exact_time:
            slots_by_exact_time[start_time] = set()
        slots_by_exact_time[start_time].add(slot['therapist'])

    for start_time, therapists in slots_by_exact_time.items():
        if len(therapists) >= 2:
            final_opportunities[start_time] = therapists
    
    perfect_match_times = set(final_opportunities.keys())

    # --- Phase 2: Find "Near Miss" candidates using a true interval intersection ---
    therapist_blocks = {}
    for block in continuous_blocks:
        therapist = block['therapist']
        if therapist not in therapist_blocks:
            therapist_blocks[therapist] = []
        therapist_blocks[therapist].append({'start': block['start'], 'end': block['end']})

    therapists = list(therapist_blocks.keys())
    
    for i in range(len(therapists)):
        for j in range(i + 1, len(therapists)):
            t1_name, t2_name = therapists[i], therapists[j]
            blocks1, blocks2 = therapist_blocks[t1_name], therapist_blocks[t2_name]

            for b1 in blocks1:
                for b2 in blocks2:
                    # Find the latest start time and earliest end time to get the shared availability window
                    overlap_start = max(b1['start'], b2['start'])
                    overlap_end = min(b1['end'], b2['end'])

                    # Check if the shared window is long enough for at least one session
                    if overlap_end - overlap_start >= session_duration:
                        # Generate all possible slots within this shared window
                        potential_start = overlap_start
                        while potential_start + session_duration <= overlap_end:
                            # This is a valid potential slot. Now, filter it.
                            is_perfect_match = potential_start in perfect_match_times
                            is_too_close = False
                            if not is_perfect_match:
                                for perfect_time in perfect_match_times:
                                    if abs(potential_start - perfect_time) < conflict_gap:
                                        is_too_close = True
                                        break
                            
                            if not is_perfect_match and not is_too_close:
                                print(f"DEBUG: Near Miss ADDED! Therapists: {t1_name.title()}, {t2_name.title()}. Aligned Start: {potential_start.strftime('%Y-%m-%d %I:%M %p')}")
                                if potential_start not in final_opportunities:
                                    final_opportunities[potential_start] = set()
                                final_opportunities[potential_start].add(t1_name)
                                final_opportunities[potential_start].add(t2_name)
                            
                            # Move to the next potential start time
                            potential_start += session_duration

    # --- Phase 4: Format final results ---
    final_list = []
    for start_time, therapists_set in final_opportunities.items():
        if len(therapists_set) >= 2:
            final_list.append({
                'start': start_time,
                'therapists': sorted(list(therapists_set))
            })

    return sorted(final_list, key=lambda x: x['start'])
# --- Section 3: PDF Report Generation Module ---

class AvailabilityPDF(FPDF):
    def __init__(self, settings, name_map):
        super().__init__()
        self.settings = settings
        self.name_map = name_map

    def _apply_style(self, style_key):
        """Helper function to apply font, style, size, and color from settings."""
        style = self.settings.get(style_key, {})
        font_style = ''
        if style.get('bold', False): font_style += 'B'
        if style.get('italic', False): font_style += 'I'

        font_family = style.get('font_family', 'Helvetica')

        # The set_font() method handles core PDF fonts (like Helvetica, Times, Courier)
        # automatically. The previous, problematic call to add_font() has been removed.
        self.set_font(font_family, style=font_style, size=style.get('font_size', 12))
        
        hex_color = style.get('color_hex', '#000000').lstrip('#')
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)
        self.set_text_color(r, g, b)

    def header(self):
        pass

    def footer(self):
        pass

    def add_couples_section(self, couples_slots):
        self._apply_style('couples_header')
        self.cell(0, 10, "Available Times for Couple's Massages", 0, 1, 'C')
        
        if not couples_slots:
            self._apply_style('couples_body')
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
                self._apply_style('couples_body')
                # Sort times chronologically before joining
                sorted_times = sorted(times, key=lambda x: datetime.strptime(x, '%I:%M %p'))
                self.cell(0, 8, f"  {day}: {', '.join(sorted_times)}", 0, 1, 'C')
        self.ln(10)

    def add_daily_availability(self, date, slots_for_day, sort_order="Alphabetical"):
        self._apply_style('day_of_week')
        if platform.system() == 'Windows':
            day_str = date.strftime('%A, %B %#d')
        else:
            day_str = date.strftime('%A, %B %-d')
        self.cell(0, 10, day_str, 0, 1, 'C')

        if not slots_for_day:
            self.set_font('Helvetica', 'I', 12) # Use a default for this simple message
            self.set_text_color(128)
            self.cell(0, 8, "  No availability.", 0, 1, 'C')
            return

        therapist_slots = {}
        for slot in slots_for_day:
            therapist_key = slot['therapist']
            if therapist_key not in therapist_slots:
                therapist_slots[therapist_key] = []
            time_str = slot['start'].strftime('%I:%M %p').lstrip('0').lower()
            therapist_slots[therapist_key].append(time_str)

        # --- Sorting Logic Implementation ---
        therapist_items = therapist_slots.items()
        if sort_order == "By First Availability":
            sorted_items = sorted(therapist_items, key=lambda item: datetime.strptime(
                sorted(item[1], key=lambda t: datetime.strptime(t, '%I:%M %p'))[0], '%I:%M %p'
            ))
        else:  # Default to Alphabetical
            sorted_items = sorted(therapist_items)
        
        for therapist_key, times in sorted_items:
            times_str = ', '.join(sorted(times, key=lambda x: datetime.strptime(x, '%I:%M %p')))
            
            display_name = self.name_map.get(therapist_key, therapist_key.title())
            
            self._apply_style('therapist')
            self.cell(0, 8, f"{display_name}", 0, 1, 'C')
            
            self._apply_style('times')
            self.cell(0, 8, times_str, 0, 1, 'C')
        self.ln(2)

def generate_pdf_report(individual_slots, couples_slots, name_map, settings, sort_order):
    """Generates the final PDF report in memory."""
    pdf = AvailabilityPDF(settings, name_map)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    pdf._apply_style('title')
    pdf.cell(0, 10, 'Therapist Availability', 0, 1, 'C') 
    pdf.ln(5)

    pdf.add_couples_section(couples_slots)

    slots_by_date = {}
    for slot in individual_slots:
        date = slot['start'].date()
        if date not in slots_by_date:
            slots_by_date[date] = []
        slots_by_date[date].append(slot)

    sorted_dates = sorted(slots_by_date.keys())
    for date in sorted_dates:
        pdf.add_daily_availability(date, slots_by_date[date], sort_order)

    # Output to a bytes buffer
    pdf_buffer = BytesIO(pdf.output())
    
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