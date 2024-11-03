import streamlit as st
import requests
from geopy.geocoders import Nominatim
import pymysql
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

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
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true&daily=precipitation_sum,temperature_2m_max,temperature_2m_min&timezone=auto"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        current_temp = data['current_weather']['temperature']
        yearly_precip = sum(data['daily']['precipitation_sum'])
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

def calculate_best_planting_cycle(crops_with_data):
    # Sort crops by score to find the best planting options
    crops_sorted = sorted(crops_with_data, key=lambda x: x['Score'], reverse=True)
    best_cycles = []

    # Create a simple planting cycle based on the top crops
    for crop in crops_sorted[:5]:  # Take the top 5 crops for the planting cycle
        best_cycles.append(crop['Crop'])

    return best_cycles

def load_inventory():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventory")
    inventory = cursor.fetchall()
    cursor.close()
    conn.close()
    return pd.DataFrame(inventory)

# Graph plotting function with refined data handling
import matplotlib.pyplot as plt

# Updated graph plotting function
import matplotlib.pyplot as plt

def plot_graphs(crops_with_data):
    # Convert data to DataFrame
    df = pd.DataFrame(crops_with_data)

    # Convert columns to numeric, forcing errors to NaN to avoid any data issues
    df['Profitability'] = pd.to_numeric(df['Profitability'], errors='coerce')
    df['Risk of Failure'] = pd.to_numeric(df['Risk of Failure'], errors='coerce')

    # Filter out any rows with NaN values in Profitability or Risk of Failure
    df = df.dropna(subset=['Profitability', 'Risk of Failure'])

    if df.empty:
        st.write("No valid data to display in graphs.")
        return

    # Plot combined line graph with shaded area
    st.subheader("Profitability and Risk of Failure Analysis")
    fig, ax = plt.subplots(figsize=(10, 5))

    # Plot Profitability
    ax.plot(df['Crop'], df['Profitability'], label='Profitability', color='blue', marker='o')
    
    # Plot Risk of Failure
    ax.plot(df['Crop'], df['Risk of Failure'], label='Risk of Failure', color='red', marker='o')

    # Fill between the two lines to show the score area
    ax.fill_between(df['Crop'], df['Profitability'], df['Risk of Failure'], where=(df['Profitability'] > df['Risk of Failure']),
                    color='lightgreen', alpha=0.5, label='Score Area (Profitability > Risk)')

    ax.set_xlabel("Crop")
    ax.set_ylabel("Values")
    ax.set_title("Profitability vs Risk of Failure for Crops")
    ax.legend()
    plt.xticks(rotation=45)
    st.pyplot(fig)

def main():
    st.title("Farm Profitability Maximizer")

    # Navigation
    page = st.sidebar.selectbox("Select a page:", ["Home", "Inventory", "Graphs"])

    if page == "Home":
        location = st.text_input("Enter your location:")
        if location:
            geolocator = Nominatim(user_agent="farmer.io")
            coords = geolocator.geocode(location)

            soils = get_soils()
            soil_type = st.selectbox("Select your soil type:", options=soils)
            
            if coords:
                st.write(f"Location: {coords.address}")
                current_temp, yearly_rainfall = get_weather_data((coords.latitude, coords.longitude))
                if current_temp is not None:

                    # Filter crops by soil type
                    filtered_crops = filter_crops_by_soil(soil_type)

                    crops_with_data = []
                    # Calculate profitability, risk, and score for each crop
                    for crop in filtered_crops:
                        profitability = calculate_profitability(crop, current_temp, yearly_rainfall)
                        risk_of_failure = calculate_risk_of_failure(crop, current_temp, yearly_rainfall)
                        score = calculate_score(profitability, risk_of_failure)

                        # Only include crops with non-negative scores
                        if score > 0:  # Only include crops with positive scores
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

                    # Create Tabs for different sections
                    tab1, tab2, tab3 = st.tabs(["Crop Details", "Weather Information", "Best Planting Cycle"])
                    
                    with tab1:
                        st.subheader("Crop Details")
                        st.table(crops_with_data)  # Display the crops data in a table format

                        # Plot the graphs below the crop details
                        plot_graphs(crops_with_data)

                    with tab2:
                        st.subheader("Weather Information")
                        st.write(f"Current temperature: {current_temp}°C")
                        st.write(f"Estimated yearly rainfall: {yearly_rainfall} mm")
                    
                    with tab3:
                        st.subheader("Best Planting Cycle")
                        best_planting_cycle = calculate_best_planting_cycle(crops_with_data)
                        st.write(" -> ".join(best_planting_cycle))  # Display the best planting cycle
                else:
                    st.warning("No crop data available for plotting. Please check the Home page.")
            else:
                st.warning("Could not retrieve weather data.")
        else:
            st.warning("Location not found. Please try again.")
    elif page == "Inventory":
        st.subheader("Inventory Management")
        inventory_df = load_inventory()
        st.table(inventory_df)  # Display the inventory in a table format

if __name__ == "__main__":
    main()











