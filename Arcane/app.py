import streamlit as st
import requests
from geopy.geocoders import Nominatim
import pymysql

def get_connection():
    timeout = 10
    conn = pymysql.connect(
        charset="utf8mb4",
        connect_timeout=timeout,
        cursorclass=pymysql.cursors.DictCursor,
        db="defaultdb",
        host="mysql-2c95a0b8-farmer-2024.h.aivencloud.com",
        password="AVNS_v_4126KzUUG5et4Mkct",
        read_timeout=timeout,
        port=16785,
        user="avnadmin",
        write_timeout=timeout,
    )
    return conn

def get_weather_data(coords):
    lat, lon = coords
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None

def get_soils():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT soil_type FROM crops")
    s = cursor.fetchall()
    cursor.close()
    conn.close()
    soil_types = [row['soil_type'] for row in s]
    return soil_types

def filter_crops_by_soil(soil_type):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM crops WHERE soil_type = %s", (soil_type,))
    crops = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Convert each tuple in crops to a list
    filter_crops = [dict(row) for row in crops]  # Use dict to access by column name
    return filter_crops

def calculate_profitability(crop, current_temp, current_rainfall):
    yield_per_acre = crop['yield_acre']
    profit_kg = crop['profit_kg']
    
    # Calculate temperature and rainfall shifts based on the current weather
    temp_shift = current_temp - ((crop['min_temp'] + crop['max_temp']) / 2)
    rain_shift = current_rainfall - crop['max_rainfall']

    # Define maximum shifts for normalization
    max_temp_shift = 10  # Max acceptable temperature shift
    max_rain_shift = 200  # Max acceptable rainfall shift

    # Calculate factors based on shifts
    temp_factor = 1 - min(max(abs(temp_shift) / max_temp_shift, 0), 1)
    rain_factor = 1 - min(max(abs(rain_shift) / max_rain_shift, 0), 1)
    
    # Calculate profitability
    profitability = yield_per_acre * profit_kg * temp_factor * rain_factor
    return profitability, calculate_risk_of_failure(temp_shift, rain_shift)

def calculate_risk_of_failure(temp_shift, rain_shift):
    # Risk of failure scales with the degree of deviation from optimal conditions
    max_temp_shift = 10  # Define acceptable temperature deviation
    max_rain_shift = 200  # Define acceptable rainfall deviation

    temp_risk = min(max(abs(temp_shift) / max_temp_shift, 0), 1)
    rain_risk = min(max(abs(rain_shift) / max_rain_shift, 0), 1)
    
    # Combined risk (average of temp and rain risk)
    risk_of_failure = (temp_risk + rain_risk) / 2
    return risk_of_failure

def calculate_score(profitability, risk_of_failure):
    if risk_of_failure >= 1:
        return 0  # No viable crop if the risk is too high
    return profitability / (1 + risk_of_failure)  # Score calculation

def main():
    st.title("Farm Profitability Maximizer")
    
    # User inputs
    location = st.text_input("Enter your location:")
    geolocator = Nominatim(user_agent="farmer.io")
    
    if location:
        coords = geolocator.geocode(location)
        if coords:
            st.write(f"Location found: {coords.address}")
            weather_data = get_weather_data((coords.latitude, coords.longitude))
            if weather_data:
                current_temp = weather_data['current_weather']['temperature']
                current_rainfall = weather_data.get('current_weather', {}).get('precipitation', 0)  # Adjust based on the actual API response structure
                st.write(f"Current temperature: {current_temp}°C")
                st.write(f"Current rainfall: {current_rainfall} mm")  # Make sure this key exists in the response
            else:
                st.warning("Could not retrieve weather data.")
        else:
            st.warning("Location not found. Please try again.")
    
    soils = get_soils()
    if soils:
        soil_type = st.selectbox("Select your soil type:", options=soils)

        filtered_crops = []  # Initialize the variable

        if st.button("Get Crop Information"):
            # Filter crops by soil type
            filtered_crops = filter_crops_by_soil(soil_type)

            # Display information for each crop
            if filtered_crops:
                crops_with_scores = []
                
                # Calculate profitability, risk, and score for each crop and store it with the crop details
                for crop in filtered_crops:
                    profitability, risk_of_failure = calculate_profitability(crop, current_temp, current_rainfall)
                    score = calculate_score(profitability, risk_of_failure)
                    crops_with_scores.append((crop, profitability, risk_of_failure, score))
                
                # Sort crops by score in descending order
                crops_with_scores.sort(key=lambda x: x[3], reverse=True)

                # Display sorted crops
                for crop, profitability, risk, score in crops_with_scores:
                    st.subheader(f"Crop: {crop['crop_name']}")
                    st.write(
                        f"Soil Type: {crop['soil_type']} | "
                        f"Min Temp (°C): {crop['min_temp']} | "
                        f"Max Temp (°C): {crop['max_temp']} | "
                        f"Min Rainfall (mm): {crop['min_rainfall']} | "
                        f"Max Rainfall (mm): {crop['max_rainfall']} | "
                        f"Harvest Time (days): {crop['harvest_time']} | "
                        f"Spoil Time (days): {crop['spoil_time']} | "
                        f"Profitability: {profitability:.2f} | "
                        f"Risk of Failure: {risk:.2f} | "
                        f"Score: {score:.2f}"
                    )
            else:
                st.info("No crops found for the selected soil type.")
    else:
        st.warning("No soil types found in the database.")

if __name__ == "__main__":
    main()




