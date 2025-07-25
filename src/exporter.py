import os
import math
from typing import List, Dict
from datetime import datetime, timedelta, time
from collections import defaultdict
from colorama import Fore, Style
from collections import defaultdict
from ics import Calendar, Event
import pytz

try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False

# --- Helper Functions for Visualizations ---

def _get_color_for_hours(hours, max_hours):
    """Returns a shade of green based on the number of hours worked."""
    if hours == 0:
        return '#ebedf0'  # Light grey for no activity
    if max_hours == 0:
        return '#9be9a8' # Default green if there's only one level
    
    intensity = hours / max_hours
    if intensity < 0.25:
        return '#9be9a8' # Lightest green
    elif intensity < 0.5:
        return '#40c463'
    elif intensity < 0.75:
        return '#30a14e'
    else:
        return '#216e39' # Darkest green

def _generate_pie_chart_svg(data, color_map):
    """Generates an SVG pie chart from a dictionary of data."""
    if not data or sum(data.values()) == 0:
        return "<p>No data available for chart.</p>"

    total = sum(data.values())
    angle_start = 0
    svg_paths = ""
    legend_items = ""
    radius = 80
    cx, cy = 100, 100

    for label, value in data.items():
        angle_end = angle_start + (value / total) * 360
        
        # Calculate coordinates for the slice
        start_x = cx + radius * math.cos(math.radians(angle_start))
        start_y = cy + radius * math.sin(math.radians(angle_start))
        end_x = cx + radius * math.cos(math.radians(angle_end))
        end_y = cy + radius * math.sin(math.radians(angle_end))
        
        large_arc_flag = 1 if (angle_end - angle_start) > 180 else 0
        color = color_map.get(label, '#cccccc')
        
        path = f'<path d="M {cx},{cy} L {start_x},{start_y} A {radius},{radius} 0 {large_arc_flag},1 {end_x},{end_y} Z" fill="{color}"></path>'
        svg_paths += path
        
        percentage = (value / total) * 100
        legend_items += f'<div class="pie-legend-item"><div class="color-box" style="background-color: {color};"></div><span>{label} ({percentage:.1f}%)</span></div>'
        
        angle_start = angle_end

    svg = f"""
    <div class="pie-chart-container">
        <svg viewBox="0 0 200 200" width="200" height="200">{svg_paths}</svg>
        <div class="pie-legend">{legend_items}</div>
    </div>
    """
    return svg


# --- Main HTML Generation Function ---

def generate_schedule_html(events: List[Dict], program_colors: Dict[str, str], duration_summary: Dict[str, float], total_hours: float, pic_hours: Dict[str, float], bantu_hours: float) -> str:
    """
    Generates a self-contained HTML string with advanced visualizations.
    """
    # Map colorama colors to HTML-friendly hex codes
    color_map = {
        Fore.CYAN: '#008B8B', Fore.GREEN: '#228B22', Fore.YELLOW: '#DAA520',
        Fore.BLUE: '#4169E1', Fore.LIGHTRED_EX: '#CD5C5C', Fore.MAGENTA: '#8A2BE2',
        Fore.WHITE: '#A9A9A9', Style.RESET_ALL: '#333333'
    }
    
    # Map program titles to the hex codes for the pie chart
    pie_color_map = {title: color_map[color_code] for title, color_code in program_colors.items()}
    if bantu_hours > 0:
        pie_color_map['Program Bantu'] = color_map[Fore.MAGENTA]

    # --- HTML Structure and Enhanced CSS ---
    html = """
    <!DOCTYPE html><html lang="id"><head><meta charset="UTF-8"><title>Laporan Visual Kegiatan KKN</title>
    <style>
        @page { size: A4; margin: 1.5cm; }
        body { font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; color: #333; }
        .container { width: 100%; margin: auto; }
        h1, h2, h3 { color: #2c3e50; border-bottom: 2px solid #e9ecef; padding-bottom: 8px; margin-bottom: 15px; }
        h1 { text-align: center; font-size: 24px; }
        h2 { font-size: 20px; margin-top: 30px; }
        h3 { font-size: 16px; margin-top: 20px; color: #34495e; border-bottom: 1px solid #dfe6e9; }
        .grid-container { display: grid; grid-template-columns: 1fr 1fr; gap: 25px; margin-top: 20px; page-break-inside: avoid; }
        .card { border: 1px solid #dee2e6; padding: 15px; border-radius: 8px; }
        .stats-list li { margin-bottom: 8px; font-size: 14px; }
        .heatmap-container { overflow-x: auto; padding: 5px; }
        .heatmap { border-collapse: collapse; }
        .heatmap td { width: 16px; height: 16px; background-color: #ebedf0; border: 1px solid white; }
        .heatmap td.has-data { cursor: pointer; }
        .heatmap .month-label, .heatmap .day-label { font-size: 10px; text-align: center; padding: 0 5px; }
        .pie-chart-container { display: flex; align-items: center; gap: 20px; }
        .pie-legend .legend-item, .pie-legend .pie-legend-item { display: flex; align-items: center; margin-bottom: 5px; font-size: 12px; }
        .color-box { width: 15px; height: 15px; margin-right: 10px; border-radius: 3px; }
        table { width: 100%; border-collapse: collapse; page-break-inside: auto; }
        tr { page-break-inside: avoid; }
        th, td { padding: 9px 12px; text-align: left; border-bottom: 1px solid #e0e0e0; font-size: 12px; vertical-align: top; }
        th { background-color: #f4f6f7; font-weight: 600; }
        .time-col { width: 18%; } .program-col { width: 25%; }
        tr.free-time-row td { background-color: #f8f9fa; color: #6c757d; font-style: italic; }
    </style>
    </head><body><div class="container">
    <h1>Laporan Visual Kegiatan KKN</h1>
    """

    # --- Data Processing for Visualizations ---
    daily_hours = defaultdict(float)
    for event in events:
        daily_hours[event['start_time'].date()] += (event['end_time'] - event['start_time']).total_seconds() / 3600.0
    
    # --- Analytics Section ---
    html += "<h2>Analisis & Statistik Kegiatan</h2><div class='grid-container'>"
    
    # Key Stats Card
    busiest_day = max(daily_hours, key=daily_hours.get) if daily_hours else None
    html += "<div class='card'><h3>Statistik Kunci</h3><ul class='stats-list'>"
    html += f"<li><strong>Total Jam Kerja:</strong> {total_hours:.1f} jam</li>"
    html += f"<li><strong>Jumlah Hari Aktif:</strong> {len(daily_hours)} hari</li>"
    if busiest_day:
        html += f"<li><strong>Hari Tersibuk:</strong> {busiest_day.strftime('%d %b %Y')} ({daily_hours[busiest_day]:.1f} jam)</li>"
    html += f"<li><strong>Rata-rata Jam per Hari Aktif:</strong> {total_hours / len(daily_hours) if daily_hours else 0:.1f} jam</li>"
    html += "</ul></div>"

    # PIC Breakdown Card
    if pic_hours:
        html += "<div class='card'><h3>Jam Bantuan per PIC</h3><ul class='stats-list'>"
        for pic, hours in sorted(pic_hours.items(), key=lambda item: item[1], reverse=True):
            html += f"<li><strong>{pic}:</strong> {hours:.1f} jam</li>"
        html += "</ul></div>"
    
    html += "</div>" # End grid-container

    # Pie Chart
    pie_data = duration_summary.copy()
    if bantu_hours > 0:
        pie_data['Program Bantu'] = bantu_hours
    html += "<h3>Distribusi Jam Kerja</h3>"
    html += _generate_pie_chart_svg(pie_data, pie_color_map)

    # GitHub-style Heatmap
    # html += "<h3>Aktivitas Harian</h3><div class='heatmap-container'><table class='heatmap'><tbody>"
    # start_date = min(daily_hours.keys()) if daily_hours else datetime.now().date()
    # end_date = max(daily_hours.keys()) if daily_hours else datetime.now().date()
    # max_hours_in_day = max(daily_hours.values()) if daily_hours else 0
    
    # current_date = start_date - timedelta(days=start_date.weekday()) # Start from Monday
    
    # Month labels
    # html += "<tr><td></td>"
    # month_year = None
    # while current_date <= end_date:
    #     if current_date.strftime('%b %Y') != month_year:
    #         month_year = current_date.strftime('%b %Y')
    #         html += f"<td colspan='4' class='month-label'>{month_year}</td>"
    #     current_date += timedelta(days=7)
    # html += "</tr>"
    
    # current_date = start_date - timedelta(days=start_date.weekday())
    # day_labels = ['Sen', 'Rab', 'Jum']
    # for i in range(7): # 7 days of the week
    #     html += "<tr>"
    #     if i % 2 != 0:
    #          html += f"<td class='day-label'>{day_labels.pop(0) if day_labels else ''}</td>"
    #     else:
    #          html += "<td class='day-label'></td>"

    #     for j in range(18): # ~4 months view
    #         d = current_date + timedelta(days=(j*7)+i)
    #         if start_date <= d <= end_date:
    #             hours = daily_hours.get(d, 0)
    #             color = _get_color_for_hours(hours, max_hours_in_day)
    #             html += f"<td class='has-data' style='background-color: {color};' title='{d.strftime('%d %b %Y')}: {hours:.1f} jam'></td>"
    #         else:
    #             html += "<td></td>"
    #     html += "</tr>"
    # html += "</tbody></table></div>"

    # --- Full Schedule Section ---
    html += '<h2>Rincian Jadwal Kegiatan</h2>'
    # ... (rest of the schedule table generation code remains the same) ...
    sorted_dates = sorted(daily_hours.keys())
    for date_key in sorted_dates:
        html += f'<div class="day-schedule"><h3>{date_key.strftime("%A, %d %B %Y")}</h3>'
        html += '<table><thead><tr><th class="time-col">Waktu</th><th>Judul Kegiatan</th><th class="program-col">Program</th></tr></thead><tbody>'
        day_events = sorted([e for e in events if e['start_time'].date() == date_key], key=lambda x: x['start_time'])
        current_time = datetime.combine(date_key, time.min)
        for event in day_events:
            if event['start_time'] > current_time:
                html += f'<tr class="free-time-row"><td>{current_time.strftime("%H:%M")} - {event["start_time"].strftime("%H:%M")}</td><td>Waktu Luang</td><td>-</td></tr>'
            color = pie_color_map.get(event["type"], '#cccccc')
            html += f'<tr style="border-left: 4px solid {color};"><td>{event["start_time"].strftime("%H:%M")} - {event["end_time"].strftime("%H:%M")}</td><td>{event["title"]}</td><td>{event["type"]}</td></tr>'
            current_time = event['end_time']
        end_of_day = datetime.combine(date_key + timedelta(days=1), time.min)
        if current_time < end_of_day:
            html += f'<tr class="free-time-row"><td>{current_time.strftime("%H:%M")} - 24:00</td><td>Waktu Luang</td><td>-</td></tr>'
        html += '</tbody></table></div>'

    html += "</div></body></html>"
    return html

# --- Export Functions (Unchanged) ---
def export_to_html_file(html_content: str, filename: str = "timeline_report.html"):
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"\n{Fore.GREEN}✅ Laporan berhasil diekspor ke {filename}{Style.RESET_ALL}")
    except IOError as e:
        print(f"\n{Fore.RED}Error: Gagal menyimpan file HTML. {e}{Style.RESET_ALL}")

def export_to_pdf(html_content: str, filename: str = "timeline_report.pdf"):
    if not WEASYPRINT_AVAILABLE:
        # ... (error message remains the same) ...
        return
    try:
        print(f"\n{Fore.YELLOW}⏳ Membuat PDF, proses ini mungkin memakan waktu...{Style.RESET_ALL}")
        HTML(string=html_content).write_pdf(filename)
        print(f"{Fore.GREEN}✅ Laporan berhasil diekspor ke {filename}{Style.RESET_ALL}")
    except Exception as e:
        print(f"\n{Fore.RED}Terjadi kesalahan saat membuat PDF: {e}{Style.RESET_ALL}")

def export_to_ics(events: List[Dict], filename: str = "kkn_schedule.ics"):
    """Exports the schedule to an .ics calendar file."""
    # Use the appropriate timezone for Indonesia (WIB)
    local_tz = pytz.timezone('Asia/Jakarta')
    c = Calendar()

    for event_data in events:
        e = Event()
        e.name = event_data['title']
        # The datetimes from the app are naive, so we make them timezone-aware
        e.begin = local_tz.localize(event_data['start_time'])
        e.end = local_tz.localize(event_data['end_time'])
        e.description = f"Program: {event_data['type']}"
        c.events.add(e)
    
    try:
        with open(filename, 'w', encoding="utf-8") as f:
            f.writelines(c.serialize_iter())
        print(f"\n{Fore.GREEN}✅ Jadwal berhasil diekspor ke {filename}{Style.RESET_ALL}")
        print("   Anda dapat mengimpor file ini ke Google Calendar, Outlook, atau Apple Calendar.")
    except IOError as e:
        print(f"\n{Fore.RED}Error: Gagal menyimpan file ICS. {e}{Style.RESET_ALL}")
