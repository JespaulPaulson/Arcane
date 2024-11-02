import streamlit as st
import mysql.connector
import requests
from geopy.geocoders import Nominatim

def create_connection():
    conn = mysql.connector.connect(
        host= st.secrets.DB_HOST,
        user= st.secrets.DB_USER,
        password= st.secrets.DB_PASSWORD,
        database= st.secrets.DB_NAME
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
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT soil_type FROM crops")
    s = [ x[1] for x in cursor.fetchall() ]
    cursor.close()
    conn.close()
    return s

def filter_crops_by_soil(soil_type):
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM crops WHERE soil_type = {soil_type}")
    filter_crops = cursor.fetchall()
    cursor.close()
    conn.close()
    return filter_crops

def main():
    st.title("Farm Profitability Maximizer")

    # User inputs
    location = st.text_input("Enter your location:")
    geolocator = Nominatim(user_agent="farmer.io")
    coords = geolocator.geocode(location)
   
    soils = get_soils()
    soil_type = st.selectbox("Select your soil type:", soils)

    if st.button("Get Crop Information"):
        
        # Filter crops by soil type
        filtered_crops = filter_crops_by_soil(soil_type)

        #profitable_crops = list_crops_by_profitability(filtered_crops)

    # Display information for each crop
    for crop in filtered_crops:
        st.subheader(f"Crop: {crop['name']}")
        st.write(
            f"**Soil Type:** {crop['soil_type']} | "
            f"**Min Temp (°C):** {crop['min_temp']} | "
            f"**Max Temp (°C):** {crop['max_temp']} | "
            f"**Min Rainfall (mm):** {crop['min_rainfall']} | "
            f"**Max Rainfall (mm):** {crop['max_rainfall']} | "
            f"**Harvest Time (days):** {crop['harvest_time']} | "
            f"**Spoil Time (days):** {crop['spoil_time']}"
        )

if __name__ == "__main__":
    main()