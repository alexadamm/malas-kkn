# Malas KKN Attendance Automation
A simple program that automatically submits your KKN attendance on SIMASTER UGM once a day at a random time.

-----

## Getting Started

There are two ways to run this bot:

1.  **With Docker (Recommended):** The easiest method, works on any system with Docker.
2.  **On Termux (Without Docker):** A lightweight option for running directly on an Android device.

-----

### Method 1: Running with Docker

**Prerequisites:** You must have **[Docker](https://www.docker.com/get-started)** and **Docker Compose** installed.

**1. Clone the Repository**

```bash
git clone https://github.com/alexadamm/malas-kkn.git
cd malas-kkn
```

**2. Create the Environment File**

Create a file named `.env` in the project's root directory.

**3. Configure Your Settings**

Copy the template below into your `.env` file and fill in your details.

```env
# --- Simaster Credentials (Required) ---
SIMASTER_USERNAME=your_simaster_username
SIMASTER_PASSWORD=your_simaster_password

# --- KKN Location Settings (Required) ---
KKN_LOCATION_LATITUDE=-7.9547226
KKN_LOCATION_LONGITUDE=110.2788225
KKN_LOCATION_RADIUS_METERS=50

# --- Scheduling Window (Optional) ---
RUN_WINDOW_START_HOUR=5
RUN_WINDOW_END_HOUR=23
```

**4. Start the Bot**

Build and run the application in the background:

```bash
docker-compose up --build -d
```

-----

### Method 2: Running on Termux (Without Docker)

**1. Install Dependencies in Termux**

Open Termux and run the following commands to install Python and the necessary build tools for the `lxml` library:

```bash
pkg update && pkg upgrade
pkg install python clang libxml2 libxslt
```

**2. Clone the Repository**

```bash
git clone https://github.com/alexadamm/malas-kkn.git
cd malas-kkn
```

**3. Set up a Virtual Environment**

This keeps the project's libraries separate from your system's Python.

```bash
python -m venv .venv
source .venv/bin/activate
```

**4. Install Python Libraries**

```bash
pip install -r requirements.txt
```

**5. Create and Configure `.env` File**

Follow steps 2 and 3 from the Docker method above to create and configure your `.env` file.

**6. Run the Bot**

Start the script using the Python module flag:

```bash
python -m src.main
```

To keep it running in the background, you can use a terminal multiplexer like `tmux` (available via `pkg install tmux`).

-----

## Managing the Bot

  * **View Logs (Docker):**
    ```bash
    docker-compose logs -f
    ```
  * **Stop the Bot (Docker):**
    ```bash
    docker-compose down
    ```
