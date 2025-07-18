import os
import re
import requests
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# --- Import fungsi dari file Anda yang sudah ada ---
# Pastikan file-file ini berada di direktori yang sama
from simaster import get_simaster_session, get_kkn_programs, get_logbook_entries_by_id, get_bantu_pic_entries

# Inisialisasi colorama untuk pewarnaan di terminal
from colorama import init, Fore, Style
init(autoreset=True)

# Kamus untuk menerjemahkan nama bulan dalam Bahasa Indonesia ke angka
MONTH_MAP = {
    'januari': 1, 'februari': 2, 'maret': 3, 'april': 4, 'mei': 5, 'juni': 6,
    'juli': 7, 'agustus': 8, 'september': 9, 'oktober': 10, 'november': 11, 'desember': 12
}

def parse_datetime_range(datetime_str: Optional[str]) -> Tuple[Optional[datetime], Optional[datetime]]:
    """
    Menerjemahkan string tanggal dan waktu yang kompleks dari Simaster menjadi objek datetime.
    Mendukung format 'DD MMMM YYYY HH:MM - HH:MM' dan 'DD MMMM YYYY HH:MM s.d DD MMMM YYYY HH:MM'.
    """
    if not datetime_str:
        return None, None

    datetime_str = datetime_str.lower().replace("wib", "").strip()

    try:
        # Pola untuk rentang waktu antar hari (e.g., "8 Juli 2025 19:00 s.d 9 Juli 2025 00:00")
        overnight_match = re.search(r'(\d{1,2})\s(\w+)\s(\d{4})\s(\d{2}:\d{2})\s+s\.d\s+(\d{1,2})\s(\w+)\s(\d{4})\s(\d{2}:\d{2})', datetime_str)
        if overnight_match:
            d1, m1_str, y1, t1, d2, m2_str, y2, t2 = overnight_match.groups()
            start_dt = datetime(int(y1), MONTH_MAP[m1_str], int(d1), int(t1[:2]), int(t1[3:]))
            end_dt = datetime(int(y2), MONTH_MAP[m2_str], int(d2), int(t2[:2]), int(t2[3:]))
            return start_dt, end_dt

        # Pola untuk rentang waktu dalam satu hari (e.g., "2 Juli 2025 13:00 - 16:00")
        sameday_match = re.search(r'(\d{1,2})\s(\w+)\s(\d{4})\s(\d{2}:\d{2})\s+-\s+(\d{2}:\d{2})', datetime_str)
        if sameday_match:
            d, m_str, y, t1, t2 = sameday_match.groups()
            start_dt = datetime(int(y), MONTH_MAP[m_str], int(d), int(t1[:2]), int(t1[3:]))
            end_dt = datetime(int(y), MONTH_MAP[m_str], int(d), int(t2[:2]), int(t2[3:]))
            return start_dt, end_dt

    except (ValueError, KeyError) as e:
        print(f"{Fore.RED}Error parsing date string '{datetime_str}': {e}{Style.RESET_ALL}")
        return None, None
        
    return None, None


def visualize_timeline(events: List[Dict]):
    """Menampilkan daftar kegiatan yang sudah diurutkan secara kronologis dengan pewarnaan."""
    if not events:
        print(f"{Fore.YELLOW}Tidak ada kegiatan yang bisa ditampilkan di linimasa.")
        return

    print("\n" + "="*80)
    print(" " * 28 + "LINIMASA KEGIATAN KKN")
    print("="*80 + "\n")

    # Urutkan semua kegiatan berdasarkan waktu mulai
    sorted_events = sorted(events, key=lambda x: x['start_time'])

    for event in sorted_events:
        event_type = event['type']
        color = Fore.CYAN if event_type == "Program Utama" else Fore.MAGENTA
        
        start_str = event['start_time'].strftime('%a, %d %b %Y, %H:%M')
        end_str = event['end_time'].strftime('%H:%M')

        # Jika kegiatan berlangsung lebih dari satu hari, tampilkan tanggal berakhir juga
        if event['start_time'].date() != event['end_time'].date():
             end_str = event['end_time'].strftime('%a, %d %b, %H:%M')

        print(f"{color}[{event_type:^15}]{Style.RESET_ALL} {event['title']}")
        print(f"{' ' * 18} 🕒 {start_str} -> {end_str}\n")


def main():
    """Fungsi utama untuk mengambil data dan membuat linimasa."""
    username = os.getenv("SIMASTER_USERNAME")
    password = os.getenv("SIMASTER_PASSWORD")
    if not username or not password:
        print(f"{Fore.RED}Error: Variabel SIMASTER_USERNAME dan SIMASTER_PASSWORD belum diatur.")
        return

    print("--- Login ke SIMASTER untuk mengambil data linimasa ---")
    session = get_simaster_session(username, password)
    if not session:
        print(f"{Fore.RED}Login gagal. Keluar.")
        return

    all_events = []

    # 1. Mengambil data dari Sub-Entri Program Utama
    print("\n🔄 Mengambil data dari Program Utama...")
    programs = get_kkn_programs(session)
    if programs:
        for prog in programs:
            entries = get_logbook_entries_by_id(session, prog['program_mhs_id'])
            if entries:
                for entry in entries:
                    for sub_entry in entry.get('sub_entries', []):
                        start_time, end_time = parse_datetime_range(sub_entry.get('datetime_str'))
                        if start_time and end_time:
                            all_events.append({
                                'title': sub_entry['title'],
                                'start_time': start_time,
                                'end_time': end_time,
                                'type': 'Program Utama'
                            })

    # 2. Mengambil data dari Program Bantu
    print("🔄 Mengambil data dari Program Bantu...")
    # Menggunakan program pertama sebagai titik masuk untuk mengambil data program bantu
    if programs:
        bantu_entries = get_bantu_pic_entries(session, programs[0])
        if bantu_entries:
            for entry in bantu_entries:
                # Di program bantu, judul dan waktu berada di field yang berbeda
                title = entry.get('title')
                time_str_raw = entry.get('activity_time') # Gunakan field yang benar
                
                # Ekstrak hanya bagian dalam kurung untuk parsing
                time_match = re.search(r'\((.*?)\)', time_str_raw) if time_str_raw else None
                time_str_to_parse = time_match.group(1) if time_match else None

                start_time, end_time = parse_datetime_range(time_str_to_parse)
                if start_time and end_time:
                    all_events.append({
                        'title': title,
                        'start_time': start_time,
                        'end_time': end_time,
                        'type': 'Program Bantu'
                    })

    # 3. Membuat Visualisasi
    visualize_timeline(all_events)


if __name__ == "__main__":
    main()
