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
    filter_crops = [list(row.values()) for row in crops]  # Use .values() for DictCursor
    return filter_crops

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
                st.write(f"Current temperature: {weather_data['current_weather']['temperature']}°C")
        else:
            st.warning("Location not found. Please try again.")
    
    soils = get_soils()  # Make sure to fetch soils here
    if soils:
        soil_type = st.selectbox("Select your soil type:", options=soils)

        filtered_crops = []  # Initialize the variable

        if st.button("Get Crop Information"):
            # Filter crops by soil type
            filtered_crops = filter_crops_by_soil(soil_type)

            # Display information for each crop
            if filtered_crops:
                for crop in filtered_crops:
                    st.subheader(f"Crop: {crop[0]}")
                    st.write(
                        f"Soil Type: {crop[1]} | "
                        f"Min Temp (°C): {crop[2]} | "
                        f"Max Temp (°C): {crop[3]} | "
                        f"Min Rainfall (mm): {crop[4]} | "
                        f"Max Rainfall (mm): {crop[5]} | "
                        f"Harvest Time (days): {crop[6]} | "
                        f"Spoil Time (days): {crop[7]}"
                    )
            else:
                st.info("No crops found for the selected soil type.")
    else:
        st.warning("No soil types found in the database.")

if __name__ == "__main__":
    main()

