import streamlit as st
import requests
from geopy.geocoders import Nominatim
import pymysql
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

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

# Function to load inventory records
def load_inventory():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM inventory")
    inventory = cursor.fetchall()
    cursor.close()
    conn.close()
    return pd.DataFrame(inventory, columns=['id', 'crop_name', 'quantity', 'unit', 'cost_per_unit', 'location', 'notes'])

# Function to insert a new inventory record
def insert_inventory_record(crop_name, quantity, unit, cost_per_unit, location, notes):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        sql = """INSERT INTO inventory (crop_name, quantity, unit, cost_per_unit, location, notes)
                 VALUES (%s, %s, %s, %s, %s, %s)"""
        cursor.execute(sql, (crop_name, quantity, unit, cost_per_unit, location, notes))
        conn.commit()  # Commit the transaction
        st.success("Record inserted successfully!")
    except Exception as e:
        st.error(f"Error inserting record: {e}")
    finally:
        cursor.close()
        conn.close()

# Function to delete an inventory record
def delete_inventory_record(record_id):
    conn = get_connection()
    try:
        cursor = conn.cursor()
        sql = "DELETE FROM inventory WHERE id = %s"
        cursor.execute(sql, (record_id,))
        conn.commit()  # Commit the transaction
        st.success("Record deleted successfully!")
    except Exception as e:
        st.error(f"Error deleting record: {e}")
    finally:
        cursor.close()
        conn.close()

def plot_crops_scores(crops_with_data):
    # Convert crops data to DataFrame
    df = pd.DataFrame(crops_with_data)

    # Filter out any rows with NaN values in Score
    df = df.dropna(subset=['Score'])

    if df.empty:
        st.write("No valid data to display in graph.")
        return

    # Plotting scores
    plt.figure(figsize=(10, 5))
    
    # Plot the scores
    plt.plot(df['Crop'], df['Score'], label='Crop Score', color='blue', marker='o')
    
    # Fill the area below the score line for visual representation
    plt.fill_between(df['Crop'], df['Score'], color='lightblue', alpha=0.5)

    plt.xlabel("Crops")
    plt.ylabel("Score")
    plt.title("Crop Scores by Location")
    plt.xticks(rotation=45)
    plt.legend()
    plt.grid()
    plt.tight_layout()
    st.pyplot(plt)  # Display the plot in Streamlit

def main():
    st.title("Farm Profitability Maximizer")

    # Navigation
    page = st.selectbox("Select a page:", ["Home", "Inventory"])

    if page == "Home":
        location = st.text_input("Enter your location:")
        soils = get_soils()
        soil_type = st.selectbox("Select your soil type:", options=soils)

        if location:
            geolocator = Nominatim(user_agent="farmer.io")
            coords = geolocator.geocode(location)
            
            if coords:
                st.write(f"Location: {coords.address}")
                current_temp, yearly_rainfall = get_weather_data((coords.latitude, coords.longitude))
                if current_temp is not None:

                                        # Get all crops from the database
                    filtered_crops = filter_crops_by_soil(soil_type)  # Adjusted to get all crops

                    all_crops_with_data = []  # To store all crops with calculated scores

                    # Calculate profitability, risk, and score for each crop
                    for crop in filtered_crops:
                        profitability = calculate_profitability(crop, current_temp, yearly_rainfall)
                        risk_of_failure = calculate_risk_of_failure(crop, current_temp, yearly_rainfall)
                        score = calculate_score(profitability, risk_of_failure)

                        # Append to the list of all crops regardless of soil type
                        all_crops_with_data.append({
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

                    # Filter crops based on the selected soil type
                    filtered_crops_with_scores = [
                        crop for crop in all_crops_with_data if crop['Soil Type'] == soil_type
                    ]

                    # Sort crops by score in descending order
                    filtered_crops_with_scores.sort(key=lambda x: x['Score'], reverse=True)

                    # Create Tabs for different sections
                    tab1, tab2, tab3 = st.tabs(["Crop Details", "Weather Information", "Best Planting Cycle"])
                    
                    with tab1:
                        st.subheader("Crop Details")
                        st.table(crops_with_data)  # Display the crops data in a table format

                    with tab2:
                        st.subheader("Weather Information")
                        st.write(f"Current temperature: {current_temp}°C")
                        st.write(f"Estimated yearly rainfall: {yearly_rainfall} mm")
                    
                    with tab3:
                        st.subheader("Best Planting Cycle")
                        best_cycle = calculate_best_planting_cycle(crops_with_data)
                        st.write(f"The best planting cycle is: {', '.join(best_cycle)}")

                    # Plot the graph below the other details
                    st.subheader("Crop Scores Graph")
                    plot_crops_scores(crops_with_data)

    elif page == "Inventory":
        # Streamlit app starts here
        st.title("Inventory Management")

        # Load the inventory records
        if 'inventory' not in st.session_state:
            st.session_state.inventory = load_inventory()

        # Display the inventory records
        st.subheader("Current Inventory")
        df = st.session_state.inventory
        st.dataframe(df)

        # Inputs for adding a new record
        st.subheader("Add New Inventory Record")
        crop_name = st.text_input("Crop Name")
        quantity = st.number_input("Quantity", min_value=0)
        unit = st.selectbox("Unit", options=["kg", "lbs"])
        cost_per_unit = st.number_input("Cost per Unit", min_value=0.0, format="%.2f")
        location = st.text_input("Location")
        notes = st.text_area("Notes")

        if st.button("Add Record"):
            insert_inventory_record(crop_name, quantity, unit, cost_per_unit, location, notes)
            # Reload inventory to refresh the displayed records
            st.session_state.inventory = load_inventory()

        # Delete functionality
        if not df.empty:
            st.subheader("Delete Inventory Record")
            record_ids = df['id'].tolist()
            record_to_delete = st.selectbox("Select Record to Delete", options=record_ids, format_func=lambda x: f"{df.loc[df['id'] == x, 'crop_name'].values[0]} (ID: {x})")

            if st.button("Delete Record"):
                delete_inventory_record(record_to_delete)
                # Reload inventory to refresh the displayed records
                st.session_state.inventory = load_inventory()

if __name__ == "__main__":
    main()












