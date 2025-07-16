"""
This file contains the functions required to interact with UGM's SIMASTER.
The interactions include logging in, fetching academic schedules and posting
KKN (Kuliah Kerja Nyata) attendance
"""

import hashlib
import re
import json
from typing import Dict, List, Optional

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
            try:
                req = ses.get(HOME_URL, timeout=10)
                if req.status_code == 200:
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

        try:
            # a successful post returns a json object.
            response_json = response.json()
            if response_json.get("status") == "success":
                print(f"Success message from server: {response_json.get('msg')}")
                return True
            else:
                print(f"Post failed. Server response: {response_json}")
                return False
        except requests.exceptions.JSONDecodeError:
            # a failed post (e.g., already attended) returns an html page.
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


def get_kkn_programs(ses: requests.Session) -> Optional[List[Dict]]:
    """
    Fetches the list of KKN programs by navigating through the KKN pages
    and using a CSRF token from the session cookie.
    """
    try:
        
        print("\nAccessing KKN main page to find logbook URL...")
        kkn_main_url = f"{BASE_URL}/kkn/kkn/"
        main_page_req = ses.get(kkn_main_url)
        main_page_req.raise_for_status()

        logbook_page_url_match = re.search(
            r"<a href=['\"]([^'\"]*logbook_program[^'\"]*)['\"][^>]*>.*?Pelaksanaan Program.*?</a>",
            main_page_req.text,
            re.IGNORECASE | re.DOTALL,
        )
        if not logbook_page_url_match:
            print("Could not find 'Pelaksanaan Program' link on the KKN main page.")
            return None
        logbook_page_url = logbook_page_url_match.group(1)
        if not logbook_page_url.startswith("http"):
            logbook_page_url = f"{BASE_URL}{logbook_page_url.lstrip('/')}"
        print(f"Found logbook page URL: {logbook_page_url}")

        print(f"Accessing logbook page to set session cookie and get data URL...")
        page_req = ses.get(logbook_page_url)
        page_req.raise_for_status()

        # get CSRF token from the session's cookie.
        token = ses.cookies.get('simasterUGM_cookie')
        if not token:
            print("Could not find 'simasterUGM_cookie' in the session after visiting the logbook page.")
            return None
        print(f"Found CSRF token in session cookie: {token}")

        # parse data URL.
        data_url_match = re.search(
            r"'url'\s*:\s*[\"'](https://simaster\.ugm\.ac\.id/kkn/kkn/logbook_program_data/[^\"']+)",
            page_req.text,
        )
        if not data_url_match:
            print("Could not find data URL in logbook page's JavaScript.")
            return None
        data_url = data_url_match.group(1)
        print(f"Found data URL: {data_url}")

        #POST request to get proker's table.
        post_data = {
            "draw": "1", "start": "0", "length": "25",
            "search[value]": "", "search[regex]": "false", "dt": "{}",
            "simasterUGM_token": token,
            "columns[0][data]": "no", "columns[0][name]": "", "columns[0][searchable]": "false", "columns[0][orderable]": "false", "columns[0][search][value]": "", "columns[0][search][regex]": "false",
            "columns[1][data]": "program_nama", "columns[1][name]": "", "columns[1][searchable]": "true", "columns[1][orderable]": "true", "columns[1][search][value]": "", "columns[1][search][regex]": "false",
            "columns[2][data]": "program_mhs_judul", "columns[2][name]": "", "columns[2][searchable]": "true", "columns[2][orderable]": "true", "columns[2][search][value]": "", "columns[2][search][regex]": "false",
            "columns[3][data]": "program_jenis_id", "columns[3][name]": "", "columns[3][searchable]": "true", "columns[3][orderable]": "true", "columns[3][search][value]": "", "columns[3][search][regex]": "false",
            "columns[4][data]": "program_mhs_keberlanjutan", "columns[4][name]": "", "columns[4][searchable]": "true", "columns[4][orderable]": "true", "columns[4][search][value]": "", "columns[4][search][regex]": "false",
            "columns[5][data]": "status_nama", "columns[5][name]": "", "columns[5][searchable]": "true", "columns[5][orderable]": "true", "columns[5][search][value]": "", "columns[5][search][regex]": "false",
            "columns[6][data]": "action", "columns[6][name]": "", "columns[6][searchable]": "false", "columns[6][orderable]": "false", "columns[6][search][value]": "", "columns[6][search][regex]": "false",
        }
        headers = {"X-Requested-With": "XMLHttpRequest"}

        print("Fetching program data with full DataTables payload...")
        data_req = ses.post(data_url, data=post_data, headers=headers)
        data_req.raise_for_status()

        programs_data = data_req.json()
        
        
        new_token = programs_data.get('csrf_value')
        if new_token:
            ses.cookies.set('simasterUGM_cookie', new_token)
            print(f"Updated session with new CSRF token: {new_token}")

        programs = programs_data.get("data", [])
        print(f"Found {len(programs)} programs.")
        return programs

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching programs: {e}")
        return None
    except json.JSONDecodeError:
        print("Failed to decode JSON from the server response.")
        print("Response Text:", data_req.text)
        return None
    except Exception as e:
        print(f"An unexpected error occurred in get_kkn_programs: {e}")
        return None



