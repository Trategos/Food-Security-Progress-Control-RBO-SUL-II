import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium

# Load CSV
file_path = "cleaned_data.csv"
df = pd.read_csv(file_path, delimiter=";")
df.columns = df.columns.str.strip()

# Ensure numeric coords
df["X"] = pd.to_numeric(df["X"], errors="coerce")  # latitude
df["Y"] = pd.to_numeric(df["Y"], errors="coerce")  # longitude

# Add new columns if not exist
if "Panjang Aktual" not in df.columns:
    df["Panjang Aktual"] = 0
if "Uang Terserap" not in df.columns:
    df["Uang Terserap"] = 0
if "Progress Control" not in df.columns:
    df["Progress Control"] = 0.0

# Calculate progress
df["Progress Control"] = (df["Uang Terserap"] / df["KEBUTUHAN ANGGARAN"].replace(0, 1)) * 100

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
        return "#145214FF"  # dark green

# Create map
m = folium.Map(location=[df["X"].mean(), df["Y"].mean()], zoom_start=12, tiles="OpenStreetMap")

# Add CircleMarkers
for i, row in df.iterrows():
    if pd.notnull(row["X"]) and pd.notnull(row["Y"]):
        popup_html = f"""
        <b>Kelompok:</b> {row['NAMA KELOMPOK'] if 'NAMA KELOMPOK' in df.columns else i}<br>
        Usulan Panjang (m): {row.get('Usulan Panjang (m)', 0)}<br>
        Kebutuhan Anggaran: {row.get('KEBUTUHAN ANGGARAN', 0)}<br>
        Panjang Aktual: {row.get('Panjang Aktual', 0)}<br>
        Uang Terserap: {row.get('Uang Terserap', 0)}<br>
        Progress Control: {row.get('Progress Control', 0):.2f}%
        """
        folium.CircleMarker(
            location=[row["X"], row["Y"]],
            radius=7,
            color=get_marker_color(row["Progress Control"]),
            fill=True,
            fill_color=get_marker_color(row["Progress Control"]),
            popup=folium.Popup(popup_html, max_width=300),
        ).add_to(m)

# --- Add Legend with new colors ---
legend_html = """
<div style="
    position: fixed; 
    bottom: 50px; left: 50px; width: 160px; 
    background-color: rgba(255,255,255,0.9);
    border: 1px solid grey; 
    z-index: 9999; 
    font-size: 13px;
    padding: 8px;
    color: black;
    border-radius: 5px;
    ">
    <b style="font-size:14px;">Progress Legend</b><br>
    <div style="margin-top:4px; line-height: 18px;">
        <span style="background:#FF0000; display:inline-block; width:12px; height:12px; margin-right:6px;"></span>0–24%<br>
        <span style="background:#FF8000; display:inline-block; width:12px; height:12px; margin-right:6px;"></span>25–49%<br>
        <span style="background:#FFD700; display:inline-block; width:12px; height:12px; margin-right:6px;"></span>50–74%<br>
        <span style="background:#7CBE19; display:inline-block; width:12px; height:12px; margin-right:6px;"></span>75–99%<br>
        <span style="background:#145214FF; display:inline-block; width:12px; height:12px; margin-right:6px;"></span>100%<br>
    </div>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# Render map
st_data = st_folium(m, width=800, height=600)

# --- User input section ---
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
    panjang_aktual = st.number_input("Panjang Aktual (m)", value=int(df.loc[idx, "Panjang Aktual"]))
    uang_terserap = st.number_input("Uang Terserap", value=int(df.loc[idx, "Uang Terserap"]))

    if st.button("Simpan Perubahan"):
        df.loc[idx, "Panjang Aktual"] = panjang_aktual
        df.loc[idx, "Uang Terserap"] = uang_terserap
        df.loc[idx, "Progress Control"] = (
            (uang_terserap / df.loc[idx, "KEBUTUHAN ANGGARAN"]) * 100
            if df.loc[idx, "KEBUTUHAN ANGGARAN"] > 0 else 0
        )
        df.to_csv(file_path, sep=";", index=False)
        st.success(f"Data untuk kelompok '{selected_kelompok}' berhasil diperbarui!")

# Show the entire updated dataframe
st.write("### Data saat ini")
st.dataframe(df, use_container_width=True)
