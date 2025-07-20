import os
from typing import List, Dict
from datetime import datetime, timedelta, time
from colorama import Fore, Style

try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

def generate_schedule_html(events: List[Dict], program_colors: Dict[str, str], duration_summary: Dict[str, float], total_hours: float) -> str:
    """
    Generates a self-contained HTML string to visualize the schedule, including free time blocks
    to show a full 24-hour day.
    """
    # Map colorama colors to HTML-friendly hex codes or names
    color_map = {
        Fore.CYAN: '#008B8B',        # DarkCyan
        Fore.GREEN: '#228B22',       # ForestGreen
        Fore.YELLOW: '#DAA520',      # GoldenRod
        Fore.BLUE: '#4169E1',        # RoyalBlue
        Fore.LIGHTRED_EX: '#CD5C5C', # IndianRed
        Fore.MAGENTA: '#8A2BE2',     # BlueViolet
        Fore.WHITE: '#A9A9A9',       # DarkGray
        Style.RESET_ALL: '#333333'   # Default text color
    }

    # --- HTML Structure and CSS Styling ---
    html = """
    <!DOCTYPE html>
    <html lang="id">
    <head>
        <meta charset="UTF-8">
        <title>Visualisasi Jadwal KKN</title>
        <style>
            @page { size: A4; margin: 1.5cm; }
            body { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.5; color: #333; }
            .container { width: 100%; margin: auto; }
            h1, h2, h3 { color: #2c3e50; border-bottom: 2px solid #e9ecef; padding-bottom: 8px; }
            h1 { text-align: center; font-size: 22px; }
            h2 { font-size: 18px; margin-top: 25px; }
            h3 { font-size: 15px; margin-top: 20px; color: #34495e; }
            .legend, .summary { border: 1px solid #dee2e6; padding: 15px; border-radius: 8px; margin-bottom: 20px; page-break-inside: avoid; }
            .legend-item, .summary-item { display: flex; align-items: center; margin-bottom: 8px; font-size: 13px; }
            .color-box { width: 18px; height: 18px; margin-right: 12px; border-radius: 4px; border: 1px solid #ccc; }
            .day-schedule { margin-bottom: 20px; page-break-inside: avoid; }
            table { width: 100%; border-collapse: collapse; page-break-inside: auto; }
            tr { page-break-inside: avoid; page-break-after: auto; }
            th, td { padding: 9px 12px; text-align: left; border-bottom: 1px solid #e0e0e0; font-size: 12px; vertical-align: top; }
            th { background-color: #f4f6f7; font-weight: 600; }
            .time-col { width: 18%; font-weight: 500; color: #555; }
            .program-col { font-style: italic; color: #666; width: 25%; }
            .activity-title { font-weight: 500; }
            tr.free-time-row td { background-color: #f8f9fa; color: #6c757d; font-style: italic; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Visualisasi Jadwal Kegiatan KKN</h1>
    """

    # --- Legend Section ---
    html += '<h2>Legenda</h2><div class="legend">'
    for title, color_code in program_colors.items():
        color = color_map.get(color_code, 'black')
        html += f'<div class="legend-item"><div class="color-box" style="background-color: {color};"></div><span>{title}</span></div>'
    if any(e['type'] == 'Program Bantu' for e in events):
         html += f'<div class="legend-item"><div class="color-box" style="background-color: {color_map[Fore.MAGENTA]};"></div><span>Program Bantu</span></div>'
    html += '</div>'

    # --- Group events by date for processing ---
    events_by_date = {}
    for event in events:
        date_key = event['start_time'].date()
        if date_key not in events_by_date:
            events_by_date[date_key] = []
        events_by_date[date_key].append(event)

    # --- Schedule Table Section ---
    html += '<h2>Jadwal Kegiatan</h2>'
    sorted_dates = sorted(events_by_date.keys())
    for date_key in sorted_dates:
        html += f'<div class="day-schedule"><h3>{date_key.strftime("%A, %d %B %Y")}</h3>'
        html += '<table><thead><tr><th class="time-col">Waktu</th><th class="activity-title">Judul Kegiatan</th><th class="program-col">Program</th></tr></thead><tbody>'
        
        day_events = sorted(events_by_date[date_key], key=lambda x: x['start_time'])
        
        # Start tracking time from the beginning of the day (00:00)
        current_time = datetime.combine(date_key, time.min)

        for event in day_events:
            # If there's a gap between the last activity and this one, it's free time.
            if event['start_time'] > current_time:
                free_start_str = current_time.strftime('%H:%M')
                free_end_str = event['start_time'].strftime('%H:%M')
                html += '<tr class="free-time-row">'
                html += f'<td class="time-col">{free_start_str} - {free_end_str}</td>'
                html += '<td>Waktu Luang</td><td>-</td></tr>'

            # Render the actual event
            start_str = event['start_time'].strftime('%H:%M')
            end_str = event['end_time'].strftime('%H:%M')
            color = color_map.get(event.get('color', Fore.WHITE), 'grey')
            html += f'<tr style="border-left: 4px solid {color};">'
            html += f'<td class="time-col">{start_str} - {end_str}</td>'
            html += f'<td class="activity-title">{event["title"]}</td>'
            html += f'<td class="program-col">{event["type"]}</td></tr>'

            # Move the timeline cursor to the end of this event
            current_time = event['end_time']

        # Check for free time at the end of the day until midnight
        end_of_day = datetime.combine(date_key + timedelta(days=1), time.min)
        if current_time < end_of_day:
            free_start_str = current_time.strftime('%H:%M')
            html += '<tr class="free-time-row">'
            html += f'<td class="time-col">{free_start_str} - 24:00</td>'
            html += '<td>Waktu Luang</td><td>-</td></tr>'

        html += '</tbody></table></div>'
    
    # --- Duration Summary Section ---
    html += '<h2>Ringkasan Durasi Kegiatan</h2><div class="summary">'
    bantu_hours = sum((e['end_time'] - e['start_time']).total_seconds() / 3600.0 for e in events if e['type'] == 'Program Bantu')
    
    for title, hours in duration_summary.items():
        color = color_map.get(program_colors.get(title, Fore.WHITE), 'black')
        html += f'<div class="summary-item"><div class="color-box" style="background-color: {color};"></div><span><strong>{title}:</strong> {hours:.1f} jam</span></div>'
    if bantu_hours > 0:
        html += f'<div class="summary-item"><div class="color-box" style="background-color: {color_map[Fore.MAGENTA]};"></div><span><strong>Program Bantu (PIC Assistance):</strong> {bantu_hours:.1f} jam</span></div>'

    html += f'<hr style="border: none; border-top: 1px solid #eee; margin: 15px 0;"><p style="font-size: 14px; font-weight: bold;">Total Keseluruhan: {total_hours:.1f} jam</p>'
    html += '</div></div></body></html>'
    return html

def export_to_html_file(html_content: str, filename: str = "timeline.html"):
    """Saves the generated HTML content to a file."""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"\n{Fore.GREEN}✅ Timeline successfully exported to {filename}{Style.RESET_ALL}")
        print("   You can open this file in your web browser.")
    except IOError as e:
        print(f"\n{Fore.RED}Error: Failed to write HTML file. {e}{Style.RESET_ALL}")

def export_to_pdf(html_content: str, filename: str = "timeline.pdf"):
    """Converts the generated HTML string to a PDF file using WeasyPrint."""
    if not WEASYPRINT_AVAILABLE:
        print(f"\n{Fore.RED}Error: PDF export failed. The 'weasyprint' library is not installed.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Please install it by running: {Style.BRIGHT}pip install weasyprint{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}Note: WeasyPrint may require additional system dependencies on Linux or macOS.{Style.RESET_ALL}")
        print(f"{Fore.YELLOW}See https://weasyprint.readthedocs.io/en/stable/install.html for details.{Style.RESET_ALL}")
        return

    try:
        print(f"\n{Fore.YELLOW}⏳ Generating PDF, this might take a moment...{Style.RESET_ALL}")
        HTML(string=html_content).write_pdf(filename)
        print(f"{Fore.GREEN}✅ Timeline successfully exported to {filename}{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}An unexpected error occurred during PDF generation: {e}{Style.RESET_ALL}")

