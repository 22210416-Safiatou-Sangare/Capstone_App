"""
streamlit_app.py -- post-flight mission dashboard (finished version).

Run with:
    streamlit run app/streamlit_app.py

Features:
  * Flight selector: every CSV in data/ appears in a dropdown; uploads work too
  * MEASURED views: mission map, telemetry graphs, stats
  * SIMULATED views: LIDAR terrain (synthetic OR real cached SRTM), thermal
  * One-click self-contained HTML mission report (for the submission)
"""

import io
from pathlib import Path

import numpy as np
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

import dem_sources
import ingest
import report as report_mod
import simulate

MEASURED = "🟢 **MEASURED** — real data recorded by the drone"
SIMULATED = "🟠 **SIMULATED** — synthetic layer for the feasibility study"
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

st.set_page_config(page_title="Drone Survey Dashboard", page_icon="🛰️",
                   layout="wide")

# ----------------------------------------------------------- flight choice
st.sidebar.title("🛰️ Survey Dashboard")

flight_files = sorted(DATA_DIR.glob("*.csv"))
names = [f.name for f in flight_files]
choice = st.sidebar.selectbox("Flight", names + ["⬆️ Upload a CSV…"],
                              index=0 if names else 0)


@st.cache_data
def load_path(path_str: str):
    return ingest.load_flight(path_str)


@st.cache_data
def load_bytes(b: bytes):
    return ingest.load_flight(io.BytesIO(b))


try:
    if choice == "⬆️ Upload a CSV…":
        up = st.sidebar.file_uploader("Flight CSV (project schema)", type="csv")
        if up is None:
            st.info("Upload a flight CSV in the sidebar, or add files to data/.")
            st.stop()
        df, mission_name = load_bytes(up.getvalue()), up.name
    else:
        df, mission_name = load_path(str(DATA_DIR / choice)), choice
except ingest.BadFlightFile as err:
    st.error(f"Could not load flight file: {err}")
    st.stop()

st.sidebar.caption(f"{len(df)} rows · "
                   f"{(df['time_ms'].iloc[-1]) / 1000:.0f} s mission")

# ----------------------------------------------------- simulation controls
st.sidebar.subheader("Simulated layers")
show_anomaly = st.sidebar.toggle("Inject synthetic buried structure", True)
use_online = st.sidebar.toggle(
    "Fetch REAL elevation data (needs internet once)", False,
    help="Downloads ~30-90 m SRTM elevations for this flight's area from the "
         "open-elevation API and caches them in data/. After the first fetch "
         "it works fully offline. If the fetch fails, the app falls back to "
         "the synthetic terrain automatically.")

bbox = simulate.flight_bbox(df)
lat_axis = np.linspace(bbox[0], bbox[1], simulate.GRID)
lon_axis = np.linspace(bbox[2], bbox[3], simulate.GRID)


@st.cache_data
def get_layers(bbox, online: bool, anomaly: bool):
    dem, label = dem_sources.get_dem(bbox, allow_online=online,
                                     buried_structure=anomaly)
    thermal, centers = simulate.generate_thermal(bbox)
    return dem, label, thermal


dem, dem_label, thermal = get_layers(bbox, use_online, show_anomaly)

# time slider drives the position marker + chart cursor
t0, t1 = int(df["time_ms"].iloc[0]) // 1000, int(df["time_ms"].iloc[-1]) // 1000
t_sel = st.sidebar.slider("Mission time (s)", t0, max(t1, t0 + 1), t0)
row = df.iloc[(df["time_ms"] - t_sel * 1000).abs().argmin()]

# ------------------------------------------------------------ header stats
stats = ingest.mission_stats(df)
st.title("Autonomous GPS Survey — Mission Dashboard")
c = st.columns(6)
c[0].metric("Duration", f"{stats['duration_s']:.0f} s")
c[1].metric("Distance", f"{stats['distance_m']:.0f} m")
c[2].metric("Max altitude", f"{stats['max_alt_m']:.1f} m")
c[3].metric("Max speed", f"{stats['max_speed_ms']:.1f} m/s")
c[4].metric("Min battery", f"{stats['min_vbat_v']:.2f} V")
c[5].metric("Avg satellites", f"{stats['avg_sats']:.0f}")

tab_map, tab_tel, tab_lidar, tab_thermal, tab_about = st.tabs(
    ["🗺️ Mission map", "📈 Telemetry", "⛰️ LIDAR terrain (SIM)",
     "🌡️ Thermal (SIM)", "ℹ️ About the data"])

# ------------------------------------------------------------------ 1) map
with tab_map:
    st.markdown(MEASURED)
    path_data = [{"path": df[["lon", "lat"]].values.tolist()}]
    layers = [
        pdk.Layer("PathLayer", data=path_data, get_path="path",
                  get_color=[0, 150, 255], width_min_pixels=3),
        pdk.Layer("ScatterplotLayer",
                  data=[{"pos": [float(row["lon"]), float(row["lat"])]}],
                  get_position="pos", get_radius=4,
                  get_fill_color=[255, 80, 80], radius_min_pixels=6),
    ]
    view = pdk.ViewState(latitude=float(df["lat"].mean()),
                         longitude=float(df["lon"].mean()), zoom=16)
    st.pydeck_chart(pdk.Deck(layers=layers, initial_view_state=view,
                             map_style=None))
    st.caption("Blue line: full autonomous flight path (lawnmower survey "
               "pattern). Red dot: drone position at the selected time.")

# ------------------------------------------------------------ 2) telemetry
with tab_tel:
    st.markdown(MEASURED)
    t_s = df["time_ms"] / 1000
    for col, label, unit in [("alt_m", "Altitude", "m"),
                             ("ground_speed_ms", "Ground speed", "m/s"),
                             ("vbat_v", "Battery voltage", "V"),
                             ("sat_count", "GPS satellites", "")]:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=t_s, y=df[col], mode="lines", name=label))
        fig.add_vline(x=t_sel, line_dash="dash", line_color="red")
        fig.update_layout(height=220, margin=dict(l=10, r=10, t=30, b=10),
                          title=f"{label} ({unit})" if unit else label)
        st.plotly_chart(fig, use_container_width=True)

# -------------------------------------------------------- 3) LIDAR terrain
with tab_lidar:
    src_badge = ("🟢 **REAL elevation data** (SRTM, "
                 f"{dem_label})" if dem_label.startswith("real")
                 else SIMULATED)
    st.markdown(src_badge)
    st.write("Terrain relief this mission *would* have captured with an "
             "aerial LIDAR payload. Aerial LIDAR maps fine **surface** "
             "relief; buried structures appear as subtle bumps and "
             "depressions — not as underground X-ray images.")
    shade = simulate.hillshade(dem)

    fig = go.Figure()
    fig.add_trace(go.Heatmap(z=shade, x=lon_axis, y=lat_axis,
                             colorscale="Greys", reversescale=True,
                             showscale=False))
    fig.add_trace(go.Scatter(x=df["lon"], y=df["lat"], mode="lines",
                             line=dict(color="deepskyblue", width=2),
                             name="real flight path (MEASURED)"))
    fig.update_layout(height=560, yaxis_scaleanchor="x",
                      margin=dict(l=10, r=10, t=30, b=10),
                      title=f"Hillshade relief ({dem_label} DEM) + real flight path")
    st.plotly_chart(fig, use_container_width=True)
    if show_anomaly:
        st.info("A faint rectangular platform (~0.6 m relief) is injected — "
                "the signature a buried structure would leave. Labeled "
                "SYNTHETIC ANOMALY. Toggle it in the sidebar.")

    with st.expander("3D terrain view"):
        fig3d = go.Figure()
        fig3d.add_trace(go.Surface(z=dem, x=lon_axis, y=lat_axis,
                                   colorscale="Earth", showscale=False))
        fig3d.add_trace(go.Scatter3d(
            x=df["lon"], y=df["lat"], z=df["alt_m"] + float(dem.mean()),
            mode="lines", line=dict(color="red", width=4),
            name="flight path"))
        fig3d.update_layout(height=600, margin=dict(l=0, r=0, t=0, b=0),
                            scene=dict(aspectmode="manual",
                                       aspectratio=dict(x=1, y=1, z=0.35)))
        st.plotly_chart(fig3d, use_container_width=True)

# ---------------------------------------------------- 4) simulated thermal
with tab_thermal:
    st.markdown(SIMULATED)
    st.write("Ground temperature field a thermal payload (MLX90640-class) "
             "*would* have recorded along this mission.")
    fig = go.Figure()
    fig.add_trace(go.Heatmap(z=thermal, x=lon_axis, y=lat_axis,
                             colorscale="Inferno",
                             colorbar=dict(title="°C")))
    fig.add_trace(go.Scatter(x=df["lon"], y=df["lat"], mode="lines",
                             line=dict(color="white", width=1.5),
                             name="real flight path (MEASURED)"))
    fig.update_layout(height=520, yaxis_scaleanchor="x",
                      margin=dict(l=10, r=10, t=30, b=10),
                      title="Synthetic surface temperature + real flight path")
    st.plotly_chart(fig, use_container_width=True)

    series = simulate.sample_along_path(thermal, bbox, df)
    t_s = df["time_ms"] / 1000
    fig2 = go.Figure()
    for key, color in [("max", "orangered"), ("avg", "orange"),
                       ("min", "gold")]:
        fig2.add_trace(go.Scatter(x=t_s, y=series[key], mode="lines",
                                  name=f"{key} °C", line=dict(color=color)))
    fig2.add_vline(x=t_sel, line_dash="dash", line_color="red")
    fig2.update_layout(height=280, margin=dict(l=10, r=10, t=30, b=10),
                       title="Simulated sensor readings along the mission")
    st.plotly_chart(fig2, use_container_width=True)

# ------------------------------------------------------------------ 5) about
with tab_about:
    st.subheader("What is real and what is simulated")
    st.markdown(f"""
| Layer | Status | Source |
|---|---|---|
| Flight path, altitude, speed, battery, satellites | 🟢 MEASURED | INAV blackbox log recorded during the autonomous mission |
| Terrain elevation | {"🟢 REAL (SRTM via open-elevation, " + dem_label + ")" if dem_label.startswith("real") else "🟠 SIMULATED (procedural)"} | Over the real flight's bounding box; one sidebar toggle switches source |
| Buried-structure anomaly | 🟠 SYNTHETIC | Injected relief feature, always labeled |
| Thermal layer | 🟠 SIMULATED | Procedural temperature field sampled along the real flight path |

**Why simulate?** Survey-grade LIDAR and radiometric thermal payloads cost far
more than a student budget allows. This project demonstrates the complete
system — autonomous flight, blackbox data logging, processing pipeline, and
analysis software — with premium sensors replaced by clearly-labeled synthetic
layers anchored to real missions. Swapping a simulated layer for a real
sensor requires no change to the rest of the system.
""")

# ------------------------------------------------------------ report export
st.sidebar.divider()
if st.sidebar.button("📄 Build mission report (HTML)"):
    html = report_mod.build_report(df, dem, dem_label, thermal,
                                   mission_name=mission_name)
    st.sidebar.download_button("⬇️ Download report", html,
                               file_name=f"report_{mission_name}.html",
                               mime="text/html")
