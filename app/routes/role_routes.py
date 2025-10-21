from flask import Blueprint,Response, render_template, request, redirect, url_for, make_response, jsonify
from app.models.db import get_db_connection, insert_update_user, fetch_history, delete_weather, weather_base_info,update_weather_info
import requests
from io import StringIO
import csv


role_bp = Blueprint('role_bp', __name__)
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
REVERSE_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/reverse"


# ----------------------
# Login
# ----------------------
@role_bp.route('/login', methods=['GET', 'POST'])
def loginnew():
    if request.method == 'POST':
        username = request.form.get('username')
        userpassword = request.form.get('userpassword')

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT userid, fullname FROM tbl_user WHERE username=%s AND password=%s",
            (username, userpassword)
        )
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            user_id, fullname = user
            resp = make_response(redirect("/"))
            resp.set_cookie("name", fullname, max_age=60*60*24*7)
            resp.set_cookie("user_id", str(user_id), max_age=60*60*24*7)
            return resp
        else:
            return render_template('login.html', message="Invalid username or password.")

    return render_template('login.html')


# ----------------------
# Dashboard
# ----------------------


@role_bp.route('/')
def index():
    user_id = request.cookies.get('user_id')   # cookie থেকে user_id নেওয়া হচ্ছে

    if not user_id:   # যদি cookie না থাকে
        return render_template('login.html')  # login page এ redirect করবে
    else:
        return render_template('dashboard.html')       # cookie থাকলে dashboard দেখাবে


# ----------------------
# Weather History
# ----------------------
@role_bp.route('/history')
def history():
    rows = fetch_history()
    return render_template('history.html', rows=rows)


# ----------------------
# Delete Weather Entry
# ----------------------
@role_bp.route('/roledelete')
def deletehistory():
    weatherid = request.args.get('id')
    if weatherid:
        delete_weather(weatherid)

    return redirect(url_for('role_bp.history'))


# ----------------------
# Edit Weather Entry Form
# ----------------------
@role_bp.route('/roleedit')
def edithistory():
    weatherid = request.args.get('id')
    if not weatherid:
        return redirect(url_for('role_bp.history'))
    row = weather_base_info(weatherid)
    return render_template('weatheredit.html', row=row)


# ----------------------
# Update Weather Entry
# ----------------------
@role_bp.route('/weatherupdate', methods=['POST'])
def weatherupdate():
    weatherid = request.form.get('weatherid')
    location = request.form.get('location')
    date = request.form.get('date')
    temp_max = request.form.get('temp_max')
    temp_min = request.form.get('temp_min')
    description = request.form.get('description')

    if weatherid:
        update_weather_info(location, date, temp_max, temp_min, description, weatherid)


    return redirect(url_for('role_bp.history'))


# ----------------------
# User Add
# ----------------------
@role_bp.route('/user_add', methods=['GET', 'POST'])
def user_add():
    message = ""
    if request.method == 'POST':
        fullname = request.form.get('fullname')
        username = request.form.get('username')
        userpassword = request.form.get('userpassword')
        user_id = request.form.get('user_id')
        message = insert_update_user(fullname, username, userpassword, user_id)

    return render_template('user_add.html', message=message)


# ----------------------
# Fetch Weather from API
# ----------------------
@role_bp.route("/weather", methods=["POST"])
def get_weather():
    location = request.form.get("location")
    lat = request.form.get("lat")
    lon = request.form.get("lon")
    fromdate = request.form.get("fromdate")
    todate = request.form.get("todate")

    # 🌍 Geocode or Reverse Geocode
    if not (lat and lon):
        geo_response = requests.get(GEOCODE_URL, params={"name": location, "count": 1})
        geo_data = geo_response.json()
        if "results" not in geo_data or len(geo_data["results"]) == 0:
            return jsonify({"error": "Location not found"}), 404
        lat = geo_data["results"][0]["latitude"]
        lon = geo_data["results"][0]["longitude"]
        city = geo_data["results"][0].get("name", location)
        country = geo_data["results"][0].get("country", "")
    else:
        try:
            lat = float(lat)
            lon = float(lon)
            rev_geo_resp = requests.get(REVERSE_GEOCODE_URL, params={
                "latitude": lat,
                "longitude": lon,
                "count": 1
            })
            rev_geo = rev_geo_resp.json()
            results = rev_geo.get("results")
            if results and len(results) > 0:
                city = results[0].get("name", "Your Location")
                country = results[0].get("country", "")
            else:
                city = "Your Location"
                country = ""
        except:
            city = "Your Location"
            country = ""

    # 🌦 Fetch Weather
    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": fromdate,
        "end_date": todate,
        "daily": ["temperature_2m_max", "temperature_2m_min", "weathercode"],
        "timezone": "auto",
        "current_weather": True
    }
    weather_response = requests.get(WEATHER_URL, params=params)
    weather_data = weather_response.json()

    if "daily" not in weather_data or "time" not in weather_data["daily"]:
        return jsonify({"error": "Weather data not found"}), 404

    current = weather_data.get("current_weather", {})
    current_info = {
        "city": city,
        "country": country,
        "temp": current.get("temperature", "N/A"),
        "windspeed": current.get("windspeed", "N/A"),
        "description": get_weather_description(current.get("weathercode", 0))
    }

    # 📆 Forecast
    forecast_data = []
    for i in range(len(weather_data["daily"]["time"])):
        forecast_data.append({
            "date": weather_data["daily"]["time"][i],
            "temp_max": weather_data["daily"]["temperature_2m_max"][i],
            "temp_min": weather_data["daily"]["temperature_2m_min"][i],
            "description": get_weather_description(weather_data["daily"]["weathercode"][i])
        })

    # 💾 Save to DB
    conn = get_db_connection()
    cur = conn.cursor()
    location_name = f"{city}, {country}" if country else city
    for entry in forecast_data:
        cur.execute("""
              INSERT INTO tbl_weather (location, date, temp_max, temp_min, description, userid)
              VALUES (%s, %s, %s, %s, %s, %s)
          """, (
            location_name,
            entry["date"],
            entry["temp_max"],
            entry["temp_min"],
            entry["description"],
            int(request.cookies.get("user_id"))
        ))
    conn.commit()
    cur.close()
    conn.close()

    resp = make_response(jsonify({"current": current_info, "forecast": forecast_data}))
    resp.set_cookie("location", location_name, max_age=60*60*24*7)
    return resp

@role_bp.route('/export_csv')
def export_csv():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT weatherid, location, date, temp_max, temp_min, description FROM tbl_weather WHERE userid = %s",
        (int(request.cookies.get("user_id")),)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()

    # Create CSV in memory
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Location', 'Date', 'Temp Max', 'Temp Min', 'Description'])
    writer.writerows(rows)
    csv_data = output.getvalue()
    output.close()

    # Send response as downloadable CSV
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment;filename=weather_history.csv"}
    )

def get_weather_description(code):
    codes = {
        0: "Clear Sky", 1: "Mainly Clear", 2: "Partly Cloudy", 3: "Overcast",
        45: "Fog", 48: "Depositing Rime Fog", 51: "Light Drizzle", 53: "Moderate Drizzle",
        55: "Dense Drizzle", 61: "Slight Rain", 63: "Moderate Rain", 65: "Heavy Rain",
        71: "Slight Snow Fall", 73: "Moderate Snow Fall", 75: "Heavy Snow Fall",
        80: "Rain Showers", 81: "Moderate Showers", 82: "Violent Showers",
        95: "Thunderstorm", 99: "Thunderstorm with Hail"
    }
    return codes.get(code, "Unknown")
