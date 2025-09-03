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
sa_info["private_key"] = sa_info["private_key"].replace("\\n", "\n")  # fix newline

creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
client = gspread.authorize(creds)

# ID Google Sheet
SHEET_ID = "1hhr1KjWSAU49wJQhcH_3Js_N8-VQA0WX2fZoGhs3m0w"
worksheet = client.open_by_key(SHEET_ID).sheet1

# Load data dari sheet
data = worksheet.get_all_records()
df = pd.DataFrame(data)
df.columns = df.columns.str.strip()

# Pastikan numeric coords
df["X"] = pd.to_numeric(df["X"], errors="coerce")  # latitude
df["Y"] = pd.to_numeric(df["Y"], errors="coerce")  # longitude

# Tambahkan kolom bila belum ada
for col, default in [("Panjang Aktual", 0.0), ("Uang Terserap", 0.0), ("Progress Control", 0.0)]:
    if col not in df.columns:
        df[col] = default

# Hitung progress berdasarkan Panjang Aktual / Usulan Panjang
df["Progress Control"] = (
    df["Panjang Aktual"].astype(float) / df["Usulan Panjang (m)"].replace(0, 1).astype(float)
) * 100

# ======================
# 2. Fungsi utilitas
# ======================
def get_marker_color(progress: float) -> str:
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
# 3. Peta Folium
# ======================
# Handle jika koordinat kosong
if df["X"].notnull().any() and df["Y"].notnull().any():
    center_lat = df["X"].mean()
    center_lon = df["Y"].mean()
else:
    center_lat, center_lon = -0.5, 117.0  # default center Indonesia

m = folium.Map(location=[center_lat, center_lon], zoom_start=12, tiles="OpenStreetMap")

for _, row in df.iterrows():
    if pd.notnull(row["X"]) and pd.notnull(row["Y"]):
        popup_html = f"""
        <b>Kelompok:</b> {row.get('NAMA KELOMPOK', '-') }<br>
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

# Tambah legenda
legend_html = """
<div style="position: fixed; bottom: 50px; left: 50px; width: 160px;
            background-color: rgba(255,255,255,0.9);
            border: 1px solid grey; border-radius: 5px;
            z-index: 9999; font-size: 13px;
            padding: 8px; color: black;">
    <b style="font-size:14px;">Progress Legend</b><br>
    <span style="background:#FF0000; display:inline-block; width:12px; height:12px; margin-right:6px;"></span>0–24%<br>
    <span style="background:#FF8000; display:inline-block; width:12px; height:12px; margin-right:6px;"></span>25–49%<br>
    <span style="background:#FFD700; display:inline-block; width:12px; height:12px; margin-right:6px;"></span>50–74%<br>
    <span style="background:#7CBE19; display:inline-block; width:12px; height:12px; margin-right:6px;"></span>75–99%<br>
    <span style="background:#145214; display:inline-block; width:12px; height:12px; margin-right:6px;"></span>100%<br>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# Render map
st_data = st_folium(m, width=800, height=600)

# ======================
# 4. Input User
# ======================
st.write("### Update Data")
kelompok_list = df["NAMA KELOMPOK"].dropna().unique().tolist()
selected_kelompok = st.selectbox("Pilih NAMA KELOMPOK", options=kelompok_list)

if selected_kelompok:
    idx = df[df["NAMA KELOMPOK"] == selected_kelompok].index[0]

    # Info (read-only)
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

        # ======================
        # Update hanya 1 baris
        # ======================
        row_number = idx + 2  # +2 karena row 1 = header, index 0 = row 2
        worksheet.update_cell(row_number, df.columns.get_loc("Panjang Aktual")+1, str(panjang_aktual))
        worksheet.update_cell(row_number, df.columns.get_loc("Uang Terserap")+1, str(uang_terserap))
        worksheet.update_cell(row_number, df.columns.get_loc("Progress Control")+1, str(df.loc[idx, "Progress Control"]))

        st.success(f"Data untuk kelompok '{selected_kelompok}' berhasil diperbarui!")

# ======================
# 5. Tampilkan Data
# ======================
st.write("### Data saat ini")
st.dataframe(df, use_container_width=True)
