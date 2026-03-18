from __future__ import annotations

import json
from datetime import datetime

import streamlit as st

from engine import ACMEngine


SAMPLE_TELEMETRY = {
    "objects": [
        {
            "id": "SAT-1",
            "type": "SATELLITE",
            "r_km": [7000.0, 0.0, 0.0],
            "v_km_s": [0.0, 7.5, 0.0],
            "mass_kg": 550.0,
            "fuel_kg": 50.0,
        },
        {
            "id": "SAT-2",
            "type": "SATELLITE",
            "r_km": [7000.0, 0.05, 0.0],
            "v_km_s": [0.0, 7.5, 0.0],
            "mass_kg": 540.0,
            "fuel_kg": 45.0,
        },
        {
            "id": "DEB-1",
            "type": "DEBRIS",
            "r_km": [7000.0, 0.08, 0.0],
            "v_km_s": [0.0, 7.5, 0.0],
            "mass_kg": 1.0,
        },
    ]
}


def _theme() -> None:
    """Apply a custom visual style for the demo UI."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&display=swap');

        :root {
            --bg-0: #f4f6f8;
            --bg-1: #e8f2f2;
            --text: #17232e;
            --card: rgba(255,255,255,0.72);
            --brand: #0a7f6f;
            --accent: #b55123;
            --ok: #0a7f6f;
        }

        .stApp {
            background:
                radial-gradient(circle at 10% 15%, #d9efe9 0%, transparent 35%),
                radial-gradient(circle at 90% 30%, #ffe7d8 0%, transparent 40%),
                linear-gradient(120deg, var(--bg-0) 0%, var(--bg-1) 100%);
            color: var(--text);
            font-family: 'Space Grotesk', sans-serif;
        }

        .title-wrap {
            padding: 1.2rem 1.4rem;
            border: 1px solid rgba(10, 127, 111, 0.2);
            border-radius: 16px;
            background: var(--card);
            backdrop-filter: blur(8px);
            box-shadow: 0 8px 25px rgba(23, 35, 46, 0.08);
            margin-bottom: 0.8rem;
            animation: rise 500ms ease-out;
        }

        .metric-chip {
            padding: 0.35rem 0.7rem;
            border-radius: 999px;
            background: rgba(10,127,111,0.10);
            border: 1px solid rgba(10,127,111,0.28);
            display: inline-block;
            margin-right: 0.45rem;
            margin-bottom: 0.45rem;
            font-size: 0.86rem;
        }

        .stTextArea textarea {
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', monospace;
        }

        @keyframes rise {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )



def _init_state() -> None:
    if "engine" not in st.session_state:
        st.session_state.engine = ACMEngine()
    if "events" not in st.session_state:
        st.session_state.events = []



def _log(event: str) -> None:
    stamp = datetime.utcnow().strftime("%H:%M:%S")
    st.session_state.events.append(f"[{stamp} UTC] {event}")



def _header() -> None:
    engine: ACMEngine = st.session_state.engine
    st.markdown(
        """
        <div class="title-wrap">
            <h1 style="margin:0; letter-spacing:0.2px;">ACM Engine Command Deck</h1>
            <p style="margin:0.45rem 0 0 0; opacity:0.85;">
                Direct demo frontend for vectorized simulation, maneuver scheduling, and collision checks.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    chips = [
        f"Objects: {engine.object_count}",
        f"Sim Time: {engine.current_time_s:.1f}s",
    ]
    st.markdown(
        "".join(f'<span class="metric-chip">{c}</span>' for c in chips),
        unsafe_allow_html=True,
    )



def _controls() -> None:
    engine: ACMEngine = st.session_state.engine

    col_a, col_b, col_c = st.columns([1, 1, 1])
    with col_a:
        if st.button("Reset Engine", use_container_width=True):
            st.session_state.engine = ACMEngine()
            st.session_state.events = []
            _log("Engine reset")
            st.rerun()

    with col_b:
        if st.button("Load Sample Telemetry", use_container_width=True):
            result = engine.ingest_telemetry(SAMPLE_TELEMETRY)
            _log(f"Sample telemetry ingested -> {result}")
            st.success("Sample telemetry loaded")

    with col_c:
        step_seconds = st.number_input("Step Seconds", min_value=1.0, value=20.0, step=10.0)
        if st.button("Step Simulation", use_container_width=True):
            result = engine.step_simulation(step_seconds)
            _log(
                "Step run -> "
                f"ticks={result['ticks']}, maneuvers={result['maneuvers_executed']}, "
                f"collisions={len(result['collisions_detected'])}, conjunctions={len(result['predicted_conjunctions'])}"
            )
            st.success("Simulation advanced")



def _ingest_panel() -> None:
    engine: ACMEngine = st.session_state.engine

    st.subheader("Ingest Telemetry")
    payload_text = st.text_area(
        "Telemetry JSON",
        value=json.dumps(SAMPLE_TELEMETRY, indent=2),
        height=280,
    )

    if st.button("Ingest JSON Payload"):
        try:
            payload = json.loads(payload_text)
            result = engine.ingest_telemetry(payload)
            _log(f"Custom telemetry ingested -> {result}")
            st.success(result)
        except Exception as exc:
            st.error(f"Ingest failed: {exc}")



def _maneuver_panel() -> None:
    engine: ACMEngine = st.session_state.engine

    st.subheader("Schedule Maneuver")
    m_col1, m_col2, m_col3, m_col4 = st.columns([2, 1, 1, 1])

    with m_col1:
        object_id = st.text_input("Object ID", value="SAT-1")
    with m_col2:
        dvx = st.number_input("dVx (km/s)", value=0.0, step=0.001, format="%.6f")
    with m_col3:
        dvy = st.number_input("dVy (km/s)", value=0.001, step=0.001, format="%.6f")
    with m_col4:
        dvz = st.number_input("dVz (km/s)", value=0.0, step=0.001, format="%.6f")

    if st.button("Schedule Burn"):
        try:
            result = engine.schedule_maneuver(
                {
                    "object_id": object_id,
                    "delta_v_km_s": [dvx, dvy, dvz],
                }
            )
            _log(f"Maneuver scheduled -> {result}")
            st.success(result)
        except Exception as exc:
            st.error(f"Schedule failed: {exc}")



def _snapshot_panel() -> None:
    engine: ACMEngine = st.session_state.engine
    snapshot = engine.get_snapshot()

    st.subheader("Snapshot")
    s_col1, s_col2, s_col3 = st.columns(3)
    s_col1.metric("Timestamp (s)", f"{snapshot['timestamp_s']:.1f}")
    s_col2.metric("Satellites", len(snapshot["satellites"]))
    s_col3.metric("Debris", snapshot["debris"]["count"])

    st.markdown("Satellite Rows")
    st.dataframe(
        snapshot["satellites"],
        use_container_width=True,
        hide_index=True,
        column_config={
            0: "id",
            1: "lat_deg",
            2: "lon_deg",
            3: "fuel_kg",
            4: "status",
        },
    )

    st.markdown("Debris Payload Metadata")
    st.json(
        {
            "count": snapshot["debris"]["count"],
            "encoding": snapshot["debris"]["encoding"],
            "dtype": snapshot["debris"]["dtype"],
            "shape": snapshot["debris"]["shape"],
            "data_preview": str(snapshot["debris"]["data"])[:64],
        }
    )



def _events_panel() -> None:
    st.subheader("Engine Event Log")
    if not st.session_state.events:
        st.caption("No events yet. Run an action from the control panels.")
        return
    st.code("\n".join(st.session_state.events[-30:]), language="text")



def main() -> None:
    st.set_page_config(
        page_title="ACM Engine Demo",
        page_icon="🛰️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )
    _theme()
    _init_state()
    _header()

    left, right = st.columns([1.25, 1])
    with left:
        _controls()
        _ingest_panel()
        _maneuver_panel()

    with right:
        _snapshot_panel()
        _events_panel()


if __name__ == "__main__":
    main()
