"""
This file contains the functions required to interact with UGM's SIMASTER.
The interactions include logging in, fetching academic schedules and posting
KKN (Kuliah Kerja Nyata) attendance
"""

import hashlib
import re
import json
from datetime import datetime
from typing import Dict, List, Optional 
import cachelib
import requests
from lxml.html.soupparser import fromstring
from lxml.html import tostring

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
            # cache for 2 days
            cache.set(key, ses, timeout=60 * 60 * 24 * 2)
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


def add_kkn_logbook_entry(
    ses: requests.Session, program: Dict, entry_title: str, entry_date: str, latitude: float, longitude: float
) -> bool:
    """
    Adds a new logbook entry.
    """
    print(f"\nAdding logbook entry for program: {program.get('program_nama', 'Unknown')}")
    try:
        action_html = program.get("action", "")
        rpp_url_match = re.search(r"href='([^']+logbook_program_rpp[^']+)'", action_html)
        if not rpp_url_match:
            print("Could not find RPP URL in program action.")
            return False
        rpp_url = rpp_url_match.group(1)
        print(f"Found RPP URL: {rpp_url}")

        rpp_page_req = ses.get(rpp_url)
        rpp_page_req.raise_for_status()
        add_link_match = re.search(r"<a href='([^']+)'.*?title='Tambah'>", rpp_page_req.text)
        if not add_link_match:
            print("Could not find 'Tambah' link on the RPP page.")
            return False
        add_page_url = add_link_match.group(1)
        print(f"Found 'Tambah' (Add) link: {add_page_url}")

        add_page_req = ses.get(add_page_url)
        add_page_req.raise_for_status()

        tree = fromstring(add_page_req.content)
        form = tree.find('.//form[@id="form-usulan-program"]')
        if form is None:
            print("Could not find the add form on the page.")
            return False
        action_url = form.get("action")
        hidden_inputs = form.xpath('.//input[@type="hidden"]')
        form_data = {inp.get("name"): inp.get("value") for inp in hidden_inputs}
        
        print(f"Found add-entry form token: {form_data.get('simasterUGM_token')}")
        
        form_data["dParam[judul]"] = entry_title
        form_data["dParam[pelaksanaan]"] = entry_date
        form_data["dParam[lokasi]"] = f"{latitude}, {longitude}"

        print("Submitting new logbook entry...")
        response = ses.post(action_url, data=form_data)
        response.raise_for_status()

        response_data = response.json()
        if response_data.get("status") == "success":
            print(f"Successfully added logbook entry: {response_data.get('msg')}")
            return True
        else:
            print(f"Failed to add logbook entry: {response_data.get('msg')}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred in add_kkn_logbook_entry: {e}")
        return False



def add_kkn_logbook_entry_by_id(
    ses: requests.Session, program_mhs_id: str, entry_title: str, entry_date: str, latitude: float, longitude: float
) -> bool:
    """add a logbook entry by its program_mhs_id."""
    programs = get_kkn_programs(ses)
    if not programs:
        print("Could not fetch programs list.")
        return False
    
    target_program = None
    for program in programs:
        if program.get("program_mhs_id") == program_mhs_id:
            target_program = program
            break

    if not target_program:
        print(f"Program with ID '{program_mhs_id}' not found.")
        print("Available programs:")
        for p in programs:
            print(f"  - ID: {p.get('program_mhs_id', 'No ID')}, Title: {p.get('program_mhs_judul', 'No name')}")
        return False

    return add_kkn_logbook_entry(ses, target_program, entry_title, entry_date, latitude, longitude)

def get_logbook_entries_by_id(ses: requests.Session, program_mhs_id: str) -> Optional[List[Dict]]:
    """
    Fetches the logbook entries (RPP) for a specific KKN program.
    """
    try:
        programs = get_kkn_programs(ses)
        if not programs:
            print("Could not fetch programs list to find the target program.")
            return None

        target_program = None
        for program in programs:
            if program.get("program_mhs_id") == program_mhs_id:
                target_program = program
                break
        
        if not target_program:
            print(f"Program with ID '{program_mhs_id}' not found in the program list.")
            return None

        action_html = target_program.get("action", "")
        rpp_url_match = re.search(r"href='([^']+logbook_program_rpp[^']+)'", action_html)
        if not rpp_url_match:
            print("Could not find RPP URL in program's action HTML.")
            return None
        rpp_url = rpp_url_match.group(1)
        print(f"\nFound RPP URL for program {program_mhs_id}: {rpp_url}")

        print("Accessing RPP page to parse HTML...")
        rpp_page_req = ses.get(rpp_url)
        rpp_page_req.raise_for_status()
        
        tree = fromstring(rpp_page_req.content)
        rows = tree.xpath('//table[@id="datatables2"]/tbody/tr')
        
        entries = []
        i = 0
        while i < len(rows):
            main_row = rows[i]
            cols = main_row.findall('td')

            # If it's not a main entry row, skip 
            if len(cols) != 5:
                i += 1
                continue
            
            # If it IS a main entry row, parse
            action_html_str = tostring(cols[4], pretty_print=True).decode('utf-8')
            kegiatan_match = re.search(r"href=['\"]([^'\"]*logbook_kegiatan[^'\"]*)['\"]", action_html_str)

            entry_data = {
                "entry_index": int(cols[0].text_content().strip()),
                "kegiatan_url": kegiatan_match.group(1) if kegiatan_match else None,
                "title": cols[1].text_content().strip(),
                "date": cols[2].text_content().strip(),
                "location": cols[3].text_content().strip(),
                "attendance_status": "Sudah Presensi", 
            }

            # look ahead for all consecutive sub-entry rows
            sub_entry_found = False
            j = i + 1
            while j < len(rows):
                sub_row = rows[j]
                sub_cols = sub_row.findall('td')
                # A sub-row has 2 columns, the first of which is empty
                if len(sub_cols) == 2 and not sub_cols[0].text_content():
                    sub_entry_found = True
                    # If we find even one sub-entry that is not attended, the whole entry is marked as such.
                    if "Belum Presensi" in sub_row.text_content():
                        entry_data["attendance_status"] = "Belum Presensi"
                    j += 1 # Move to the next potential sub-row
                else:
                    break
            
            # If no sub-entries were found at all, mark status as unknown or pending
            if not sub_entry_found:
                entry_data["attendance_status"] = "Belum Presensi"

            entries.append(entry_data)
            
            # Move the main index 'i' past all the rows we just processed
            i = j
        print(f"Found and parsed {len(entries)} entries from the HTML.")
        return entries

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching logbook entries: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred in get_logbook_entries_by_id: {e}")
        return None

'''
BUG: You cannot add a sub entry if the program already have 2 sub entries for some reason, this should not matter since ideally you would just create a new entry
'''
def create_sub_entry(ses: requests.Session, main_entry: Dict, sub_entry_title: str, description_text: str, duration: int) -> bool:
    """
    Creates a new sub-entry (kegiatan) under a main logbook entry.
    """
    try:
        kegiatan_url = main_entry.get("kegiatan_url")
        if not kegiatan_url:
            print("Selected main entry is missing the 'kegiatan_url'. Cannot proceed.")
            return False

        print(f"\nAccessing 'Kegiatan' page for entry '{main_entry.get('title')}': {kegiatan_url}")
        kegiatan_page_req = ses.get(kegiatan_url)
        kegiatan_page_req.raise_for_status()

        add_form_url_match = re.search(r"<a href='([^']+)'.*?title='Tambah'>", kegiatan_page_req.text)
        if not add_form_url_match:
            print("Could not find 'Tambah' link on the 'Kegiatan' page.")
            return False
        
        add_form_url = add_form_url_match.group(1)
        print(f"Found 'Tambah' form URL: {add_form_url}")

        print("Accessing form page...")
        form_page_req = ses.get(add_form_url)
        form_page_req.raise_for_status()

        tree = fromstring(form_page_req.content)
        form = tree.find('.//form')
        if form is None:
            print("Could not find the sub-entry form on the page.")
            return False

        action_url = form.get("action")
        hidden_inputs = form.xpath('.//input[@type="hidden"]')
        form_data = {inp.get("name"): inp.get("value") for inp in hidden_inputs}

        print(f"Found form token: {form_data.get('simasterUGM_token')}")

        form_data["dParam[judul]"] = sub_entry_title
        form_data["dParam[pelaksanaan]"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        form_data["dParam[durasi]"] = str(duration)
        form_data["dParam[deskripsi]"] = description_text
        form_data["dParam[sasaran]"] = "-"
        form_data["dParam[jumPeserta]"] = "0"
        form_data["dParam[sumberDana]"] = "1"
        form_data["dParam[sumberDanaLain]"] = ""
        form_data["dParam[jumDana]"] = "0"
        form_data["dParam[hasilKegiatan]"] = "Kegiatan terlaksana dengan baik."

        print("Submitting form to create sub-entry...")
        response = ses.post(action_url, data=form_data)
        response.raise_for_status()
        
        
        try:
            response_json = response.json()
            if response_json.get("status") == "success":
                print(f"Successfully created new sub-entry: {response_json.get('msg')}")
                return True
            else:
                print(f"Failed to create sub-entry. Server response: {response_json}")
                return False
        except json.JSONDecodeError:
             
            if response.status_code == 200:
                print("Successfully created new sub-entry (judging by status code).")
                return True
            print(f"Failed to create sub-entry and response was not valid JSON.")
            return False

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while creating sub-entry: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred in create_sub_entry: {e}")
        return False

"""
it works now
"""

def post_attendance_for_sub_entry(ses: requests.Session, program_mhs_id: str, main_entry_index: int, sub_entry_title_to_find: str, latitude: float, longitude: float) -> bool:
    """
    Finds a specific sub-entry and posts attendance using a specific token
    captured from the RPP page response.
    """
    try:
        
        programs = get_kkn_programs(ses)
        if not programs: return False
        target_program = next((p for p in programs if p.get("program_mhs_id") == program_mhs_id), None)
        if not target_program:
            print(f"Program with ID '{program_mhs_id}' not found.")
            return False
        action_html = target_program.get("action", "")
        rpp_url_match = re.search(r"href='([^']+logbook_program_rpp[^']+)'", action_html)
        if not rpp_url_match: return False
        rpp_url = rpp_url_match.group(1)
        
        print(f"\nAccessing RPP page for program {program_mhs_id}...")
        rpp_page_req = ses.get(rpp_url)
        rpp_page_req.raise_for_status()

        page_token = rpp_page_req.cookies.get('simasterUGM_cookie')
        if not page_token:
            print("ERROR: Could not find 'simasterUGM_cookie' in the RPP page response. Trying session cookie as fallback.")
            page_token = ses.cookies.get('simasterUGM_cookie')
            if not page_token:
                 print("Fallback failed. Cannot find a valid token.")
                 return False
        print(f"Successfully captured page token: {page_token}")

        tree = fromstring(rpp_page_req.content)
        rows = tree.xpath('//table[@id="datatables2"]/tbody/tr')

        i = 0
        while i < len(rows):
            main_row = rows[i]
            cols = main_row.findall('td')

            if len(cols) != 5:
                i += 1
                continue
            
            if int(cols[0].text_content().strip()) != main_entry_index:
                i += 1
                continue
            
            print(f"Found main entry #{main_entry_index}. Searching for sub-entry '{sub_entry_title_to_find}'...")
            j = i + 1
            while j < len(rows):
                sub_row = rows[j]
                if len(sub_row.findall('td')) != 2: break

                if sub_entry_title_to_find in sub_row.text_content():
                    print("Found target sub-entry row.")
                    
                    presensi_buttons = sub_row.xpath(".//a[contains(., 'Presensi')]")
                    if not presensi_buttons:
                        print("No 'Presensi' button available.")
                        return False
                    presensi_button = presensi_buttons[0]

                    ajaxify_url = presensi_button.get('ajaxify')
                    if not ajaxify_url:
                        print("ERROR: 'Presensi' button has no 'ajaxify' URL.")
                        return False
                    
                    url_parts = [part for part in ajaxify_url.split('/') if part]
                    
                    
                    payload = {
                        "timelineId": url_parts[-5],
                        "rppJenisProgram": url_parts[-4],
                        "rppMhsId": url_parts[-3],
                        "kegiatanMhsId": url_parts[-2],
                        "programMhsId": url_parts[-1],
                        "agreement": "1",
                        "latitude": str(latitude),
                        "longtitude": str(longitude),
                        "simasterUGM_token": page_token
                    }
                    
                    action_url = f"{BASE_URL}/kkn/kkn/logbook_kegiatan_presensi"
                    print("Submitting attendance request...")
                    response = ses.post(action_url, data=payload)
                    response.raise_for_status()
                    
                    response_json = response.json()
                    if response_json.get("status") == "success":
                        print(f"SUCCESS: {response_json.get('msg')}")
                        return True
                    else:
                        print(f"FAILED: Server response: {response_json.get('msg')}")
                        return False
                j += 1
            
            print(f"Error: Could not find sub-entry '{sub_entry_title_to_find}'.")
            return False
        
        print(f"Error: Could not find main entry #{main_entry_index}.")
        return False

    except Exception as e:
        print(f"An unexpected error occurred in post_attendance_for_sub_entry: {e}")
        return False

