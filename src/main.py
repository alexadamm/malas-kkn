import os
import random
import time

from .simaster import get_simaster_session, post_kkn_presensi
from .utils import generate_random_point, get_next_run_time
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

def main():
    print("--- KKN Attendance Server Starting ---")

    # load envs
    username = os.getenv("SIMASTER_USERNAME")
    password = os.getenv("SIMASTER_PASSWORD")

    KKN_LOCATION_LATITUDE = float(os.getenv("KKN_LOCATION_LATITUDE"))
    KKN_LOCATION_LONGITUDE = float(os.getenv("KKN_LOCATION_LONGITUDE"))
    KKN_LOCATION_RADIUS_METERS = int(os.getenv("KKN_LOCATION_RADIUS_METERS")) # radius in meters for random point generation

    if not username or not password:
        print("Error: SIMASTER_USERNAME and SIMASTER_PASSWORD environment variables not set.")
        return

    # --- initial login ---
    # the session will be reused for all subsequent attendance posts (cos i found no expiration so far)
    session = get_simaster_session(username, password)
    if not session:
        print("Login failed. Exiting server.")
        return

    print("\nLogin successful. Starting scheduling loop...")

    def submit_kkn_attendance():
        random_lat, random_lon = generate_random_point(
            KKN_LOCATION_LATITUDE,
            KKN_LOCATION_LONGITUDE,
            KKN_LOCATION_RADIUS_METERS,
        )
        print(f"Generated random point: (Lat: {random_lat}, Lon: {random_lon})")

        tanggal_presensi = datetime.now().strftime("%d-%m-%Y")

        success = post_kkn_presensi(session, random_lat, random_lon, tanggal_presensi)

        if success:
            print("Attendance task completed successfully.")
        else:
            print("Attendance task failed. Check logs for details.")
        
        print("="*40 + "\n")

    # --- initial attendance post (to ensure at least you've attended now)
    submit_kkn_attendance()


    # --- main scheduling loop ---
    while True:
        next_run = get_next_run_time()
        sleep_duration = (next_run - datetime.now()).total_seconds()

        if sleep_duration > 0:
            print(f"Next attendance post scheduled for: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"Sleeping for {sleep_duration:.2f} seconds...")
            time.sleep(sleep_duration)

        print("\n" + "="*40)
        print(f"Waking up at {datetime.now()} to post attendance.")

        submit_kkn_attendance()
        
        time.sleep(60)


if __name__ == "__main__":
    main()
