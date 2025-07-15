"""
This file contains the functions required to interact with UGM's SIMASTER.
The interactions include logging in, fetching academic schedules and posting
KKN (Kuliah Kerja Nyata) attendance
"""

import hashlib
import re
from datetime import datetime

import cachelib
import requests
from lxml.html.soupparser import fromstring

BASE_URL = "https://simaster.ugm.ac.id"
HOME_URL = f"{BASE_URL}/beranda"
LOGIN_URL = f"{BASE_URL}/services/simaster/service_login"

cache = cachelib.SimpleCache()


def get_cache_key(username: str, password: str) -> str:
    """Creates a unique cache key from username and password."""
    return hashlib.md5(f"{username}:{password}".encode()).hexdigest()


def get_simaster_session(
    username: str, password: str, reuse_session: bool = True
) -> requests.Session | None:
    """
    Logs in to SIMASTER, then return a `Session` object if success.
    Returns `None` if failed. Utilizes caching to reuse valid sessions.
    """
    # 1. try to get a valid session from the cache
    key = get_cache_key(username, password)
    if reuse_session:
        ses = cache.get(key)
        if ses:
            print("Found cached session. Validating...")
            # validate session by checking if we can access the homepage
            # and find a csrf token, which indicates were logged in
            try:
                req = ses.get(HOME_URL, timeout=10)
                if req.status_code == 200 and "simasterUGM_token" in req.text:
                    print("Cached session is valid.")
                    return ses
                else:
                    print("Cached session is invalid or expired.")
            except requests.exceptions.RequestException as e:
                print(f"Failed to validate cached session: {e}")

    # 2. if no valid cached session, create a new one
    print("Attempting a new login...")
    ses = requests.Session()
    login_data = {"aId": "", "username": username, "password": password}
    try:
        req = ses.post(LOGIN_URL, data=login_data)
        # print(f"--- Raw Server Response ---\n{req.text}\n--------------------------")
        req.raise_for_status()

        response_json = req.json()
        if response_json.get("isLogin") == 1:
            print(f"Successfully logged in as {response_json.get('namaLengkap')}.")
            cache.set(key, ses, timeout=86400)
            return ses
        else:
            print("Login failed. Please check your username and password.")
            return None

    except requests.exceptions.RequestException as e:
        print(f"An error occurred during login: {e}")
        return None


def post_kkn_presensi(
    ses: requests.Session, latitude: float, longitude: float, tanggal_presensi: str
) -> bool:
    """
    Posts KKN attendance for a specific date.

    This function scrapes the required `simasterUGM_token`, posts the attendance,
    and then checks the JSON response for a success status.
    """
    presensi_url = f"{BASE_URL}/kkn/presensi/add"
    print(f"\nAccessing KKN attendance page at {presensi_url}...")

    try:
        # get csrf token
        page_req = ses.get(presensi_url)
        page_req.raise_for_status()

        token_match = re.search(r'name="simasterUGM_token" value="(.+?)"', page_req.text)
        if not token_match:
            print("Could not find simasterUGM_token on the KKN page.")
            return False
        token = token_match.group(1)
        print(f"Found KKN page simasterUGM_token: {token}")

        presensi_data = {
            "simasterUGM_token": token,
            "tanggalPresensi": tanggal_presensi,
            "agreement": "1",
            "latitude": str(latitude),
            "longtitude": str(longitude),
        }

        print(f"Posting attendance for {tanggal_presensi}...")
        response = ses.post(presensi_url, data=presensi_data)
        response.raise_for_status()

        # print(f"--- Raw Server Response ---\n{response.text}\n--------------------------")

        try:
            # a successful post returns a json object. (so far i think so)
            response_json = response.json()
            if response_json.get("status") == "success":
                print(f"Success message from server: {response_json.get('msg')}")
                return True
            else:
                print(f"Post failed. Server response: {response_json}")
                return False
        except requests.exceptions.JSONDecodeError:
            # a failed post (e.g., already attended) returns an html page. (so far i think so)
            # parsing the HTML to extract the error message
            print("Post failed. Did not receive a valid JSON response from the server.")
            tree = fromstring(response.text)
            error_node = tree.find('.//div[@class="note note-danger"]')
            if error_node is not None:
                error_message = error_node.text_content().strip()
                print(f"Error message found in HTML: '{error_message}'")
            return False

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while posting attendance: {e}")
        return False
