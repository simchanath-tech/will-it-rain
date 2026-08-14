# Will It Rain on My Vacation? — Version 4 Prototype

Features:
- Broad region selection
- Top five destination recommendations
- Optional city search that calculates the best dates for one specific destination
- Earliest departure and latest return
- Trip-length dropdown
- Weekend, extended-weekend, and long-weekend options
- Weekend preference for trips of five days or more
- Interactive Leaflet/OpenStreetMap map
- Daily weather outlook
- Server-side proprietary forecast and ranking calculations
- Render deployment configuration

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:8000

## GitHub Desktop

Copy all files and folders into your cloned `will-it-rain` repository folder.
In GitHub Desktop:
1. Review the changed files.
2. Enter a summary such as `Add Version 4 vacation planner`.
3. Click **Commit to main**.
4. Click **Push origin**.

## Important prototype limitation

This launch prototype uses a consistent global ERA5-Land historical baseline through
Open-Meteo so that region ranking works worldwide. The next data-engine phase can
route U.S. destinations to NOAA station observations and add additional official
regional station sources without changing the user interface.


## Version 4.1 reliability update

- Batches all destinations into one historical request and one seasonal request.
- Retries temporary HTTP 429 responses.
- Shows readable browser errors when Render returns HTML.
- Uses a five-minute Gunicorn worker timeout for initial regional calculations.
