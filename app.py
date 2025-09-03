import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials

# ======================
# 1. Google Sheets Setup
# ======================
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

# Ambil secrets dari Streamlit Cloud
sa_info = dict(st.secrets["gcp_service_account"])
sa_info["private_key"] = sa_info["private_key"].replace("\\n", "\n")

creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
client = gspread.authorize(creds)

# ID Google Sheet
SHEET_ID = "1hhr1KjWSAU49wJQhcH_3Js_N8-VQA0WX2fZoGhs3m0w"
worksheet = client.open_by_key(SHEET_ID).sheet1

# Load data dari sheet
data = worksheet.get_all_records()
df = pd.DataFrame(data)
df.columns = df.columns.str.strip()

# Ensure numeric coords (X = lat, Y = lon)
df["X"] = pd.to_numeric(df["X"], errors="coerce")  # latitude
df["Y"] = pd.to_numeric(df["Y"], errors="coerce")  # longitude

# Add new columns if not exist
for col, default in [("Panjang Aktual", 0.0), ("Uang Terserap", 0.0), ("Progress Control", 0.0)]:
    if col not in df.columns:
        df[col] = default

# Calculate progress: Panjang Aktual / Usulan Panjang
df["Progress Control"] = (
    df["Panjang Aktual"].astype(float) / df["Usulan Panjang (m)"].replace(0, 1).astype(float)
) * 100

# Function to get marker color
def get_marker_color(progress):
    if progress < 25:
        return "#FF0000"  # red
    elif progress < 50:
        return "#FF8000"  # orange
    elif progress < 75:
        return "#FFD700"  # yellow
    elif progress < 100:
        return "#7CBE19"  # light green
    else:
        return "#145214"  # dark green

# ======================
# 2. Map
# ======================
# ======================
# 2. Map (using ESRI tiles)
# ======================
m = folium.Map(
    location=[df["X"].mean(), df["Y"].mean()],  # X = latitude, Y = longitude
    zoom_start=12,
    tiles=None
)

# Add ESRI basemap
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
    attr="Tiles © Esri — Source: Esri, Maxar, Earthstar Geographics",
    name="Esri World Imagery"
).add_to(m)

# Optionally also add another basemap
folium.TileLayer(
    tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
    attr="Tiles © Esri — Source: Esri, DeLorme, NAVTEQ",
    name="Esri World Street Map"
).add_to(m)

# Add marker points
for i, row in df.iterrows():
    if pd.notnull(row["X"]) and pd.notnull(row["Y"]):
        popup_html = f"""
        <b>Kelompok:</b> {row.get('NAMA KELOMPOK', i)}<br>
        Usulan Panjang (m): {row.get('Usulan Panjang (m)', 0)}<br>
        Kebutuhan Anggaran: {row.get('KEBUTUHAN ANGGARAN', 0)}<br>
        Panjang Aktual: {row.get('Panjang Aktual', 0)}<br>
        Uang Terserap: {row.get('Uang Terserap', 0)}<br>
        Progress Control: {row.get('Progress Control', 0):.2f}%
        """
        folium.CircleMarker(
            location=[row["X"], row["Y"]],  # [lat, lon]
            radius=7,
            color=get_marker_color(row["Progress Control"]),
            fill=True,
            fill_color=get_marker_color(row["Progress Control"]),
            popup=folium.Popup(popup_html, max_width=300),
        ).add_to(m)

# Add layer control to switch basemaps
folium.LayerControl().add_to(m)

# Add legend
m.get_root().html.add_child(folium.Element(legend_html))

# Render
st_folium(m, width=600, height=600)


# ======================
# 3. User input section
# ======================
st.write("### Update Data")
kelompok_list = df["NAMA KELOMPOK"].dropna().unique().tolist()
selected_kelompok = st.selectbox("Pilih NAMA KELOMPOK", options=kelompok_list)

if selected_kelompok:
    idx = df[df["NAMA KELOMPOK"] == selected_kelompok].index[0]

    # Non-editable info
    st.info(f"Usulan Panjang (m): {df.loc[idx, 'Usulan Panjang (m)']}")
    st.info(f"Kebutuhan Anggaran: {df.loc[idx, 'KEBUTUHAN ANGGARAN']}")
    st.info(f"Progress Control: {df.loc[idx, 'Progress Control']:.2f}%")

    # Editable inputs
    panjang_aktual = st.number_input("Panjang Aktual (m)", value=float(df.loc[idx, "Panjang Aktual"]), step=0.1)
    uang_terserap = st.number_input("Uang Terserap", value=float(df.loc[idx, "Uang Terserap"]), step=1000.0)

    if st.button("Simpan Perubahan"):
        df.loc[idx, "Panjang Aktual"] = panjang_aktual
        df.loc[idx, "Uang Terserap"] = uang_terserap
        df.loc[idx, "Progress Control"] = (
            (panjang_aktual / df.loc[idx, "Usulan Panjang (m)"]) * 100
            if df.loc[idx, "Usulan Panjang (m)"] > 0 else 0
        )

        # Update hanya baris terkait di Google Sheets
        row_number = idx + 2  # header = row 1
        worksheet.update_cell(row_number, df.columns.get_loc("Panjang Aktual") + 1, str(panjang_aktual))
        worksheet.update_cell(row_number, df.columns.get_loc("Uang Terserap") + 1, str(uang_terserap))
        worksheet.update_cell(row_number, df.columns.get_loc("Progress Control") + 1, str(df.loc[idx, "Progress Control"]))

        st.success(f"Data untuk kelompok '{selected_kelompok}' berhasil diperbarui!")

# ======================
# 4. Show Data
# ======================
st.write("### Data saat ini")
st.dataframe(df, use_container_width=True)

