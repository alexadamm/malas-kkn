import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import re
from dotenv import load_dotenv
from .utils import generate_random_point
from src import generative
from colorama import init, Fore, Style
import getpass
from collections import defaultdict
init(autoreset=True)
from src.simaster import (
    get_simaster_session, 
    get_kkn_programs, 
    get_logbook_entries_by_id,
    get_bantu_pic_entries,
    create_sub_entry,
    create_bantu_pic_sub_entry,
    add_kkn_logbook_entry_by_id,
    post_attendance_for_sub_entry
)
from src.exporter import generate_schedule_html, export_to_html_file, export_to_pdf, export_to_ics

load_dotenv()

# --- Helper Functions for Interactive Selection ---

def select_program(session, auto=False):
    """Lists KKN programs and prompts the user to select one."""
    print("\nFetching KKN programs...")
    programs = get_kkn_programs(session)
    if not programs:
        print("No KKN programs found or failed to retrieve them.")
        return None

    print("\nAvailable KKN Programs:")
    for i, program in enumerate(programs):
        print(f"  [{i+1}] {program.get('program_mhs_judul', 'N/A')}")
    
    while True:
        try:
            if auto:
                print("\nAuto-selecting the first program...")
                return programs[0]
            choice = int(input(f"Please select a program (1-{len(programs)}): "))
            if 1 <= choice <= len(programs):
                return programs[choice-1]
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def select_main_entry(session, program_mhs_id, show_entries=True):
    """Lists main logbook entries and prompts the user to select one."""
    if show_entries:
        print(f"\nFetching logbook entries for program ID: {program_mhs_id}...")
    
    entries = get_logbook_entries_by_id(session, program_mhs_id)
    if not entries:
        print("No logbook entries found for this program.")
        return None

    if show_entries:
        print("\nAvailable Logbook Entries:")
        for entry in entries:
            print(f"  [{entry.get('entry_index')}] {entry.get('title')} (Status: {entry.get('attendance_status')})")

    while True:
        try:
            choice = int(input(f"Please select an entry (1-{len(entries)}): "))
            selected_entry = next((e for e in entries if e.get("entry_index") == choice), None)
            if selected_entry:
                return selected_entry
            else:
                print("Invalid entry number. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def select_sub_entry(session, main_entry):
    """
    Uses the pre-fetched sub_entries from the main_entry dictionary to list and select one.
    """
    print(f"\nSub-entries for '{main_entry.get('title')}':")
    
    unattended_entries = [se for se in main_entry.get('sub_entries', []) if not se.get('is_attended')]
    
    if not unattended_entries:
        print("No sub-entries found or all have been attended.")
        return None

    print("\nAvailable Sub-Entries (that need attendance):")
    for i, sub_entry in enumerate(unattended_entries):
        print(f"  [{i+1}] {sub_entry.get('title')}")

    while True:
        try:
            choice = int(input(f"Please select a sub-entry to attend (1-{len(unattended_entries)}): "))
            if 1 <= choice <= len(unattended_entries):
                return unattended_entries[choice-1]
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")

def select_pic_entry(session, pic_entries):
    """Lists PIC-assisted programs and prompts the user to select one."""
    # Sort entries to show those with unattended activities first
    sorted_entries = sorted(pic_entries, key=lambda x: any(not sub.get('is_attended', True) for sub in x.get('sub_activities', [])))

    print("\nAvailable Program Bantu (unattended first):")
    for i, entry in enumerate(sorted_entries):
        status = " (Needs Attention)" if any(not sub.get('is_attended', True) for sub in entry.get('sub_activities', [])) else ""
        print(f"  [{i+1}] {entry.get('title')} (PIC: {entry.get('pic')}){status}")

    while True:
        try:
            choice = int(input(f"Please select a program to assist (1-{len(sorted_entries)}): "))
            if 1 <= choice <= len(sorted_entries):
                return sorted_entries[choice-1]
            else:
                print("Invalid choice. Please try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")


# --- Logic Handlers for Menu Actions ---

def handle_add_logbook_entry(session):
    """Guides user to add a new main logbook entry."""
    program = select_program(session)
    if not program:
        return

    program_mhs_id = program.get("program_mhs_id")

    # Show current entries first
    print("\n--- Current Logbook Entries ---")
    entries = get_logbook_entries_by_id(session, program_mhs_id)
    if entries:
        for entry in entries:
            # Print the main entry
            print(f"\n[{entry.get('entry_index')}] {entry.get('title')} (on {entry.get('date')})")
            
            # Check for and print sub-entries
            sub_entries = entry.get('sub_entries', [])
            if sub_entries:
                for sub in sub_entries:
                    status_icon = "✅" if sub.get('is_attended') else "❌"
                    title = sub.get('title', 'N/A')
                    datetime_str = sub.get('datetime_str', 'N/A')
                    duration = sub.get('duration', 'N/A')
                    print(f"  {status_icon} Sub-Entry: {title}")
                    print(f"      Time:     {datetime_str}")
                    print(f"      Duration: {duration}")
            else:
                print("  - No sub-entries found for this logbook entry.")
    else:
        print("  No entries found yet.")
    print("---------------------------------")

    # Get details for the new entry
    title = input("\nEnter the title for the new logbook entry: ")
    default_date = datetime.now().strftime("%d-%m-%Y")
    date_str = input(f"Enter the date (DD-MM-YYYY, default: {default_date}): ") or default_date

    # Get location details
    default_lat = os.getenv("KKN_LOCATION_LATITUDE", "0.0")
    default_lon = os.getenv("KKN_LOCATION_LONGITUDE", "0.0")
    
    print(f"\nDefault location is Lat: {default_lat}, Lon: {default_lon}")
    use_default_loc = input("Use default location? (y/n, default: y): ").lower()
    
    latitude = float(default_lat)
    longitude = float(default_lon)

    if use_default_loc == 'n':
        try:
            latitude = float(input("Enter new Latitude: "))
            longitude = float(input("Enter new Longitude: "))
        except ValueError:
            print("Invalid input for location. Using defaults.")
            latitude = float(default_lat)
            longitude = float(default_lon)

    # Confirmation step
    print("\n--- New Entry Summary ---")
    print(f"  Title: {title}")
    print(f"  Date: {date_str}")
    print(f"  Location: Lat: {latitude}, Lon: {longitude}")
    print("---------------------------")
    
    confirm = input("Do you want to add this entry? (y/n, default: y): ").lower()
    if confirm == 'n':
        print("Operation cancelled.")
        return

    random_lat, random_lon = generate_random_point(latitude, longitude, 50)
    print(f"Generated random point for submission: (Lat: {random_lat}, Lon: {random_lon})")

    success = add_kkn_logbook_entry_by_id(session, program_mhs_id, title, date_str, random_lat, random_lon)
    if success:
        print("\nLogbook entry added successfully.")
    else:
        print("\nFailed to add logbook entry.")

def get_sub_entry_details_from_user(proker_title):
    """Shared logic to get sub-entry details from the user, with AI option."""
    sub_entry_title = input("\nEnter the title for the new sub-entry (kegiatan): ")
    duration_str = input("Enter the duration in minutes (default: 60): ") or "60"
    
    # --- Get additional details ---
    pelaksanaan_datetime_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    sasaran = "-"
    jumPeserta = "0"
    jumDana = "0"

    fill_details = input("\nDo you want to fill in additional details (date, time, participants, etc.)? (y/n, default: n): ").lower()
    if fill_details == 'y':
        default_date = datetime.now().strftime("%Y-%m-%d")
        date_input = input(f"Enter date (YYYY-MM-DD, default: {default_date}): ") or default_date

        default_time = datetime.now().strftime("%H:%M")
        time_input = input(f"Enter time (HH:MM, default: {default_time}): ") or default_time
        
        pelaksanaan_datetime_str = f"{date_input} {time_input}"

        sasaran = input("Enter target audience (sasaran, default: '-'): ") or "-"
        jumPeserta = input("Enter number of participants (jumlah peserta, default: '0'): ") or "0"
        jumDana = input("Enter amount of funds (jumlah dana, default: '0'): ") or "0"

    # --- AI or Manual Text Entry ---
    description_text = ""
    hasil_kegiatan_text = "Kegiatan terlaksana dengan baik."

    use_ai = False
    if generative.is_generative_ai_available():
        answer = input("\n✨ Gemini AI is available. Generate description and results? (y/n, default: n): ").lower()
        if answer == 'y':
            use_ai = True

    if use_ai:
        print("\n🤖 Generating content with Gemini AI...")
        while True:
            desc_prompt = generative.generate_description_prompt(proker_title, sub_entry_title)
            generated_desc = generative.generate_content(desc_prompt)
            
            hasil_prompt = generative.generate_hasil_kegiatan_prompt(proker_title, sub_entry_title, generated_desc)
            generated_hasil = generative.generate_content(hasil_prompt)

            print("\n--- AI Generated Content ---")
            print("Deskripsi Kegiatan:\n" + f"'{generated_desc}'")
            print("\nHasil Kegiatan:\n" + f"'{generated_hasil}'")
            print("--------------------------")

            choice = input("Accept (a), Regenerate (r), or write Manually (m)? [a/r/m] (default: a): ").lower()
            if choice == 'r':
                print("\n🔄 Regenerating content...")
                continue
            elif choice == 'm':
                description_text = input("\nEnter Deskripsi Kegiatan: ")
                hasil_kegiatan_text = input("Enter Hasil Kegiatan: ")
                break
            else:
                description_text, hasil_kegiatan_text = generated_desc, generated_hasil
                break
    else:
        description_text = input("\nEnter Deskripsi Kegiatan: ")
        hasil_kegiatan_text = input("Enter Hasil Kegiatan (default: 'Kegiatan terlaksana dengan baik.'): ") or "Kegiatan terlaksana dengan baik."
    
    return {
        "sub_entry_title": sub_entry_title,
        "duration": int(duration_str),
        "pelaksanaan_datetime": pelaksanaan_datetime_str,
        "sasaran": sasaran,
        "jumPeserta": jumPeserta,
        "jumDana": jumDana,
        "description_text": description_text,
        "hasil_kegiatan_text": hasil_kegiatan_text,
    }

def handle_create_sub_entry(session):
    """Guides user to create a new sub-entry for their own program."""
    program = select_program(session)
    if not program:
        return
    
    program_mhs_id = program.get("program_mhs_id")
    proker_title = program.get("program_mhs_judul", "Judul Proker Tidak Ditemukan")

    main_entry = select_main_entry(session, program_mhs_id)
    if not main_entry:
        return

    form_details = get_sub_entry_details_from_user(proker_title)
    
    success = create_sub_entry(session, main_entry, form_details)
    if success:
        print("\nSub-entry created successfully.")
    else:
        print("\nFailed to create sub-entry.")


def handle_post_attendance(session):
    """Guides user to post attendance for a sub-entry."""
    program = select_program(session)
    if not program:
        return
    
    program_mhs_id = program.get("program_mhs_id")

    main_entry = select_main_entry(session, program_mhs_id)
    if not main_entry:
        return
    
    sub_entry = select_sub_entry(session, main_entry)
    if not sub_entry:
        return

    try:
        latitude = float(os.getenv("KKN_LOCATION_LATITUDE"))
        longitude = float(os.getenv("KKN_LOCATION_LONGITUDE"))
    except (TypeError, ValueError):
        print("\nError: KKN_LOCATION_LATITUDE and KKN_LOCATION_LONGITUDE not set correctly in .env file.")
        return

    random_lat, random_lon = generate_random_point(latitude, longitude, 50)
    print(f"\nGenerated random point for attendance: (Lat: {random_lat}, Lon: {random_lon})")
    
    success = post_attendance_for_sub_entry(
        session, program_mhs_id, main_entry.get('entry_index'), sub_entry.get('title'), random_lat, random_lon
    )

    if success:
        print("\nAttendance posted successfully.")
    else:
        print("\nFailed to post attendance.")

def display_pic_entries(entries):
    """Displays a formatted list of PIC-assisted program entries."""
    if not entries:
        print("\nNo entries to display.")
        return

    # A simple header for the table
    print(f"\n{'No.':<4} {'PIC':<25} {'Program Title':<45} {'Status':<15}")
    print("-" * 91)
    
    for entry in entries:
        # Use emojis for a quick visual status
        status = "✅ Sudah" if entry.get('presensi_done') else "❌ Belum"
        
        print(f"{entry.get('index', ''):<4} "
              f"{entry.get('pic', 'N/A').split(' ')[0]:<10} "
              f"{entry.get('title', 'N/A'):<20} "
              f"{entry.get('date', 'N/A'):<20} "
              f"{entry.get('activity_time', 0):<5} "
              f"{entry.get('durasi', 'N/A'):<10} "
              f"{status:<15}")


def handle_bantu_pic(session):
    """
    Updated handler to display PIC-assisted programs with their sub-entries.
    """
    print("\nMengambil data Program Bantu...")
    my_program = select_program(session, auto=True)
    if not my_program:
        return

    pic_entries = get_bantu_pic_entries(session, my_program)
    if not pic_entries:
        print("Tidak ada program bantu yang dapat ditemukan.")
        return

    print("\n" + "="*85)
    print(" " * 30 + "DAFTAR PROGRAM BANTU")
    print("="*85 + "\n")
    print(len(pic_entries), "program bantu ditemukan.")
    for entry in pic_entries:
        print(f"{Fore.YELLOW}▶ {entry.get('title', 'N/A')}{Style.RESET_ALL}")
        print(f"  PIC: {entry.get('pic', 'N/A')}")
        
        sub_entries = entry.get('sub_entries', [])
        if sub_entries:
            for sub in sub_entries:
                status_icon = "✅" if sub.get('is_attended') else "❌"
                title = sub.get('title', 'N/A')
                datetime_str = sub.get('datetime_str', 'N/A')
                print(f"    {status_icon} {title} ({datetime_str})")
        else:
            print("    - Tidak ada sub-kegiatan yang tercatat.")
        print()


# --- Helper functions and constants for Timeline Visualization ---

MONTH_MAP = {
    'januari': 1, 'februari': 2, 'maret': 3, 'april': 4, 'mei': 5, 'juni': 6,
    'juli': 7, 'agustus': 8, 'september': 9, 'oktober': 10, 'november': 11, 'desember': 12
}
MAIN_PROGRAM_COLORS = [Fore.CYAN, Fore.GREEN, Fore.YELLOW, Fore.BLUE, Fore.LIGHTRED_EX, Fore.MAGENTA, Fore.WHITE]



def parse_datetime_range(datetime_str: Optional[str]) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Parses complex date-time strings from Simaster into start and end datetime objects.
    Handles same-day ("13:00 - 16:00") and overnight ("19:00 s.d 00:00") formats.
    """
    if not datetime_str:
        return None, None

    datetime_str = datetime_str.lower().replace("wib", "").strip()

    try:
        # Pattern for overnight ranges (e.g., "8 Juli 2025 19:00 s.d 9 Juli 2025 00:00")
        overnight_match = re.search(r'(\d{1,2})\s(\w+)\s(\d{4})\s(\d{2}:\d{2})\s+s\.d\s+(\d{1,2})\s(\w+)\s(\d{4})\s(\d{2}:\d{2})', datetime_str)
        if overnight_match:
            d1, m1_str, y1, t1, d2, m2_str, y2, t2 = overnight_match.groups()
            start_dt = datetime(int(y1), MONTH_MAP[m1_str], int(d1), int(t1[:2]), int(t1[3:]))
            end_dt = datetime(int(y2), MONTH_MAP[m2_str], int(d2), int(t2[:2]), int(t2[3:]))
            return start_dt, end_dt

        # Pattern for same-day ranges (e.g., "2 Juli 2025 13:00 - 16:00")
        sameday_match = re.search(r'(\d{1,2})\s(\w+)\s(\d{4})\s(\d{2}:\d{2})\s+-\s+(\d{2}:\d{2})', datetime_str)
        if sameday_match:
            d, m_str, y, t1, t2 = sameday_match.groups()
            start_dt = datetime(int(y), MONTH_MAP[m_str], int(d), int(t1[:2]), int(t1[3:]))
            end_dt = datetime(int(y), MONTH_MAP[m_str], int(d), int(t2[:2]), int(t2[3:]))
            return start_dt, end_dt
        
        # Fallback for overnight ranges without a start date (e.g., "21:00 s.d 18 Juli 2025 00:00")
        overnight_fallback_match = re.search(r'(\d{2}:\d{2})\s+s\.d\s+(\d{1,2})\s(\w+)\s(\d{4})\s(\d{2}:\d{2})', datetime_str)
        if overnight_fallback_match:
             return None, None


    except (ValueError, KeyError) as e:
        return None, None
        
    return None, None



def visualize_schedule_plot(events: List[Dict], program_colors: Dict[str, str]):
    """
    Displays the schedule in a Gantt-like chart in the console.
    """
    if not events:
        print("No events to visualize.")
        return

    print("\n" + "="*85)
    print(" " * 28 + "VISUALISASI JADWAL KEGIATAN")
    print(f" " * 20 + f"(Waktu Saat Ini: {datetime.now().strftime('%A, %d %b %Y, %H:%M WIB')})")
    print("="*85 + "\n")

    # --- Legend ---
    print("Legenda:")
    for title, color in program_colors.items():
        print(f"  {color}█ {Style.RESET_ALL}{title[:50]}")
    if any(e['type'] == 'Program Bantu' for e in events):
        print(f"  {Fore.MAGENTA}█ {Style.RESET_ALL}Program Bantu")
    print("")

    # --- Group events by date ---
    events_by_date = {}
    for event in events:
        date_key = event['start_time'].date()
        if date_key not in events_by_date:
            events_by_date[date_key] = []
        events_by_date[date_key].append(event)

    sorted_dates = sorted(events_by_date.keys())
    for date_key in sorted_dates:
        print(f"--- {date_key.strftime('%A, %d %B %Y')} ---")
        day_events = sorted(events_by_date[date_key], key=lambda x: x['start_time'])
        for event in day_events:
            start_str = event['start_time'].strftime('%H:%M')
            end_str = event['end_time'].strftime('%H:%M')
            duration_hours = (event['end_time'] - event['start_time']).total_seconds() / 3600
            bar_length = int(duration_hours * 4) 
            bar = '█' * bar_length
            
            color = event.get('color', Fore.WHITE)
            print(f"  [{start_str} - {end_str}] {color}{bar}{Style.RESET_ALL} {event['title']}")
        print("")

def handle_generate_timeline(session):
    """
    Orchestrates fetching all program data, displays it, and offers export options.
    """
    print("\n--- Generating Timeline & Report ---")
    print("Fetching data from all programs, this may take a moment...")
    
    # (Data fetching logic remains the same)
    all_events = []
    main_program_hours = defaultdict(float)
    bantu_hours = 0.0
    program_colors = {}
    color_index = 0
    pic_hours = defaultdict(float)
    programs = get_kkn_programs(session)
    if not programs:
        print(f"{Fore.YELLOW}No programs found to generate a timeline.{Style.RESET_ALL}")
        return
    for prog in programs:
        prog['title'] = prog.get('program_mhs_judul', 'Unknown Program')
        prog['program_mhs_id'] = prog.get('program_mhs_id', 'Unknown ID')
        prog_title = prog['title']
        if prog_title not in program_colors:
            program_colors[prog_title] = MAIN_PROGRAM_COLORS[color_index % len(MAIN_PROGRAM_COLORS)]
            color_index += 1
    for prog in programs:
        prog_title = prog['title']
        print(f"  - Menganalisis program utama: {prog_title[:40]}...")
        entries = get_logbook_entries_by_id(session, prog['program_mhs_id'])
        if entries:
            for entry in entries:
                for sub_entry in entry.get('sub_entries', []):
                    start_time, end_time = parse_datetime_range(sub_entry.get('datetime_str'))
                    if start_time and end_time:
                        duration = (end_time - start_time).total_seconds() / 3600.0
                        main_program_hours[prog_title] += duration
                        all_events.append({'title': sub_entry['title'], 'start_time': start_time, 'end_time': end_time, 'type': prog_title, 'color': program_colors[prog_title]})
    print("  - Menganalisis program bantu...")
    bantu_entries = get_bantu_pic_entries(session, programs[0])
    if bantu_entries:
        for entry in bantu_entries:
            pic_name = entry.get('pic', 'Unknown PIC')
            for sub_entry in entry.get('sub_entries', []):
                start_time, end_time = parse_datetime_range(sub_entry.get('datetime_str'))
                if start_time and end_time:
                    duration = (end_time - start_time).total_seconds() / 3600.0
                    bantu_hours += duration
                    pic_hours[pic_name] += duration
                    all_events.append({'title': sub_entry['title'], 'start_time': start_time, 'end_time': end_time, 'type': 'Program Bantu', 'color': Fore.MAGENTA})
    if not all_events:
        print(f"{Fore.YELLOW}No activities found to generate a timeline.{Style.RESET_ALL}")
        return

    # (Console display logic remains the same)
    visualize_schedule_plot(all_events, program_colors)
    total_hours = sum(main_program_hours.values()) + bantu_hours
    print("\n" + "="*85)
    print(" " * 30 + "RINGKASAN DURASI KEGIATAN")
    print("="*85 + "\n")
    for title, hours in main_program_hours.items():
        color = program_colors.get(title, Fore.WHITE)
        print(f"  {color}▶ {title[:50]:<55}{Style.RESET_ALL} {hours: >6.1f} jam")
    if bantu_hours > 0:
        print(f"  {Fore.MAGENTA}▶ {'Program Bantu (PIC Assistance)':<55}{Style.RESET_ALL} {bantu_hours: >6.1f} jam")
    print("-"*85)
    print(f"  {'Total Keseluruhan:':<57} {total_hours: >6.1f} jam")
    print("="*85)

    # --- UPDATED: Ask the user for their preferred export format ---
    while True:
        print("\nChoose an export option:")
        print("[1] Export to HTML Report")
        print("[2] Export to PDF Report")
        print(f"{Fore.CYAN}[3] Export to ICS (Calendar File){Style.RESET_ALL}")
        print("[4] Export All (HTML, PDF, ICS)")
        print("[5] Skip export")
        choice = input("\nEnter your choice (1-5): ").strip()
        if choice in ['1', '2', '3', '4', '5']:
            break
        else:
            print(f"{Fore.RED}Invalid choice. Please enter a number between 1 and 5.{Style.RESET_ALL}")

    if choice == '5':
        print("\nSkipping export. Returning to main menu.")
        return

    print(f"\n{Fore.CYAN}Generating content for export...{Style.RESET_ALL}")

    # Generate HTML/PDF if needed
    if choice in ['1', '2', '4']:
        html_content = generate_schedule_html(
            events=all_events, program_colors=program_colors,
            duration_summary=main_program_hours, total_hours=total_hours,
            pic_hours=pic_hours, bantu_hours=bantu_hours
        )
        if choice in ['1', '4']:
            export_to_html_file(html_content)
        if choice in ['2', '4']:
            export_to_pdf(html_content)

    # Generate ICS if needed
    if choice in ['3', '4']:
        export_to_ics(all_events)

def handle_check_all_attendance(session):
    """
    Checks and displays the attendance status for all sub-entries in main and assisted programs.
    """
    print("\n--- Checking All Attendance ---")
    print("Fetching data, this may take a moment...")

    # --- 1. Check Main Programs (Program Utama) ---
    print(f"\n{Fore.YELLOW}--- Program Utama ---{Style.RESET_ALL}")
    programs = get_kkn_programs(session)
    if not programs:
        print(f"{Fore.YELLOW}No main programs found.{Style.RESET_ALL}")
        return

    for prog in programs:
        prog_title = prog.get('program_mhs_judul', 'Unknown Program')
        print(f"\n{Fore.CYAN}Program: {prog_title}{Style.RESET_ALL}")
        entries = get_logbook_entries_by_id(session, prog['program_mhs_id'])
        if not entries:
            print("  No logbook entries found for this program.")
            continue
        
        found_sub_entry = False
        for entry in entries:
            for sub_entry in entry.get('sub_entries', []):
                # print(sub_entry)
                found_sub_entry = True
                date_str = sub_entry.get('datetime_str', 'No date').split(' - ')[0]
                title = sub_entry.get('title', 'No Title')
                is_hadir = sub_entry.get('is_attended', False)
                
                if is_hadir:
                    status_text = f"{Fore.GREEN}Hadir{Style.RESET_ALL}"
                else:
                    status_text = f"{Fore.RED}Belum Hadir{Style.RESET_ALL}"
                
                print(f"  - [{status_text}] {date_str} - {title}")
        
        if not found_sub_entry:
            print("  No sub-entries found for this program.")

    # --- 2. Check Assisted Programs (Program Bantu) ---
    print(f"\n{Fore.YELLOW}--- Program Bantu (PIC Assistance) ---{Style.RESET_ALL}")
    bantu_entries = get_bantu_pic_entries(session, programs[0]) # programs[0] is just to get a valid program context
    if not bantu_entries:
        print(f"{Fore.YELLOW}No assisted program entries found.{Style.RESET_ALL}")
        return

    for entry in bantu_entries:
        pic_name = entry.get('pic', 'Unknown PIC')
        print(f"\n{Fore.MAGENTA}PIC: {pic_name}{Style.RESET_ALL}")
        
        if not entry.get('sub_entries'):
            print("  No sub-entries found for this PIC.")
            continue

        for sub_entry in entry.get('sub_entries', []):
            # print(sub_entry)
            date_str = sub_entry.get('datetime_str', 'No date').split(' - ')[0]
            title = sub_entry.get('title', 'No Title')
            is_hadir = sub_entry.get('is_attended', False)

            if is_hadir:
                status_text = f"{Fore.GREEN}Hadir{Style.RESET_ALL}"
            else:
                status_text = f"{Fore.RED}Belum Hadir{Style.RESET_ALL}"
            
            print(f"  - [{status_text}] {date_str} - {title}")

    print("\n--- Attendance Check Complete ---")

def handle_change_account():
    print("Input username and password for SIMASTER:")
    username = input("Username: ").strip()
    password = getpass.getpass('Password:')
    if not username or not password:
        print("Username and password cannot be empty.")
        return
    session = get_simaster_session(username, password)
    if session:
        print(f"{Fore.GREEN}Login successful!{Style.RESET_ALL}")
    else:
        print(f"{Fore.RED}Login failed. Please check your credentials.{Style.RESET_ALL}")
    return session
def main():
    """Main function to run the interactive CLI."""
    username = os.getenv("SIMASTER_USERNAME")
    password = os.getenv("SIMASTER_PASSWORD")

    if not username or not password:
        print("Error: SIMASTER_USERNAME and SIMASTER_PASSWORD environment variables not set in .env file.")
        return

    print("--- Logging in to SIMASTER ---")
    session = get_simaster_session(username, password)
    if not session:
        print("Login failed. Exiting.")
        return

    while True:
        print("\n--- Malas KKN CLI ---")
        print("What would you like to do?")
        print("[1] Add New Logbook Entry (My Program)")
        print("[2] Add New Sub-Entry (My Program)")
        print("[3] Post Attendance for My Sub-Entry")
        print("[4] Manage PIC-Assisted Programs (Program Bantu)")
        print("[5] Generate Activity Timeline") 
        print("[6] Handle Attendance Check for All Programs")
        print("[7] Change Account")
        print("[8] Exit")
        
        choice = input("Enter your choice (1-8): ")

        if choice == '1':
            handle_add_logbook_entry(session)
        elif choice == '2':
            handle_create_sub_entry(session)
        elif choice == '3':
            handle_post_attendance(session)
        elif choice == '4':
            handle_bantu_pic(session)
        elif choice == '5': 
            handle_generate_timeline(session)
        elif choice == '6':
            handle_check_all_attendance(session)
            continue
        elif choice == '7':
            print("\nChanging account...")
            session = handle_change_account()
        elif choice == '8':
            print("Exiting. Sampai jumpa!")
            break
        else:
            print("Invalid choice. Please try again.")
        
        input("\nPress Enter to return to the main menu...")

if __name__ == "__main__":
    main()
