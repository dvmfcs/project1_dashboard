import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import pydeck as pdk
from datetime import datetime, timedelta
import io

st.set_page_config(
    page_title="Texas Property Market Dashboard",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===========================
# DATA LOADING & CACHING
# ===========================

def load_data():
    """Load Airbnb data from CSV"""
    try:
        if "uploaded_file" in st.session_state and st.session_state.uploaded_file is not None:
            df = pd.read_csv(st.session_state.uploaded_file)
            print("Loaded from uploaded file")
        else:
            df = pd.read_csv("airbnb_texas.csv")
            print("Loaded from airbnb_texas.csv")
    except FileNotFoundError:
        print("File not found, generating sample data")
        df = generate_sample_data()

    print(f"Rows after load: {len(df)}")
    print(f"Columns: {list(df.columns)}")

    # Rename columns to match app expectations
    column_mapping = {
        "average_rate_per_night": "price",
        "bedrooms_count": "bedrooms",
        "date_of_listing": "listing_date",
        "title": "name",
        "longtitude": "longitude"
    }

    df = df.rename(columns=column_mapping)
    print(f"Columns after rename: {list(df.columns)}")

    # Clean price - remove $, commas, etc
    if "price" in df.columns:
        df["price"] = df["price"].astype(str).str.replace("$", "").str.replace(",", "").str.strip()
        print(f"Sample prices: {df['price'].head(3).tolist()}")

    # Convert data types
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["bedrooms"] = pd.to_numeric(df["bedrooms"], errors="coerce")
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df["listing_date"] = pd.to_datetime(df["listing_date"], errors="coerce")

    print(f"Rows after conversion: {len(df)}")
    print(f"Sample prices after conversion: {df['price'].head(3).tolist()}")
    print(f"Valid prices (>0): {len(df[df['price'] > 0])}")

    # Fill missing values instead of removing rows
    if "bedrooms" in df.columns:
        df["bedrooms"] = df["bedrooms"].fillna(df["bedrooms"].median())

    if "price" in df.columns:
        df["price"] = df["price"].fillna(df["price"].median())

    if "latitude" in df.columns:
        df["latitude"] = df["latitude"].fillna(0.0)

    if "longitude" in df.columns:
        df["longitude"] = df["longitude"].fillna(0.0)

    # Remove rows with invalid prices only
    if "price" in df.columns:
        df = df[df["price"] > 0]

    print(f"Final rows: {len(df)}")
    return df


def generate_sample_data():
    """Generate sample Airbnb Texas data"""
    np.random.seed(42)

    cities = ["Houston", "Austin", "Dallas", "San Antonio", "Fort Worth",
              "El Paso", "Arlington", "Corpus Christi", "Plano", "Garland",
              "New Braunfels", "Galveston", "Fredericksburg", "San Marcos", "Marble Falls"]

    city_coords = {
        "Houston": (29.7604, -95.3698),
        "Austin": (30.2672, -97.7431),
        "Dallas": (32.7767, -96.7970),
        "San Antonio": (29.4241, -98.4936),
        "Fort Worth": (32.7555, -97.3308),
        "El Paso": (31.7619, -106.4850),
        "Arlington": (32.7357, -97.2239),
        "Corpus Christi": (27.5598, -97.1599),
        "Plano": (33.0198, -96.6989),
        "Garland": (32.9128, -96.6348),
        "New Braunfels": (29.7010, -97.9196),
        "Galveston": (29.3011, -94.7977),
        "Fredericksburg": (30.2709, -98.8755),
        "San Marcos": (29.8833, -97.9413),
        "Marble Falls": (30.5633, -98.2839),
    }

    n_records = 500
    data = []

    for i in range(n_records):
        city = np.random.choice(cities)
        lat, lon = city_coords[city]
        lat += np.random.normal(0, 0.1)
        lon += np.random.normal(0, 0.1)

        bedrooms = np.random.choice([1, 2, 3, 4, 5, 6])
        price = np.random.gamma(2, 100) * bedrooms + np.random.normal(50, 20)
        price = max(50, min(price, 1000))

        listing_date = datetime.now() - timedelta(days=np.random.randint(1, 730))

        data.append({
            "name": f"{city} Property {i+1}",
            "city": city,
            "price": round(price, 2),
            "bedrooms": bedrooms,
            "latitude": lat,
            "longitude": lon,
            "listing_date": listing_date,
        })

    return pd.DataFrame(data)


# ===========================
# TITLE
# ===========================

st.title("Texas Property Market Dashboard")
st.markdown("Explore Airbnb property listings across Texas with interactive filters and analysis.")

# ===========================
# LOAD DATA & SIDEBAR FILTERS
# ===========================

df = load_data()

with st.sidebar:
    st.header("Filters")

    all_cities = sorted(df["city"].unique())
    selected_cities = st.multiselect(
        "Select Cities",
        options=all_cities,
        default=all_cities[:3] if len(all_cities) >= 3 else all_cities,
    )

    # Safe min/max calculations with fallbacks
    try:
        bedroom_min = int(df["bedrooms"].min())
        bedroom_max = int(df["bedrooms"].max())
    except (ValueError, TypeError):
        bedroom_min = 1
        bedroom_max = 6

    bedroom_range = st.slider(
        "Minimum Bedrooms",
        min_value=bedroom_min,
        max_value=bedroom_max,
        value=1,
    )

    try:
        min_price = float(df["price"].min())
        max_price = float(df["price"].max())
    except (ValueError, TypeError):
        min_price = 50.0
        max_price = 500.0

    price_range = st.slider(
        "Price Range (USD)",
        min_value=min_price,
        max_value=max_price,
        value=(min_price, max_price),
        step=10.0,
    )

    try:
        min_date = df["listing_date"].dropna().min()
        max_date = df["listing_date"].dropna().max()
        if pd.isna(min_date) or pd.isna(max_date):
            raise ValueError("No valid dates")
    except:
        min_date = pd.Timestamp.now() - timedelta(days=365)
        max_date = pd.Timestamp.now()
    date_range = st.date_input(
        "Listing Date Range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
    )

    st.divider()
    st.subheader("Upload Your Data")
    uploaded = st.file_uploader(
        "Upload CSV with columns: name, city, price, bedrooms, latitude, longitude, listing_date",
        type="csv"
    )
    if uploaded is not None:
        st.session_state.uploaded_file = uploaded
        st.success("CSV loaded! Refresh to see your data.")


# ===========================
# APPLY FILTERS
# ===========================

if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
    date_start, date_end = date_range
else:
    date_start = date_range
    date_end = date_range

filtered_df = df[
    (df["city"].isin(selected_cities)) &
    (df["bedrooms"] >= bedroom_range) &
    (df["price"] >= price_range[0]) &
    (df["price"] <= price_range[1]) &
    (df["listing_date"] >= pd.Timestamp(date_start)) &
    (df["listing_date"] <= pd.Timestamp(date_end))
].copy()

if len(filtered_df) == 0:
    st.warning(f"No properties match your filters. Loaded {len(df)} total properties.")
    filtered_df = df  # Show all data if filters are too strict

col1, col2, col3 = st.columns(3)
col1.metric("Filtered Listings", len(filtered_df))
col2.metric("Cities Selected", len(selected_cities))
col3.metric("Price Range", f"${price_range[0]:.0f} - ${price_range[1]:.0f}")

st.divider()

st.write(f"**Total rows loaded:** {len(df)}")
st.write(f"**Number of Cities:** {len(df['city'].unique())}")

st.divider()

# ===========================
# TABS
# ===========================

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Map View", "Price Analysis", "Data Explorer"])

# TAB 1: OVERVIEW
with tab1:
    st.subheader("Overview & Key Metrics")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Listings", len(filtered_df))
    col2.metric("Average Price", f"${filtered_df['price'].mean():.2f}" if len(filtered_df) > 0 else "$0")
    col3.metric("Median Price", f"${filtered_df['price'].median():.2f}" if len(filtered_df) > 0 else "$0")

    city_count = filtered_df["city"].value_counts()
    top_city = city_count.index[0] if len(city_count) > 0 else "N/A"
    col4.metric("Most Popular City", top_city)

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Average Price by City (Top 15)")
        if len(filtered_df) > 0:
            city_price = filtered_df.groupby("city")["price"].mean().sort_values(ascending=False).head(15)
            fig = px.bar(
                x=city_price.values,
                y=city_price.index,
                labels={"x": "Average Price (USD)", "y": "City"},
                color=city_price.values,
                color_continuous_scale="Blues",
                orientation="h"
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Bedroom Distribution")
        if len(filtered_df) > 0:
            bedroom_counts = filtered_df["bedrooms"].value_counts().sort_index()
            fig = px.pie(
                values=bedroom_counts.values,
                names=[f"{int(b)} BR" for b in bedroom_counts.index],
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)


# TAB 2: MAP VIEW
with tab2:
    st.subheader("Interactive Map of Properties")

    if len(filtered_df) > 0:
        map_df = filtered_df.dropna(subset=["latitude", "longitude"]).copy()

        if len(map_df) > 0:
            map_df["price_bin"] = pd.cut(
                map_df["price"],
                bins=4,
                labels=["Budget", "Moderate", "Premium", "Luxury"]
            )

            color_map = {
                "Budget": (0, 255, 0),
                "Moderate": (255, 200, 0),
                "Premium": (255, 100, 0),
                "Luxury": (255, 0, 0)
            }

            map_df["color"] = map_df["price_bin"].astype(str).map(color_map)

            layer = pdk.Layer(
                "ScatterplotLayer",
                map_df,
                get_position=["longitude", "latitude"],
                get_color="color",
                get_radius=300,
                pickable=True,
            )

            view_state = pdk.ViewState(
                latitude=map_df["latitude"].mean(),
                longitude=map_df["longitude"].mean(),
                zoom=6,
                bearing=0,
                pitch=0,
            )

            deck = pdk.Deck(
                layers=[layer],
                initial_view_state=view_state,
                tooltip={"html": "<b>{name}</b><br/>Price: ${price}<br/>Bedrooms: {bedrooms}<br/>City: {city}"}
            )

            st.pydeck_chart(deck, use_container_width=True)

            st.markdown("""
            **Price Legend:**
            - Green: Budget
            - Yellow: Moderate
            - Orange: Premium
            - Red: Luxury
            """)
        else:
            st.warning("No valid location data to display map.")
    else:
        st.warning("No properties match your filters.")


# TAB 3: PRICE ANALYSIS
with tab3:
    st.subheader("Price Distribution & Trends")

    if len(filtered_df) > 0:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("##### Price Distribution")
            fig = px.histogram(
                filtered_df,
                x="price",
                nbins=30,
                labels={"price": "Price (USD)", "count": "Count"}
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.markdown("##### Price by Bedroom Count")
            fig = px.box(
                filtered_df,
                x="bedrooms",
                y="price",
                color="bedrooms",
                labels={"bedrooms": "Bedrooms", "price": "Price (USD)"}
            )
            fig.update_layout(height=400, showlegend=False)
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("##### Listings Over Time")
        if len(filtered_df) > 1 and filtered_df["listing_date"].notna().any():
            listings_over_time = filtered_df.groupby(filtered_df["listing_date"].dt.to_period("M")).size()
            listings_over_time.index = listings_over_time.index.to_timestamp()

            fig = px.line(
                x=listings_over_time.index,
                y=listings_over_time.values,
                labels={"x": "Date", "y": "New Listings"},
                markers=True
            )
            fig.update_layout(height=400, hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)


# TAB 4: DATA EXPLORER
with tab4:
    st.subheader("Property Data Table")

    if len(filtered_df) > 0:
        display_df = filtered_df[["name", "city", "price", "bedrooms", "listing_date"]].copy()
        display_df["price"] = display_df["price"].apply(lambda x: f"${x:.2f}")
        display_df["listing_date"] = display_df["listing_date"].dt.strftime("%Y-%m-%d")

        st.dataframe(display_df, use_container_width=True, hide_index=True)

        csv_buffer = io.StringIO()
        filtered_df.to_csv(csv_buffer, index=False)
        csv_data = csv_buffer.getvalue().encode()

        st.download_button(
            label="Download Filtered Data (CSV)",
            data=csv_data,
            file_name=f"texas_properties_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
        )

st.divider()
st.caption(f"Dashboard updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
