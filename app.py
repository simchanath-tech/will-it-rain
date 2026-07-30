from __future__ import annotations

import json
import math
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# Proprietary model settings stay server-side.
_HISTORICAL_WEIGHT = 0.70
_MODEL_WEIGHT = 0.30
_PRECIP_THRESHOLD_INCHES = 0.10
_MAX_FORECAST_DAYS = 210
_HISTORY_YEARS = 25

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
SEASONAL_URL = "https://seasonal-api.open-meteo.com/v1/seasonal"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"

CACHE_DIR = Path(__file__).resolve().parent / ".weather_cache"
CACHE_DIR.mkdir(exist_ok=True)

# Curated launch destinations. More can be added without changing the UI.
REGIONS: dict[str, list[dict[str, Any]]] = {
    "Europe": [
        {"name": "Lisbon", "country": "Portugal", "lat": 38.7223, "lon": -9.1393},
        {"name": "Algarve", "country": "Portugal", "lat": 37.0179, "lon": -7.9308},
        {"name": "Barcelona", "country": "Spain", "lat": 41.3874, "lon": 2.1686},
        {"name": "Mallorca", "country": "Spain", "lat": 39.6953, "lon": 3.0176},
        {"name": "Nice", "country": "France", "lat": 43.7102, "lon": 7.2620},
        {"name": "Rome", "country": "Italy", "lat": 41.9028, "lon": 12.4964},
        {"name": "Sicily", "country": "Italy", "lat": 37.5999, "lon": 14.0154},
        {"name": "Dubrovnik", "country": "Croatia", "lat": 42.6507, "lon": 18.0944},
        {"name": "Crete", "country": "Greece", "lat": 35.2401, "lon": 24.8093},
        {"name": "Madeira", "country": "Portugal", "lat": 32.7607, "lon": -16.9595},
    ],
    "Caribbean": [
        {"name": "Aruba", "country": "Aruba", "lat": 12.5211, "lon": -69.9683},
        {"name": "Curaçao", "country": "Curaçao", "lat": 12.1696, "lon": -68.9900},
        {"name": "Barbados", "country": "Barbados", "lat": 13.1939, "lon": -59.5432},
        {"name": "Nassau", "country": "Bahamas", "lat": 25.0443, "lon": -77.3504},
        {"name": "Montego Bay", "country": "Jamaica", "lat": 18.4762, "lon": -77.8939},
        {"name": "Punta Cana", "country": "Dominican Republic", "lat": 18.5601, "lon": -68.3725},
        {"name": "San Juan", "country": "Puerto Rico", "lat": 18.4655, "lon": -66.1057},
        {"name": "St. Lucia", "country": "Saint Lucia", "lat": 13.9094, "lon": -60.9789},
        {"name": "Antigua", "country": "Antigua and Barbuda", "lat": 17.0747, "lon": -61.8175},
        {"name": "Grand Cayman", "country": "Cayman Islands", "lat": 19.3133, "lon": -81.2546},
    ],
    "South America": [
        {"name": "Buenos Aires", "country": "Argentina", "lat": -34.6037, "lon": -58.3816},
        {"name": "Rio de Janeiro", "country": "Brazil", "lat": -22.9068, "lon": -43.1729},
        {"name": "São Paulo", "country": "Brazil", "lat": -23.5505, "lon": -46.6333},
        {"name": "Lima", "country": "Peru", "lat": -12.0464, "lon": -77.0428},
        {"name": "Cusco", "country": "Peru", "lat": -13.5319, "lon": -71.9675},
        {"name": "Cartagena", "country": "Colombia", "lat": 10.3910, "lon": -75.4794},
        {"name": "Santiago", "country": "Chile", "lat": -33.4489, "lon": -70.6693},
        {"name": "Quito", "country": "Ecuador", "lat": -0.1807, "lon": -78.4678},
        {"name": "Montevideo", "country": "Uruguay", "lat": -34.9011, "lon": -56.1645},
        {"name": "Mendoza", "country": "Argentina", "lat": -32.8895, "lon": -68.8458},
    ],
    "North America": [
        {"name": "New York City", "country": "United States", "lat": 40.7128, "lon": -74.0060},
        {"name": "Miami", "country": "United States", "lat": 25.7617, "lon": -80.1918},
        {"name": "San Diego", "country": "United States", "lat": 32.7157, "lon": -117.1611},
        {"name": "Honolulu", "country": "United States", "lat": 21.3069, "lon": -157.8583},
        {"name": "Vancouver", "country": "Canada", "lat": 49.2827, "lon": -123.1207},
        {"name": "Montreal", "country": "Canada", "lat": 45.5017, "lon": -73.5673},
        {"name": "Cancún", "country": "Mexico", "lat": 21.1619, "lon": -86.8515},
        {"name": "Mexico City", "country": "Mexico", "lat": 19.4326, "lon": -99.1332},
        {"name": "Anchorage", "country": "United States", "lat": 61.2181, "lon": -149.9003},
        {"name": "Seattle", "country": "United States", "lat": 47.6062, "lon": -122.3321},
    ],
    "Asia": [
        {"name": "Tokyo", "country": "Japan", "lat": 35.6762, "lon": 139.6503},
        {"name": "Kyoto", "country": "Japan", "lat": 35.0116, "lon": 135.7681},
        {"name": "Bangkok", "country": "Thailand", "lat": 13.7563, "lon": 100.5018},
        {"name": "Singapore", "country": "Singapore", "lat": 1.3521, "lon": 103.8198},
        {"name": "Bali", "country": "Indonesia", "lat": -8.3405, "lon": 115.0920},
        {"name": "Seoul", "country": "South Korea", "lat": 37.5665, "lon": 126.9780},
        {"name": "Hong Kong", "country": "China", "lat": 22.3193, "lon": 114.1694},
        {"name": "Phuket", "country": "Thailand", "lat": 7.8804, "lon": 98.3923},
        {"name": "Dubai", "country": "United Arab Emirates", "lat": 25.2048, "lon": 55.2708},
        {"name": "Maldives", "country": "Maldives", "lat": 3.2028, "lon": 73.2207},
    ],
    "Africa": [
        {"name": "Cape Town", "country": "South Africa", "lat": -33.9249, "lon": 18.4241},
        {"name": "Marrakesh", "country": "Morocco", "lat": 31.6295, "lon": -7.9811},
        {"name": "Cairo", "country": "Egypt", "lat": 30.0444, "lon": 31.2357},
        {"name": "Zanzibar", "country": "Tanzania", "lat": -6.1659, "lon": 39.2026},
        {"name": "Nairobi", "country": "Kenya", "lat": -1.2921, "lon": 36.8219},
        {"name": "Victoria Falls", "country": "Zimbabwe", "lat": -17.9243, "lon": 25.8572},
        {"name": "Mauritius", "country": "Mauritius", "lat": -20.3484, "lon": 57.5522},
        {"name": "Seychelles", "country": "Seychelles", "lat": -4.6796, "lon": 55.4920},
        {"name": "Dakar", "country": "Senegal", "lat": 14.7167, "lon": -17.4677},
        {"name": "Accra", "country": "Ghana", "lat": 5.6037, "lon": -0.1870},
    ],
    "Australia & Oceania": [
        {"name": "Sydney", "country": "Australia", "lat": -33.8688, "lon": 151.2093},
        {"name": "Melbourne", "country": "Australia", "lat": -37.8136, "lon": 144.9631},
        {"name": "Brisbane", "country": "Australia", "lat": -27.4698, "lon": 153.0251},
        {"name": "Perth", "country": "Australia", "lat": -31.9523, "lon": 115.8613},
        {"name": "Auckland", "country": "New Zealand", "lat": -36.8509, "lon": 174.7645},
        {"name": "Queenstown", "country": "New Zealand", "lat": -45.0312, "lon": 168.6626},
        {"name": "Fiji", "country": "Fiji", "lat": -17.7134, "lon": 178.0650},
        {"name": "Tahiti", "country": "French Polynesia", "lat": -17.6509, "lon": -149.4260},
        {"name": "Bora Bora", "country": "French Polynesia", "lat": -16.5004, "lon": -151.7415},
        {"name": "Gold Coast", "country": "Australia", "lat": -28.0167, "lon": 153.4000},
    ],
}

def fetch_json(url: str, timeout: int = 180) -> Any:
    last_error: Exception | None = None
    for attempt in range(5):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "WillItRainOnMyVacation/1.1",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code != 429 or attempt == 4:
                raise RuntimeError(
                    f"Weather data service returned HTTP {exc.code}."
                ) from exc
            retry_after = exc.headers.get("Retry-After")
            wait_seconds = float(retry_after) if retry_after else 2 ** attempt
            time.sleep(min(wait_seconds, 20))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == 4:
                break
            time.sleep(2 ** attempt)
    raise RuntimeError(f"Weather data service did not respond: {last_error}")

def cache_path(prefix: str, lat: float, lon: float) -> Path:
    safe = f"{lat:.4f}_{lon:.4f}".replace("-", "m").replace(".", "_")
    return CACHE_DIR / f"{prefix}_{safe}.json"

def load_cache(path: Path, max_age_seconds: int) -> Any | None:
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > max_age_seconds:
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

def save_cache(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")

def historical_daily(destination: dict[str, Any]) -> dict[str, dict[str, float]]:
    path = cache_path("history", destination["lat"], destination["lon"])
    cached = load_cache(path, 30 * 24 * 3600)
    if cached is not None:
        return cached

    end_year = date.today().year - 1
    start_year = end_year - (_HISTORY_YEARS - 1)
    params = urllib.parse.urlencode({
        "latitude": destination["lat"],
        "longitude": destination["lon"],
        "start_date": f"{start_year}-01-01",
        "end_date": f"{end_year}-12-31",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "temperature_unit": "fahrenheit",
        "precipitation_unit": "inch",
        "timezone": "UTC",
        "models": "era5_land",
    })
    data = fetch_json(f"{ARCHIVE_URL}?{params}")
    daily = data.get("daily", {})
    times = daily.get("time", [])
    highs = daily.get("temperature_2m_max", [])
    lows = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_sum", [])

    grouped: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"high": [], "low": [], "precip": []}
    )
    for i, day_text in enumerate(times):
        key = day_text[5:10]
        high = highs[i] if i < len(highs) else None
        low = lows[i] if i < len(lows) else None
        amount = precip[i] if i < len(precip) else None
        if isinstance(high, (int, float)):
            grouped[key]["high"].append(float(high))
        if isinstance(low, (int, float)):
            grouped[key]["low"].append(float(low))
        if isinstance(amount, (int, float)):
            grouped[key]["precip"].append(float(amount))

    result: dict[str, dict[str, float]] = {}
    for key, values in grouped.items():
        if not values["high"] or not values["low"] or not values["precip"]:
            continue
        result[key] = {
            "high": sum(values["high"]) / len(values["high"]),
            "low": sum(values["low"]) / len(values["low"]),
            "significantPrecipProbability": (
                sum(v >= _PRECIP_THRESHOLD_INCHES for v in values["precip"])
                / len(values["precip"])
                * 100
            ),
        }
    save_cache(path, result)
    return result

def collect_members(daily: dict[str, Any], base: str, index: int) -> list[float]:
    values: list[float] = []
    direct = daily.get(base)
    if isinstance(direct, list) and index < len(direct):
        value = direct[index]
        if isinstance(value, (int, float)):
            values.append(float(value))
    prefix = f"{base}_member"
    for key, series in daily.items():
        if key.startswith(prefix) and isinstance(series, list) and index < len(series):
            value = series[index]
            if isinstance(value, (int, float)):
                values.append(float(value))
    return values

def seasonal_range(
    destination: dict[str, Any], start: date, end: date
) -> dict[str, dict[str, float]]:
    params = urllib.parse.urlencode({
        "latitude": destination["lat"],
        "longitude": destination["lon"],
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "temperature_unit": "fahrenheit",
        "precipitation_unit": "inch",
        "timezone": "UTC",
        "cell_selection": "nearest",
        "models": "ecmwf_seasonal_seamless",
    })
    data = fetch_json(f"{SEASONAL_URL}?{params}")
    daily = data.get("daily", {})
    times = daily.get("time", [])
    result: dict[str, dict[str, float]] = {}

    for i, day_text in enumerate(times):
        highs = collect_members(daily, "temperature_2m_max", i)
        lows = collect_members(daily, "temperature_2m_min", i)
        precip = collect_members(daily, "precipitation_sum", i)
        if not highs or not lows:
            continue
        result[day_text] = {
            "high": sum(highs) / len(highs),
            "low": sum(lows) / len(lows),
            "significantPrecipProbability": (
                sum(v >= _PRECIP_THRESHOLD_INCHES for v in precip)
                / len(precip)
                * 100
                if precip else 0.0
            ),
        }
    return result


def _historical_from_api_data(data: dict[str, Any]) -> dict[str, dict[str, float]]:
    daily = data.get("daily", {})
    times = daily.get("time", [])
    highs = daily.get("temperature_2m_max", [])
    lows = daily.get("temperature_2m_min", [])
    precip = daily.get("precipitation_sum", [])

    grouped: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"high": [], "low": [], "precip": []}
    )
    for i, day_text in enumerate(times):
        key = day_text[5:10]
        high = highs[i] if i < len(highs) else None
        low = lows[i] if i < len(lows) else None
        amount = precip[i] if i < len(precip) else None
        if isinstance(high, (int, float)):
            grouped[key]["high"].append(float(high))
        if isinstance(low, (int, float)):
            grouped[key]["low"].append(float(low))
        if isinstance(amount, (int, float)):
            grouped[key]["precip"].append(float(amount))

    result: dict[str, dict[str, float]] = {}
    for key, values in grouped.items():
        if not values["high"] or not values["low"] or not values["precip"]:
            continue
        result[key] = {
            "high": sum(values["high"]) / len(values["high"]),
            "low": sum(values["low"]) / len(values["low"]),
            "significantPrecipProbability": (
                sum(v >= _PRECIP_THRESHOLD_INCHES for v in values["precip"])
                / len(values["precip"])
                * 100
            ),
        }
    return result


def historical_daily_batch(
    destinations: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, float]]]:
    results: dict[str, dict[str, dict[str, float]]] = {}
    missing: list[dict[str, Any]] = []

    for destination in destinations:
        path = cache_path("history", destination["lat"], destination["lon"])
        cached = load_cache(path, 30 * 24 * 3600)
        if cached is not None:
            results[destination["name"]] = cached
        else:
            missing.append(destination)

    if not missing:
        return results

    end_year = date.today().year - 1
    start_year = end_year - (_HISTORY_YEARS - 1)
    params = urllib.parse.urlencode({
        "latitude": ",".join(str(item["lat"]) for item in missing),
        "longitude": ",".join(str(item["lon"]) for item in missing),
        "start_date": f"{start_year}-01-01",
        "end_date": f"{end_year}-12-31",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "temperature_unit": "fahrenheit",
        "precipitation_unit": "inch",
        "timezone": "UTC",
        "models": "era5_land",
    })
    raw = fetch_json(f"{ARCHIVE_URL}?{params}", timeout=240)
    payloads = raw if isinstance(raw, list) else [raw]

    if len(payloads) != len(missing):
        raise RuntimeError("Historical weather batch returned an unexpected result count.")

    for destination, payload in zip(missing, payloads):
        parsed = _historical_from_api_data(payload)
        results[destination["name"]] = parsed
        save_cache(cache_path("history", destination["lat"], destination["lon"]), parsed)

    return results


def _seasonal_from_api_data(data: dict[str, Any]) -> dict[str, dict[str, float]]:
    daily = data.get("daily", {})
    times = daily.get("time", [])
    result: dict[str, dict[str, float]] = {}

    for i, day_text in enumerate(times):
        highs = collect_members(daily, "temperature_2m_max", i)
        lows = collect_members(daily, "temperature_2m_min", i)
        precip = collect_members(daily, "precipitation_sum", i)
        if not highs or not lows:
            continue
        result[day_text] = {
            "high": sum(highs) / len(highs),
            "low": sum(lows) / len(lows),
            "significantPrecipProbability": (
                sum(v >= _PRECIP_THRESHOLD_INCHES for v in precip)
                / len(precip) * 100
                if precip else 0.0
            ),
        }
    return result


def seasonal_range_batch(
    destinations: list[dict[str, Any]], start: date, end: date
) -> dict[str, dict[str, dict[str, float]]]:
    params = urllib.parse.urlencode({
        "latitude": ",".join(str(item["lat"]) for item in destinations),
        "longitude": ",".join(str(item["lon"]) for item in destinations),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "temperature_unit": "fahrenheit",
        "precipitation_unit": "inch",
        "timezone": "UTC",
        "cell_selection": "nearest",
        "models": "ecmwf_seasonal_seamless",
    })
    raw = fetch_json(f"{SEASONAL_URL}?{params}", timeout=180)
    payloads = raw if isinstance(raw, list) else [raw]

    if len(payloads) != len(destinations):
        raise RuntimeError("Seasonal weather batch returned an unexpected result count.")

    return {
        destination["name"]: _seasonal_from_api_data(payload)
        for destination, payload in zip(destinations, payloads)
    }


def blend_day(
    historical: dict[str, float], seasonal: dict[str, float] | None
) -> dict[str, float]:
    if seasonal is None:
        return historical
    return {
        "high": _HISTORICAL_WEIGHT * historical["high"] + _MODEL_WEIGHT * seasonal["high"],
        "low": _HISTORICAL_WEIGHT * historical["low"] + _MODEL_WEIGHT * seasonal["low"],
        "significantPrecipProbability": (
            _HISTORICAL_WEIGHT * historical["significantPrecipProbability"]
            + _MODEL_WEIGHT * seasonal["significantPrecipProbability"]
        ),
    }

def includes_full_weekend(start: date, trip_days: int) -> bool:
    days = {start + timedelta(days=i) for i in range(trip_days)}
    return any(d.weekday() == 5 for d in days) and any(d.weekday() == 6 for d in days)

def weekdays_only(start: date, trip_days: int) -> bool:
    return all((start + timedelta(days=i)).weekday() < 5 for i in range(trip_days))

def candidate_starts(
    earliest: date,
    latest_return: date,
    trip_days: int,
    weekend_preference: str,
) -> list[date]:
    last_start = latest_return - timedelta(days=trip_days - 1)
    if last_start < earliest:
        return []
    starts = []
    current = earliest
    while current <= last_start:
        allowed = True
        if weekend_preference == "include":
            allowed = includes_full_weekend(current, trip_days)
        elif weekend_preference == "weekdays":
            allowed = weekdays_only(current, trip_days)
        if allowed:
            starts.append(current)
        current += timedelta(days=1)
    return starts

def score_window(days: list[dict[str, float]], priority: str) -> float:
    avg_high = sum(d["high"] for d in days) / len(days)
    avg_low = sum(d["low"] for d in days) / len(days)
    avg_precip = sum(d["significantPrecipProbability"] for d in days) / len(days)
    spread = max(d["high"] for d in days) - min(d["high"] for d in days)

    comfort = max(0.0, 100.0 - abs(avg_high - 76.0) * 3.0 - abs(avg_low - 60.0) * 1.3)
    dryness = max(0.0, 100.0 - avg_precip)
    stability = max(0.0, 100.0 - spread * 4.0)

    if priority == "warm":
        score = 0.50 * comfort + 0.35 * max(0.0, min(100.0, (avg_high - 45) * 2.2)) + 0.15 * dryness
    elif priority == "dry":
        score = 0.70 * dryness + 0.20 * comfort + 0.10 * stability
    elif priority == "beach":
        beach_temp = max(0.0, 100.0 - abs(avg_high - 82.0) * 4.0)
        score = 0.55 * beach_temp + 0.35 * dryness + 0.10 * stability
    elif priority == "outdoor":
        outdoor_temp = max(0.0, 100.0 - abs(avg_high - 70.0) * 4.0)
        score = 0.45 * outdoor_temp + 0.40 * dryness + 0.15 * stability
    elif priority == "winter":
        winter_temp = max(0.0, 100.0 - abs(avg_high - 34.0) * 3.0)
        score = 0.65 * winter_temp + 0.20 * stability + 0.15 * avg_precip
    else:
        score = 0.50 * comfort + 0.35 * dryness + 0.15 * stability

    return max(0.0, min(100.0, score))

def outlook(score: float) -> str:
    if score >= 85:
        return "Excellent"
    if score >= 72:
        return "Very Good"
    if score >= 60:
        return "Good"
    if score >= 48:
        return "Fair"
    return "Weather Risk"

def evaluate_destination(
    destination: dict[str, Any],
    earliest: date,
    latest_return: date,
    trip_days: int,
    weekend_preference: str,
    priority: str,
    history: dict[str, dict[str, float]],
    seasonal: dict[str, dict[str, float]],
) -> dict[str, Any] | None:
    starts = candidate_starts(earliest, latest_return, trip_days, weekend_preference)
    best: dict[str, Any] | None = None

    for start in starts:
        daily_results = []
        complete = True
        for i in range(trip_days):
            target = start + timedelta(days=i)
            historical = history.get(target.strftime("%m-%d"))
            if not historical:
                complete = False
                break
            daily_results.append(blend_day(historical, seasonal.get(target.isoformat())))
        if not complete:
            continue

        score = score_window(daily_results, priority)
        avg_high = sum(d["high"] for d in daily_results) / trip_days
        avg_low = sum(d["low"] for d in daily_results) / trip_days
        avg_precip = sum(d["significantPrecipProbability"] for d in daily_results) / trip_days
        candidate = {
            "destination": destination["name"],
            "country": destination["country"],
            "latitude": destination["lat"],
            "longitude": destination["lon"],
            "startDate": start.isoformat(),
            "endDate": (start + timedelta(days=trip_days - 1)).isoformat(),
            "tripDays": trip_days,
            "averageHigh": round(avg_high, 1),
            "averageLow": round(avg_low, 1),
            "significantPrecipProbability": round(avg_precip),
            "score": round(score),
            "outlook": outlook(score),
            "daily": [
                {
                    "date": (start + timedelta(days=i)).isoformat(),
                    "high": round(daily_results[i]["high"], 1),
                    "low": round(daily_results[i]["low"], 1),
                    "significantPrecipProbability": round(
                        daily_results[i]["significantPrecipProbability"]
                    ),
                }
                for i in range(trip_days)
            ],
        }
        if best is None or candidate["score"] > best["score"]:
            best = candidate
    return best

@app.get("/")
def home():
    return render_template("index.html", regions=sorted(REGIONS.keys()))

@app.get("/api/geocode")
def geocode():
    name = request.args.get("name", "").strip()
    if len(name) < 2:
        return jsonify({"error": "Enter at least two characters."}), 400
    params = urllib.parse.urlencode({
        "name": name,
        "count": 8,
        "language": "en",
        "format": "json",
    })
    try:
        return jsonify(fetch_json(f"{GEOCODING_URL}?{params}"))
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

@app.post("/api/plan")
def plan():
    try:
        payload = request.get_json(force=True)
        region = str(payload.get("region", ""))
        earliest = date.fromisoformat(payload["earliestDate"])
        latest_return = date.fromisoformat(payload["latestReturn"])
        trip_days = int(payload["tripDays"])
        weekend_preference = str(payload.get("weekendPreference", "any"))
        priority = str(payload.get("priority", "overall"))

        if region not in REGIONS:
            raise ValueError("Choose a valid region.")
        if earliest < date.today():
            raise ValueError("Earliest departure cannot be in the past.")
        if latest_return < earliest:
            raise ValueError("Latest return must follow earliest departure.")
        if (latest_return - date.today()).days > _MAX_FORECAST_DAYS:
            raise ValueError("The latest return must be within approximately seven months.")
        if trip_days < 2 or trip_days > 30:
            raise ValueError("Trip length must be between 2 and 30 days.")
        if weekend_preference == "weekdays" and trip_days > 5:
            raise ValueError("Weekdays Only is available only for a five-day trip.")

        destinations = REGIONS[region]
        histories = historical_daily_batch(destinations)
        seasonal_data = seasonal_range_batch(
            destinations, earliest, latest_return
        )

        results = []
        failures = []
        for destination in destinations:
            try:
                result = evaluate_destination(
                    destination,
                    earliest,
                    latest_return,
                    trip_days,
                    weekend_preference,
                    priority,
                    histories.get(destination["name"], {}),
                    seasonal_data.get(destination["name"], {}),
                )
                if result:
                    results.append(result)
            except Exception as exc:
                failures.append(f"{destination['name']}: {exc}")

        results.sort(key=lambda item: item["score"], reverse=True)
        if not results:
            detail = "; ".join(failures[:3])
            raise RuntimeError(
                "No recommendations could be calculated for this request."
                + (f" Details: {detail}" if detail else "")
            )

        return jsonify({
            "region": region,
            "recommendations": results[:5],
            "evaluatedDestinations": len(REGIONS[region]),
        })
    except (ValueError, KeyError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        app.logger.exception("Vacation planning failed")
        return jsonify({"error": str(exc)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False)
