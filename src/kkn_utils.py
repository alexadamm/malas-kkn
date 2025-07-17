import os
from datetime import datetime
from dotenv import load_dotenv
from .utils import generate_random_point
from src import generative
from src.simaster import (
    get_simaster_session, 
    get_kkn_programs, 
    get_logbook_entries_by_id,
    get_sub_entries_for_main_entry,
    create_sub_entry,
    add_kkn_logbook_entry_by_id,
    post_attendance_for_sub_entry
)

load_dotenv()

# --- Helper Functions for Interactive Selection ---

def select_program(session):
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
    """Lists sub-entries and prompts the user to select one."""
    print(f"\nFetching sub-entries for '{main_entry.get('title')}'...")
    sub_entries = get_sub_entries_for_main_entry(session, main_entry)
    if not sub_entries:
        print("No sub-entries found for this main entry.")
        return None
    
    unattended_entries = [se for se in sub_entries if not se.get('is_attended')]
    if not unattended_entries:
        print("All sub-entries have already been attended.")
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
            print(f"  - [{entry.get('entry_index')}] {entry.get('title')} on {entry.get('date')}")
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

def handle_create_sub_entry(session):
    """Guides user to create a new sub-entry, with optional AI generation."""
    program = select_program(session)
    if not program:
        return
    
    program_mhs_id = program.get("program_mhs_id")
    proker_title = program.get("program_mhs_judul", "Judul Proker Tidak Ditemukan")

    main_entry = select_main_entry(session, program_mhs_id)
    if not main_entry:
        return

    sub_entry_title = input("\nEnter the title for the new sub-entry (kegiatan): ")
    duration_str = input("Enter the duration in minutes (default: 60): ") or "60"
    duration = int(duration_str)

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

    success = create_sub_entry(
        session, main_entry, sub_entry_title, 
        description_text, hasil_kegiatan_text, duration,
        pelaksanaan_datetime_str, sasaran, jumPeserta, jumDana
    )

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
        print("[1] Add New Logbook Entry (Main Entry)")
        print("[2] Add New Sub-Entry (Kegiatan)")
        print("[3] Post Attendance for a Sub-Entry")
        print("[4] Exit")
        
        choice = input("Enter your choice (1-4): ")

        if choice == '1':
            handle_add_logbook_entry(session)
        elif choice == '2':
            handle_create_sub_entry(session)
        elif choice == '3':
            handle_post_attendance(session)
        elif choice == '4':
            print("Exiting. Sampai jumpa!")
            break
        else:
            print("Invalid choice. Please try again.")
        
        input("\nPress Enter to return to the main menu...")

if __name__ == "__main__":
    main()
