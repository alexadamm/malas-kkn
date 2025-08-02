import random
import math
from datetime import datetime, timedelta


def generate_random_point(lat, lon, radius_m):
    """
    Generates a random GPS coordinate within a given radius of a starting point.

    Args:
        lat (float): The latitude of the center point.
        lon (float): The longitude of the center point.
        radius_m (int): The radius in meters.

    Returns:
        tuple: A tuple containing the new latitude and longitude.
    """
    earth_radius = 6378137.0 # (WGS84 spheroid)

    # --- convert radius from meters to degrees ---

    # offset in radians
    random_dist = math.sqrt(random.random()) * radius_m
    
    # random angle in radians
    random_angle = 2 * math.pi * random.random()

    # calculate the change in latitude (north-south direction)
    # the distance for a degree of latitude is relatively constant.
    delta_lat_rad = (random_dist / earth_radius) * math.sin(random_angle)

    # calculate the change in longitude (east-west direction)
    # the distance for a degree of longitude depends on the latitude.
    # we need to account for the earth's curvature.
    delta_lon_rad = (random_dist / (earth_radius * math.cos(math.radians(lat)))) * math.cos(random_angle)

    # convert radian offsets to degree offsets
    delta_lat_deg = math.degrees(delta_lat_rad)
    delta_lon_deg = math.degrees(delta_lon_rad)

    # add the offsets to the original point
    new_lat = lat + delta_lat_deg
    new_lon = lon + delta_lon_deg

    return (new_lat, new_lon)

# the time window in which attendance should be posted (24-hour format).
# the script will pick a random time between these hours.

RUN_WINDOW_START_HOUR = 4  # 5 AM
RUN_WINDOW_END_HOUR = 10 # 10 AM

def get_next_run_time() -> datetime:
    """
    Calculates the next random execution time to ensure it runs ONCE per day.

    If the current time is before the start of today's window, it schedules
    for today. Otherwise, it always schedules for tomorrow to prevent multiple
    runs on the same day.

    Returns:
        A datetime object representing the next scheduled run time.
    """
    now = datetime.now()
    today_run_window_start = now.replace(
        hour=RUN_WINDOW_START_HOUR, minute=0, second=0, microsecond=0
    )

    # if the current time is already within or past today's run window,
    # we must schedule for the next day to guarantee a single run per day.
    if now >= today_run_window_start:
        target_day = now + timedelta(days=1)
        print("Scheduling for tomorrow to ensure a single run per day...")
    else:
        # if it's early in the morning before the window starts, schedule for today.
        target_day = now
        print("Scheduling for today...")

    # pick a random time within the window for the target day.
    random_hour = random.randint(RUN_WINDOW_START_HOUR, RUN_WINDOW_END_HOUR - 1)
    random_minute = random.randint(0, 59)
    random_second = random.randint(0, 59)

    next_time = target_day.replace(
        hour=random_hour, minute=random_minute, second=random_second, microsecond=0
    )

    return next_time

