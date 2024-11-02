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
    # Current weather and forecast for the next 16 days
    forecast_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=auto&forecast=16"
    response = requests.get(forecast_url)
    
    if response.status_code == 200:
        forecast_data = response.json()
        daily_max_temps = forecast_data['daily']['temperature_2m_max']
        daily_min_temps = forecast_data['daily']['temperature_2m_min']
        daily_precipitation = forecast_data['daily']['precipitation_sum']
        
        # Get current weather
        current_temp_url = f"https://api.open-meteo.com/v1/current?latitude={lat}&longitude={lon}&current_weather=true"
        current_response = requests.get(current_temp_url)
        
        if current_response.status_code == 200:
            current_weather = current_response.json()
            current_temp = current_weather['current_weather']['temperature']
        else:
            current_temp = None
        
        return current_temp, daily_max_temps, daily_min_temps, daily_precipitation
    else:
        return None, None, None, None

def get_historical_weather_data(coords):
    lat, lon = coords
    historical_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&past_days=90&daily=temperature_2m_max,temperature_2m_min,precipitation_sum&timezone=auto"
    response = requests.get(historical_url)

    if response.status_code == 200:
        historical_data = response.json()
        historical_max_temps = historical_data['daily']['temperature_2m_max']
        historical_min_temps = historical_data['daily']['temperature_2m_min']
        historical_precipitation = historical_data['daily']['precipitation_sum']
        return historical_max_temps, historical_min_temps, historical_precipitation
    else:
        return None, None, None

def forecast_weather(coords):
    # Get historical weather data for the past three months
    historical_max, historical_min, historical_precip = get_historical_weather_data(coords)
    
    # Get current and forecast weather data
    current_temp, forecast_max, forecast_min, forecast_precip = get_weather_data(coords)

    # Simulate monthly weather conditions
    monthly_forecast = []
    
    # Calculate average monthly values based on past historical data and forecast
    if historical_max and historical_min and historical_precip and forecast_max and forecast_min and forecast_precip:
        # Combine historical and forecast data to create a smooth forecast
        for month in range(12):
            if month < 3:  # For the first 3 months, use historical data
                avg_max = np.mean(historical_max[-30 * (3 - month):])  # Get last 30 days of each month
                avg_min = np.mean(historical_min[-30 * (3 - month):])
                avg_precip = np.mean(historical_precip[-30 * (3 - month):])
            else:  # For the next months, use forecast data
                avg_max = np.mean(forecast_max[max(0, month - 3):month + 1])  # Take an average for a smooth transition
                avg_min = np.mean(forecast_min[max(0, month - 3):month + 1])
                avg_precip = np.mean(forecast_prec[max(0, month - 3):month + 1])

            monthly_forecast.append((avg_max, avg_min, avg_precip))

        return monthly_forecast
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
    filter_crops = [dict(row) for row in crops]  # Convert to dict for easy access by column name
    return filter_crops

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
    base_profitability = (yield_per_acre * profit_kg * market_price) - cost_of_inputs
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

def best_planting_cycle(filtered_crops, monthly_forecast):
    planting_schedule = []
    month = 0  # Start from the first month
    while month < 12:
        crop_scores = []
        
        for crop in filtered_crops:
            avg_temp = (monthly_forecast[month][0] + monthly_forecast[month][1]) / 2  # Average temperature for the month
            avg_precip = monthly_forecast[month][2]  # Average precipitation for the month
            profitability = calculate_profitability(crop, avg_temp, avg_precip)
            risk_of_failure = calculate_risk_of_failure(crop, avg_temp, avg_precip)
            score = calculate_score(profitability, risk_of_failure)
            crop_scores.append((crop['name'], score, crop['harvest_time']))

        # Sort crops by score
        crop_scores.sort(key=lambda x: x[1], reverse=True)

        # Select the best crop for the month
        if crop_scores:
            best_crop = crop_scores[0]
            planting_schedule.append((best_crop[0], month + 1))  # Store the crop name and month
            month += best_crop[2]  # Move to the next available month based on harvest time

    return planting_schedule

def main():
    st.title("Farm Profitability Maximizer")
    
    # User inputs
    location = st.text_input("Enter your location:")
    geolocator = Nominatim(user_agent="farmer.io")
    
    if location:
        coords = geolocator.geocode(location)
        if coords:
            st.write(f"Location found: {coords.address}")
            monthly_forecast = forecast_weather((coords.latitude, coords.longitude))
            if monthly_forecast is not None:
                current_temp = monthly_forecast[0][0]  # Use first month temp for current temp
                st.write("Monthly Weather Forecast:")
                for month, (max_temp, min_temp, precip) in enumerate(monthly_forecast):
                    st.write(f"Month {month + 1}: Max Temp: {max_temp:.2f}°C, Min Temp: {min_temp:.2f}°C, Precipitation: {precip:.2f} mm")
            else:
                st.warning("Could not retrieve weather data.")
        else:
            st.warning("Location not found. Please try again.")
    
    soils = get_soils()
    if soils:
        soil_type = st.selectbox("Select your soil type:", options=soils)

        if st.button("Get Crop Information"):
            # Filter crops by soil type
            filtered_crops = filter_crops_by_soil(soil_type)

            # Display information for each crop
            if filtered_crops:
                crops_with_scores = []
                
                # Calculate profitability, risk, and score for each crop
                for crop in filtered_crops:
                    profitability = calculate_profitability(crop, current_temp, monthly_forecast[0][2])  # Using first month precip
                    risk_of_failure = calculate_risk_of_failure(crop, current_temp, monthly_forecast[0][2])
                    score = calculate_score(profitability, risk_of_failure)
                    crops_with_scores.append((crop, profitability, risk_of_failure, score))
                
                # Sort crops by score in descending order
                crops_with_scores.sort(key=lambda x: x[3], reverse=True)

                # Display sorted crops
                for crop, profitability, risk, score in crops_with_scores:
                    st.subheader(f"Crop: {crop['name']}")
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
                
                # Calculate and display the best planting cycle
                if st.button("Calculate Best Planting Cycle"):
                    planting_schedule = best_planting_cycle(filtered_crops, monthly_forecast)
                    st.subheader("Best Planting Cycle")
                    for crop_name, month in planting_schedule:
                        st.write(f"**Plant {crop_name} in Month {month}**")
                
            else:
                st.info("No crops found for the selected soil type.")
    else:
        st.warning("No soil types found in the database.")

if __name__ == "__main__":
    main()
