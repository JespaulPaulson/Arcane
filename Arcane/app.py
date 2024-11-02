import streamlit as st
import mysql.connector
import requests
from geopy.geocoders import Nominatim

def create_connection():
    conn = mysql.connector.connect(
        host='127.0.0.1',
        user='root',
        password='1234',
        database='farm'
    )
    return conn

def list_crops_by_profitability(crops):
    return sorted(crops, key=lambda x: x['profitability'], reverse=True)

def filter_crops_by_soil(crops, soil_type):
    return [crop for crop in crops if crop['soil_type'] == soil_type]

def calculate_failure_risk(crop, weather_data):
    # Placeholder logic for risk calculation
    if weather_data['main']['temp'] < crop['min_temp'] or weather_data['main']['temp'] > crop['max_temp']:
        return "High"
    return "Low"

def get_crop_maintenance_instructions(crop_name):
    maintenance_instructions = {
        'wheat': "Maintain pH between 6.0 and 7.0. Water regularly.",
        'corn': "Maintain pH between 5.8 and 7.0. Fertilize every 4-6 weeks.",
        # Add more crops here
    }
    return maintenance_instructions.get(crop_name, "Instructions not available.")

def notify_weather_events(weather_data):
    if 'rain' in weather_data['weather'][0]['description']:
        return "Warning: Rain expected! Take precautions."
    return "Weather is stable."

def get_supply_demand_data(crop_name):
    supply_demand_data = {
        'wheat': {'supply': 5000, 'demand': 6000},
        'corn': {'supply': 7000, 'demand': 8000},
        # Add more crops here
    }
    return supply_demand_data.get(crop_name, "Data not available.")

def predict_crop_spoilage(crop_name, harvest_date, weather_history):
    spoilage_time = {
        'wheat': 30,  # days until spoilage
        'corn': 20,
        # Add more crops here
    }
    
    # Logic to calculate spoilage based on past weather events can go here
    return spoilage_time.get(crop_name, "Spoilage data not available.")


def get_weather_data(coords):
    lat, lon = coords
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    else:
        return None

def fetch_crop_prices():
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT crop_name, price FROM crops, crop_prices")  # Adjust your query as needed
    results = cursor.fetchall()
    cursor.close()
    conn.close()
    return results

def main():
    st.title("Farm Profitability Maximizer")

    # User inputs
    location = st.text_input("Enter your location:")
    geolocator = Nominatim(user_agent="farmer.io")
    coords = geolocator.geocode(location)

    soil_type = st.text_input("Select your soil type:")
    
    # Example crop data (this could be fetched from a database or API in a real application)
    crops = [
        {'name': 'wheat', 'profitability': 200, 'soil_type': 'loamy', 'min_temp': 10, 'max_temp': 30},
        {'name': 'corn', 'profitability': 150, 'soil_type': 'sandy', 'min_temp': 15, 'max_temp': 35},
        # Add more crops here
    ]

    if st.button("Get Crop Information"):
        # Get weather data
        weather_data = get_weather_data(coords)
            
        profitable_crops = list_crops_by_profitability(crops)

        # Filter crops by soil type
        filtered_crops = filter_crops_by_soil(profitable_crops, soil_type)

        # Display information for each crop
        for crop in filtered_crops:
            st.subheader(f"Crop: {crop['name']}")
            # Calculate failure risk
            '''risk = calculate_failure_risk(crop, weather_data)
            st.write(f"Failure Risk: {risk}")

            # Get maintenance instructions
            instructions = get_crop_maintenance_instructions(crop['name'])
            st.write(f"Maintenance Instructions: {instructions}")

            # Notify about weather events
            notification = notify_weather_events(weather_data)
            st.write(notification)

            # Supply and demand data
            supply_demand = get_supply_demand_data(crop['name'])
            st.write(f"Supply: {supply_demand['supply']}, Demand: {supply_demand['demand']}")
            st.write("-" * 40)'''

if __name__ == "__main__":
    main()