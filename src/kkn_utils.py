import os
from datetime import datetime
from dotenv import load_dotenv
from src.simaster import get_simaster_session, get_kkn_programs


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
            print(f"  {i+1}. Code: {program.get('program_mhs_id', 'N/A')}, Title: {program.get('program_mhs_judul', 'N/A')}")
    else:
        print("No KKN programs found or failed to retrieve them.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Utilities for KKN SIMASTER interactions.")
    parser.add_argument("command", choices=["list-programs", "add-logbook-entry"], help="Command to execute")

    """unused parsing from an untested functions (not pushed)"""
   # parser.add_argument("--program-code", help="KKN Program code for adding logbook entry (e.g., 02:06:06)")
    #parser.add_argument("--title", help="Title of the logbook entry")
    #parser.add_argument("--date", help="Date of the logbook entry (DD-MM-YYYY)")

    args = parser.parse_args()

    if args.command == "list-programs":
        list_kkn_programs()

      
