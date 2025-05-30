# Pterodactyl Minecraft Whitelist Manager

A Flask-based web application to collect Minecraft and Discord usernames, convert them to Mojang UUIDs, and manage server whitelist files directly on Pterodactyl-managed Minecraft servers.

## Features

* **Public Signup**: Users submit their Minecraft and Discord usernames for approval.
* **Admin Panel**: HTTP Basic Auth–protected dashboard to:

  * View, enable/disable, or delete whitelist requests.
  * Automatically discover all Pterodactyl servers under your API key.
  * Toggle whitelist syncing for individual servers.
* **Automated Sync**: Regenerate and push `/whitelist.json` and run `whitelist reload` every 10 minutes or immediately upon changes.

## Tech Stack

* Python 3.8+
* Flask
* SQLite (default; easily switchable to MySQL/PostgreSQL)
* Pterodactyl API via [pydactyl](https://pypi.org/project/pydactyl/)
* APScheduler for background tasks
* Flask-HTTPAuth for admin authentication
* python-dotenv for environment variable management

## Installation

1. **Clone the repo**

   ```bash
   git clone https://github.com/NerdAler1/PterodactylWhitelister.git
   cd pterodactyl-whitelist-manager
   ```

2. **Create a virtual environment and install dependencies**

   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Environment Variables**
   Copy the example file and fill in your values:

   ```bash
   cp .env.example .env
   ```

   Edit `.env`:

   ```ini
   FLASK_SECRET=your_flask_secret_key
   ADMIN_CREDS={"alice":"password1","bob":"password2"}
   PTERO_API_URL=https://panel.yourdomain.com
   PTERO_API_KEY=your_pterodactyl_api_key
   SYNC_INTERVAL=10
   ```

4. **Run the app**

   ```bash
   flask run
   ```

   By default, the app listens on `http://127.0.0.1:5000/`.

## Usage

* **Public Form**: Visit `/` to submit a Minecraft username and Discord tag.
* **Admin Dashboard**: Visit `/admin` and authenticate with one of the credentials in `ADMIN_CREDS`.

  * View all pending and approved requests.
  * Enable/disable or delete entries.
  * Toggle whitelist syncing for each Pterodactyl server.

## Database Schema

* **whitelist**

  | Column            | Type     | Description                  |
  | ----------------- | -------- | ---------------------------- |
  | id                | INTEGER  | Auto-increment primary key   |
  | mc\_username      | TEXT     | Submitted Minecraft username |
  | mc\_uuid          | TEXT     | Mojang UUID                  |
  | discord\_username | TEXT     | Submitted Discord username   |
  | approved          | INTEGER  | 0 = pending, 1 = approved    |
  | created\_at       | DATETIME | Timestamp of submission      |

* **ptero\_servers**

  | Column     | Type    | Description                               |
  | ---------- | ------- | ----------------------------------------- |
  | id         | INTEGER | Auto-increment primary key                |
  | name       | TEXT    | Server name from Pterodactyl API          |
  | server\_id | TEXT    | Unique Pterodactyl server identifier      |
  | enabled    | INTEGER | 0 = syncing disabled, 1 = syncing enabled |

##  Possible Future Plans
* **Discord Verifier** I would like the discord username field to actually check if users are in a discord server, that way only discord server members can actually sign up (obviously this would not be foolproof, but its possible to cut down on spam.)

## License

MIT © Jack Thiess

## AI Disclaimer

This README, as well a lot of the web UIs, were created using the assistance of AI. Additionally AI autocomplete was used during the creation of the entire project.
