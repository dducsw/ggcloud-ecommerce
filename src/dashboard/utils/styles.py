import streamlit as st

def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.2rem;
            padding-bottom: 1.2rem;
            max-width: 1400px;
        }
        .metric-card {
            border: 1px solid #d9dee7;
            background: #ffffff;
            border-radius: 4px;
            padding: 16px 18px;
            min-height: 108px;
        }
        .metric-label {
            font-size: 0.85rem;
            color: #5d6b82;
            margin-bottom: 8px;
        }
        .metric-value {
            font-size: 1.9rem;
            font-weight: 600;
            color: #1e2a3a;
            line-height: 1.1;
        }
        .metric-subtle {
            font-size: 0.82rem;
            color: #6e7b8f;
            margin-top: 8px;
        }
        div[data-testid="stMetric"] {
            border: 1px solid #d9dee7;
            background: #ffffff;
            padding: 14px 16px;
            border-radius: 4px;
        }
        h1, h2, h3 {
            color: #172231;
            letter-spacing: -0.02em;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
