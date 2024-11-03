import streamlit as st
import requests
from geopy.geocoders import Nominatim
import pymysql
import pandas as pd
import numpy as np

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
    # Get current weather
    url_current = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
    response_current = requests.get(url_current)
    
    # Get 16-day weather forecast
    url_forecast = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=precipitation_sum&timezone=auto"
    response_forecast = requests.get(url_forecast)

    if response_current.status_code == 200 and response_forecast.status_code == 200:
        current_data = response_current.json()
        forecast_data = response_forecast.json()

        current_temp = current_data['current_weather']['temperature']
        yearly_precip = sum(forecast_data['daily']['precipitation_sum'])  # Summing daily precipitation for annual estimate
        return current_temp, yearly_precip
    else:
        return None, None

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
    return [dict(row) for row in crops]  # Convert to dict for easy access by column name

def calculate_profitability(crop, current_temp, yearly_rainfall):
    yield_per_acre = crop['yield_acre'] * 1000  # Convert tonnes to kg
    profit_kg = crop['profit_kg']
    market_price = crop['market_price']  # Market price per kg of the crop
    cost_of_inputs = crop['cost_of_inputs']  # Cost of inputs for the crop

    median_temp = (crop['min_temp'] + crop['max_temp']) / 2
    median_precip = (crop['min_rainfall'] + crop['max_rainfall']) / 2

    # Adjustments for temperature and rainfall deviations
    temp_dev = max(0, 1 - abs(median_temp - current_temp) / 10)  # Temperature adjustment
    precip_dev = max(0, 1 - abs(median_precip - yearly_rainfall) / 100)  # Rainfall adjustment

    # Ensure adjustments are not too severe, setting minimum adjustment values to 0.25
    if temp_dev < 0.25:  # Minimum temperature adjustment
        temp_dev = 0.25
    if precip_dev < 0.25:  # Minimum rainfall adjustment
        precip_dev = 0.25

    # Adjusted yield based on environmental conditions
    adjusted_yield = yield_per_acre * temp_dev * precip_dev

    # Calculate profitability
    adjusted_profitability = (adjusted_yield * profit_kg * market_price) - cost_of_inputs

    # Calculate maximum potential profitability for normalization
    max_profitability = (yield_per_acre * profit_kg * market_price) - cost_of_inputs

    # Normalize the profitability to a scale of 0 to 1
    if max_profitability > 0:
        normalized_profitability = adjusted_profitability / max_profitability
    else:
        normalized_profitability = 0.0  # In case of no profit, return 0

    return normalized_profitability

def calculate_risk_of_failure(crop, current_temp, yearly_rainfall):
    median_temp = (crop['min_temp'] + crop['max_temp']) / 2
    median_precip = (crop['min_rainfall'] + crop['max_rainfall']) / 2

    temp_risk = min(max(abs(median_temp - current_temp) / 10, 0), 1)
    rain_risk = min(max(abs(median_precip - yearly_rainfall) / 100, 0), 1)

    risk_of_failure = (temp_risk + rain_risk) / 2
    return risk_of_failure

def calculate_score(profitability, risk_of_failure):
    if risk_of_failure >= 1:
        return 0  # No viable crop if the risk is too high
    return profitability / (1 + risk_of_failure)  # Score calculation

def calculate_best_planting_cycle(crops_with_data):
    # Sort crops by score to find the best planting options
    crops_sorted = sorted(crops_with_data, key=lambda x: x['Score'], reverse=True)
    best_cycles = []

    # Create a simple planting cycle based on the top crops
    for crop in crops_sorted[:5]:  # Take the top 5 crops for the planting cycle
        best_cycles.append(crop['Crop'])

    return best_cycles

def main():
    st.title("Farming Profitability Maximizer")

    # User inputs
    location = st.text_input("Enter your location:")
    geolocator = Nominatim(user_agent="farmer.io")

    if location:
        coords = geolocator.geocode(location)
        if coords:
            st.write(f"Location found: {coords.address}")
            current_temp, yearly_rainfall = get_weather_data((coords.latitude, coords.longitude))
            if current_temp is not None:
                st.write(f"Current temperature: {current_temp}°C")
                st.write(f"Yearly rainfall estimate: {yearly_rainfall} mm")
                
                # Get soil types
                soils = get_soils()
                soil_type = st.selectbox("Select your soil type:", options=soils)

                # Filter crops by soil type
                filtered_crops = filter_crops_by_soil(soil_type)

                crops_with_data = []
                # Calculate profitability, risk, and score for each crop
                for crop in filtered_crops:
                    profitability = calculate_profitability(crop, current_temp, yearly_rainfall)
                    risk_of_failure = calculate_risk_of_failure(crop, current_temp, yearly_rainfall)
                    score = calculate_score(profitability, risk_of_failure)

                    # Only include crops with non-negative scores
                    if score > 0:  # Changed from score >= 0 to score > 0 to exclude zero scores
                        crops_with_data.append({
                            'Crop': crop['name'],
                            'Soil Type': crop['soil_type'],
                            'Min Temp (°C)': crop['min_temp'],
                            'Max Temp (°C)': crop['max_temp'],
                            'Min Rainfall (mm)': crop['min_rainfall'],
                            'Max Rainfall (mm)': crop['max_rainfall'],
                            'Profitability': f"{profitability:.2f}",
                            'Risk of Failure': f"{risk_of_failure:.2f}",
                            'Score': f"{score:.2f}",
                        })

                # Sort crops by score in descending order
                crops_with_data.sort(key=lambda x: x['Score'], reverse=True)

                # Display crops in a table format
                st.subheader("Crop Details")
                st.table(crops_with_data)  # Display the crops data in a table format
                
                # Calculate the best planting cycle based on crops with the highest scores
                best_planting_cycle = calculate_best_planting_cycle(crops_with_data)

                if best_planting_cycle:
                    st.subheader("Best Planting Cycle")
                    st.write(" → ".join(best_planting_cycle)) 

            else:
                st.warning("Could not retrieve weather data.")
        else:
            st.warning("Location not found. Please try again.")

if __name__ == "__main__":
    main()










