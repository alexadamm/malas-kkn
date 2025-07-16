import os
from datetime import datetime
from dotenv import load_dotenv
from .utils import generate_random_point
from src.simaster import (
    get_simaster_session, 
    get_kkn_programs, 
    get_logbook_entries_by_id,
    create_sub_entry,
    add_kkn_logbook_entry_by_id
)

load_dotenv()

def list_kkn_programs():
    username = os.getenv("SIMASTER_USERNAME")
    password = os.getenv("SIMASTER_PASSWORD")
    if not username or not password:
        print("Error: SIMASTER_USERNAME and SIMASTER_PASSWORD environment variables not set.")
        return
    session = get_simaster_session(username, password)
    if not session:
        print("Login failed. Exiting.")
        return

    print("\nListing KKN programs...")
    programs = get_kkn_programs(session)
    if programs:
        print("Available KKN Programs:")
        for i, program in enumerate(programs):
            print(f"  {i+1}. ID: {program.get('program_mhs_id', 'N/A')}, Title: {program.get('program_mhs_judul', 'N/A')}")
    else:
        print("No KKN programs found or failed to retrieve them.")

def add_logbook_entry(program_mhs_id: str, title: str, date: str):
    username = os.getenv("SIMASTER_USERNAME")
    password = os.getenv("SIMASTER_PASSWORD")
    
    try:
        latitude = float(os.getenv("KKN_LOCATION_LATITUDE"))
        longitude = float(os.getenv("KKN_LOCATION_LONGITUDE"))
    except (TypeError, ValueError):
        print("Error: KKN_LOCATION_LATITUDE and KKN_LOCATION_LONGITUDE environment variables not set or invalid.")
        return

    if not all([username, password]):
        print("Error: SIMASTER_USERNAME and SIMASTER_PASSWORD environment variables not set.")
        return

    session = get_simaster_session(username, password)
    if not session:
        print("Login failed. Exiting.")
        return

    random_lat, random_lon = generate_random_point(latitude, longitude, 50)
    print(f"Generated random point for logbook: (Lat: {random_lat}, Lon: {random_lon})")

    success = add_kkn_logbook_entry_by_id(
        session, program_mhs_id, title, date, random_lat, random_lon
    )
    
    if success:
        print("\nLogbook entry added successfully.")
    else:
        print("\nFailed to add logbook entry.")

def list_entries(program_mhs_id: str):
    username = os.getenv("SIMASTER_USERNAME")
    password = os.getenv("SIMASTER_PASSWORD")
    if not username or not password:
        print("Error: SIMASTER_USERNAME and SIMASTER_PASSWORD environment variables not set.")
        return
    session = get_simaster_session(username, password)
    if not session:
        print("Login failed. Exiting.")
        return

    print(f"\nListing logbook entries for Program ID: {program_mhs_id}...")
    entries = get_logbook_entries_by_id(session, program_mhs_id)
    
    if entries:
        print("Available Logbook Entries:")
        for entry in entries:
            print(f"  {entry.get('entry_index')}. Title: {entry.get('title')}, Status: {entry.get('attendance_status')}")
    else:
        print("No logbook entries found for this program or failed to retrieve them.")


def run_create_sub_entry(program_mhs_id: str, entry_index: int, sub_entry_title: str, duration: int):
    username = os.getenv("SIMASTER_USERNAME")
    password = os.getenv("SIMASTER_PASSWORD")

    if not all([username, password]):
        print("Error: SIMASTER_USERNAME and SIMASTER_PASSWORD environment variables not set.")
        return

    try:
        with open("description.txt", "r", encoding="utf-8") as f:
            description_text = f.read()
    except FileNotFoundError:
        print("Error: 'description.txt' not found. Please create it in the same directory.")
        return

    session = get_simaster_session(username, password)
    if not session:
        print("Login failed. Exiting.")
        return

    print(f"\nFetching entries for program {program_mhs_id} to find entry number {entry_index}...")
    entries = get_logbook_entries_by_id(session, program_mhs_id)
    if not entries:
        print("Could not fetch entries. Cannot create sub-entry.")
        return

    target_entry = None
    for entry in entries:
        if entry.get("entry_index") == entry_index:
            target_entry = entry
            break

    if not target_entry:
        print(f"Could not find entry number {entry_index}. Please check the entry list.")
        return

    success = create_sub_entry(session, target_entry, sub_entry_title, description_text, duration)

    if success:
        print("\nSub-entry created successfully.")
    else:
        print("\nFailed to create sub-entry.")


def run_post_attendance(program_mhs_id: str, entry_index: int, sub_entry_title: str):
    username = os.getenv("SIMASTER_USERNAME")
    password = os.getenv("SIMASTER_PASSWORD")

    session = get_simaster_session(username, password)
    if not session:
        print("Login failed. Exiting.")
        return

    print(f"\nFetching entries for program {program_mhs_id} to find main entry number {entry_index}...")
    entries = get_logbook_entries_by_id(session, program_mhs_id)
    if not entries:
        print("Could not fetch entries. Cannot post attendance.")
        return

    target_main_entry = None
    for entry in entries:
        if entry.get("entry_index") == entry_index:
            target_main_entry = entry
            break
    
    if not target_main_entry:
        print(f"Could not find main entry number {entry_index}.")
        return

    success = post_attendance_for_sub_entry(session, target_main_entry, sub_entry_title)

    if success:
        print("\nAttendance posted successfully for sub-entry.")
    else:
        print("\nFailed to post attendance for sub-entry.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Utilities for KKN SIMASTER interactions.")
    parser.add_argument("command", choices=["list-programs", "list-entries","add-logbook-entry" ,"create-sub-entry", "post-attendance"], help="Command to execute")

    parser.add_argument("--program-id", help="KKN Program ID (e.g., 203341)")
    parser.add_argument("--title", help="Title of the logbook entry")
    parser.add_argument("--date", help="Date of the logbook entry (DD-MM-YYYY). Defaults to today.")
    parser.add_argument("--entry-index", type=int, help="The order of the main entry in the list (e.g., 1, 2, 3...)")
    parser.add_argument("--sub-entry-title", help="The title for the new sub-entry (e.g., 'Turu')")
    parser.add_argument("--duration", type=int, default=2, help="Duration of the activity in minutes (default: 60)")

    args = parser.parse_args()

    if args.command == "list-programs":
        list_kkn_programs()
    
    elif args.command == "list-entries":
        if not args.program_id:
            parser.error("For 'list-entries', --program-id is required.")
        list_entries(args.program_id)
     
    
    elif args.command == "add-logbook-entry":
        if not all([args.program_id, args.title]):
            parser.error("For 'add-logbook-entry', --program-id and --title are required.")
        
        entry_date = args.date if args.date else datetime.now().strftime("%d-%m-%Y")
        
        add_logbook_entry(args.program_id, args.title, entry_date)
    
    elif args.command == "create-sub-entry":
        if not all([args.program_id, args.entry_index, args.sub_entry_title]):
            parser.error("For 'create-sub-entry', --program-id, --entry-index, and --sub_entry_title are required.")
        run_create_sub_entry(args.program_id, args.entry_index, args.sub_entry_title, args.duration)
    
    elif args.command == "post-attendance":
        if not all([args.program_id, args.entry_index, args.sub_entry_title]):
            parser.error("For 'post-attendance', --program-id, --entry-index, and --sub_entry_title (of the sub-entry) are required.")
        run_post_attendance(args.program_id, args.entry_index, args.sub_entry_title)
