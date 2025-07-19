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
        
        page_req = ses.get(logbook_page_url)
        page_req.raise_for_status()

        # --- FIX for multiple cookies ---
        # Instead of using .get(), iterate to find the last (most specific) cookie value
        token = None
        for cookie in ses.cookies:
            if cookie.name == 'simasterUGM_cookie':
                token = cookie.value
        
        if not token:
            print("Could not find 'simasterUGM_cookie' in the session after visiting the logbook page.")
            return None

        data_url_match = re.search(
            r"'url'\s*:\s*[\"'](https://simaster\.ugm\.ac\.id/kkn/kkn/logbook_program_data/[^\"']+)",
            page_req.text,
        )
        if not data_url_match:
            print("Could not find data URL in logbook page's JavaScript.")
            return None
        data_url = data_url_match.group(1)

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

        data_req = ses.post(data_url, data=post_data, headers=headers)
        data_req.raise_for_status()

        programs_data = data_req.json()
        
        new_token = programs_data.get('csrf_value')
        if new_token:
            ses.cookies.set('simasterUGM_cookie', new_token)

        programs = programs_data.get("data", [])
        return programs

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching programs: {e}")
        return None
    except json.JSONDecodeError:
        print("Failed to decode JSON from the server response.")
        return None
    except Exception as e:
        # This will now catch other errors, but the specific cookie error should be gone.
        print(f"An unexpected error occurred in get_kkn_programs: {e}")
        return None


def add_kkn_logbook_entry(
    ses: requests.Session, program: Dict, entry_title: str, entry_date: str, latitude: float, longitude: float
) -> bool:
    """
    Adds a new logbook entry.
    """
    try:
        action_html = program.get("action", "")
        rpp_url_match = re.search(r"href='([^']+logbook_program_rpp[^']+)'", action_html)
        if not rpp_url_match:
            print("Could not find RPP URL in program action.")
            return False
        rpp_url = rpp_url_match.group(1)

        rpp_page_req = ses.get(rpp_url)
        rpp_page_req.raise_for_status()
        add_link_match = re.search(r"<a href='([^']+)'.*?title='Tambah'>", rpp_page_req.text)
        if not add_link_match:
            print("Could not find 'Tambah' link on the RPP page.")
            return False
        add_page_url = add_link_match.group(1)

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
        
        form_data["dParam[judul]"] = entry_title
        form_data["dParam[pelaksanaan]"] = entry_date
        form_data["dParam[lokasi]"] = f"{latitude}, {longitude}"

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
        return False

    return add_kkn_logbook_entry(ses, target_program, entry_title, entry_date, latitude, longitude)

def get_logbook_entries_by_id(ses: requests.Session, program_mhs_id: str) -> Optional[List[Dict]]:
    """
    Fetches the logbook entries (RPP) for a specific KKN program, including detailed sub-entries.
    """
    try:
        programs = get_kkn_programs(ses)
        if not programs:
            print("Could not fetch programs list to find the target program.")
            return None

        target_program = next((p for p in programs if p.get("program_mhs_id") == program_mhs_id), None)
        
        if not target_program:
            print(f"Program with ID '{program_mhs_id}' not found in the program list.")
            return None

        action_html = target_program.get("action", "")
        rpp_url_match = re.search(r"href='([^']+logbook_program_rpp[^']+)'", action_html)
        if not rpp_url_match:
            print("Could not find RPP URL in program's action HTML.")
            return None
        rpp_url = rpp_url_match.group(1)

        rpp_page_req = ses.get(rpp_url)
        rpp_page_req.raise_for_status()
        
        tree = fromstring(rpp_page_req.content)
        rows = tree.xpath('//table[@id="datatables2"]/tbody/tr')
        
        entries = []
        i = 0
        while i < len(rows):
            main_row = rows[i]
            cols = main_row.findall('td')

            # This is a main entry row
            if len(cols) == 5:
                action_html_str = tostring(cols[4], pretty_print=True).decode('utf-8')
                kegiatan_match = re.search(r"href=['\"]([^'\"]*logbook_kegiatan[^'\"]*)['\"]", action_html_str)

                entry_data = {
                    "entry_index": int(cols[0].text_content().strip()),
                    "kegiatan_url": kegiatan_match.group(1) if kegiatan_match else None,
                    "title": cols[1].text_content().strip(),
                    "date": cols[2].text_content().strip(),
                    "location": cols[3].text_content().strip(),
                    "sub_entries": []
                }

                # Look ahead for all consecutive sub-entry rows
                all_sub_attended = False
                notattendedflag = True
                sub_entry_found = False
                j = i + 1
                while j < len(rows):
                    sub_row = rows[j]
                    sub_cols = sub_row.findall('td')
                    if len(sub_cols) == 2 and not sub_cols[0].text_content().strip():
                        full_text = ' '.join(sub_cols[1].text_content().split())
                        is_attended = "Sudah Presensi" in full_text
                        if is_attended and notattendedflag:
                            all_sub_attended = True
                        elif not is_attended:
                            notattendedflag = False
                        # More powerful regex to capture title, datetime, and duration
                        sub_entry_pattern = re.compile(
                            r'^(?P<title>.*?)\s+'
                            r'\((?P<datetime_str>.*? \d{2}:\d{2}.*?)\)\s+'
                            r'\[(?P<duration>.*?)\]'
                        )
                        match = sub_entry_pattern.search(full_text)
                        
                        sub_data = { "is_attended": is_attended }
                        if match:
                            sub_data['title'] = match.group('title').strip()
                            sub_data['datetime_str'] = match.group('datetime_str').strip()
                            sub_data['duration'] = match.group('duration').strip()
                        else:
                            # Fallback for unexpected formats
                            sub_data['title'] = full_text
                            sub_data['datetime_str'] = "N/A"
                            sub_data['duration'] = "N/A"
                        sub_entry_found = True
                        entry_data["sub_entries"].append(sub_data)
                        j += 1
                    else:
                        break# Not a sub-row, break the inner loop
                
                # Determine overall status
                if not sub_entry_found:
                    entry_data["attendance_status"] = "Belum Presensi"
                else:
                    entry_data["attendance_status"] = "Sudah Presensi" if all_sub_attended else "Belum Presensi"

                entries.append(entry_data)
                i = j # Move the main index past all the rows we just processed
            else:
                i += 1 # Not a main row, just move to the next one
        
        return entries

    except requests.exceptions.RequestException as e:
        print(f"An error occurred while fetching logbook entries: {e}")
        return None
    except Exception as e:
        print(f"An unexpected error occurred in get_logbook_entries_by_id: {e}")
        return None

def get_bantu_pic_entries(ses: requests.Session, entry_point_program: Dict) -> Optional[List[Dict]]:
    """
    Navigates to the RPP page for a given program to find and scrape the 'Program Bantu' table,
    including all of its nested sub-entries.
    """
    try:
        # 1. Get the RPP page URL from the user's own program entry
        action_html = entry_point_program.get("action", "")
        rpp_url_match = re.search(r"href='([^']+logbook_program_rpp[^']+)'", action_html)
        if not rpp_url_match:
            print("Could not find RPP URL in the selected program's action HTML.")
            return None
        rpp_url = rpp_url_match.group(1)

        # 2. Navigate to the RPP page
        rpp_page_req = ses.get(rpp_url)
        rpp_page_req.raise_for_status()

        tree = fromstring(rpp_page_req.content)
        
        # 3. Find the panel for "Program Bantu"
        bantu_panel_heading = tree.xpath('//*[@id="subcontent-element"]/div[4]/div[2]/div[2]/table')
        if not bantu_panel_heading:
            print("Could not find the 'Program Bantu' panel.")
            return []
        bantu_panel = bantu_panel_heading[0].getparent().getparent()
        rows = bantu_panel.xpath('.//table/tbody/tr')

        pic_entries = []
        i = 0
        while i < len(rows):
            row = rows[i]
            cols = row.findall('td')

            # Case 1: Main Entry Row (has 6 columns with content in the first cell)
            if len(cols) == 6 and cols[0].text_content().strip():
                main_entry = {
                    "index": int(cols[0].text_content().strip()),
                    "title": cols[1].text_content().strip(),
                    "pic": cols[3].text_content().strip(),
                    "date": cols[4].text_content().strip(),
                    "location": cols[5].text_content().strip(),
                    "sub_entries": []  # Initialize list for sub-entries
                }
                pic_entries.append(main_entry)
                i += 1
                continue

            # Case 2: Sub-entry Row (has 2 columns and a specific text pattern)
            if len(cols) == 2 and pic_entries:
                cell_text = cols[1].text_content().strip()
                
                # Regex to find a sub-entry line with title, datetime, and duration
                sub_entry_pattern = re.compile(
                    r'^(?P<title>.*?)\s\((?P<datetime_str>.*?WIB)\)\s\[(?P<duration>.*?)\]', 
                    re.DOTALL
                )
                match = sub_entry_pattern.search(cell_text)

                if match:
                    # Found a valid sub-entry line, extract its details
                    sub_title = match.group('title').strip()
                    datetime_str = match.group('datetime_str').strip()
                    
                    # The attendance status is in the *next* row.
                    is_attended = False
                    if (i + 1) < len(rows):
                        row_text = rows[i].text_content()
                        next_row_text = rows[i+1].text_content()
                        next_next_row_text = rows[i+2].text_content() if (i + 2) < len(rows) else ""
                        print(next_row_text)
                        if "Sudah Presensi" in next_row_text or "Sudah Presensi" in next_next_row_text or "Sudah Presensi" in row_text:
                            is_attended = True
                            i += 1 
                    
                    sub_entry_data = {
                        'title': sub_title,
                        'datetime_str': datetime_str,
                        'is_attended': is_attended
                    }
                    
                    # Append the parsed sub-entry to the last main entry found
                    pic_entries[-1]['sub_entries'].append(sub_entry_data)
            
            # Move to the next row
            i += 1
        print(f"Found {len(pic_entries)} main entries with sub-entries in Program Bantu.")
        print(pic_entries)
        return pic_entries

    except requests.exceptions.RequestException as e:
        print(f"An HTTP error occurred: {e}")
        return None
    except (IndexError, AttributeError) as e:
        print(f"Failed to parse the HTML structure for Program Bantu: {e}")
        return None

def create_sub_entry_base(
    ses: requests.Session,
    kegiatan_url: str,
    form_details: Dict
) -> bool:
    """Base function to create a sub-entry, used by both main and PIC-assisted entries."""
    try:
        kegiatan_page_req = ses.get(kegiatan_url)
        kegiatan_page_req.raise_for_status()

        add_form_url_match = re.search(r"<a href='([^']+)'.*?title='Tambah'>", kegiatan_page_req.text)
        if not add_form_url_match:
            print("Could not find 'Tambah' (Add) link on the 'Kegiatan' page.")
            return False
        
        add_form_url = add_form_url_match.group(1)

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

        # Populate form with provided details
        form_data["dParam[judul]"] = form_details.get("sub_entry_title")
        form_data["dParam[pelaksanaan]"] = form_details.get("pelaksanaan_datetime")
        form_data["dParam[durasi]"] = str(form_details.get("duration"))
        form_data["dParam[deskripsi]"] = form_details.get("description_text")
        form_data["dParam[sasaran]"] = form_details.get("sasaran")
        form_data["dParam[jumPeserta]"] = form_details.get("jumPeserta")
        form_data["dParam[sumberDana]"] = "1"
        form_data["dParam[sumberDanaLain]"] = ""
        form_data["dParam[jumDana]"] = form_details.get("jumDana")
        form_data["dParam[hasilKegiatan]"] = form_details.get("hasil_kegiatan_text")

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
        print(f"An unexpected error occurred in create_sub_entry_base: {e}")
        return False

def create_sub_entry(
    ses: requests.Session, main_entry: Dict, form_details: Dict
) -> bool:
    """Creates a new sub-entry (kegiatan) under a main logbook entry."""
    kegiatan_url = main_entry.get("kegiatan_url")
    if not kegiatan_url:
        print("Selected main entry is missing the 'kegiatan_url'. Cannot proceed.")
        return False
    return create_sub_entry_base(ses, kegiatan_url, form_details)

def create_bantu_pic_sub_entry(
    ses: requests.Session, pic_entry: Dict, form_details: Dict
) -> bool:
    """Creates a new sub-entry (kegiatan) under a PIC-assisted logbook entry."""
    kegiatan_url = pic_entry.get("kegiatan_url")
    if not kegiatan_url:
        print("Selected PIC entry is missing the 'kegiatan_url'. Cannot proceed.")
        return False
    return create_sub_entry_base(ses, kegiatan_url, form_details)


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
        
        rpp_page_req = ses.get(rpp_url)
        rpp_page_req.raise_for_status()

        page_token = None
        for cookie in rpp_page_req.cookies:
            if cookie.name == 'simasterUGM_cookie':
                page_token = cookie.value

        if not page_token:
            for cookie in ses.cookies:
                if cookie.name == 'simasterUGM_cookie':
                    page_token = cookie.value
            if not page_token:
                 print("Fallback failed. Cannot find a valid token.")
                 return False

        tree = fromstring(rpp_page_req.content)
        rows = tree.xpath('//table[@id="datatables2"]/tbody/tr')

        i = 0
        while i < len(rows):
            main_row = rows[i]
            cols = main_row.findall('td')

            if len(cols) != 5 or int(cols[0].text_content().strip()) != main_entry_index:
                i += 1
                continue
            
            j = i + 1
            while j < len(rows):
                sub_row = rows[j]
                if len(sub_row.findall('td')) != 2: break

                if sub_entry_title_to_find in sub_row.text_content():
                    presensi_buttons = sub_row.xpath(".//a[contains(., 'Presensi')]")
                    if not presensi_buttons:
                        print("No 'Presensi' button available for this sub-entry (already attended?).")
                        return False
                    
                    ajaxify_url = presensi_buttons[0].get('ajaxify')
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
