import streamlit as st

def apply_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            color: #172231;
        }

        .stApp {
            background-color: #f8f9fb;
        }

        .block-container {
            padding-top: 1.5rem;
            max-width: 1400px;
        }

        /* Sidebar Styling */
        div[data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: 1px solid #e1e4e8;
        }

        /* Metric Cards - Reverting to old style */
        .metric-card {
            border: 1px solid #d9dee7;
            background: #ffffff;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }

        .metric-label {
            font-size: 0.9rem;
            font-weight: 500;
            color: #5d6b82;
            text-transform: uppercase;
            letter-spacing: 0.02em;
            margin-bottom: 8px;
        }

        .metric-value {
            font-size: 2.2rem;
            font-weight: 700;
            color: #1e2a3a;
            line-height: 1.1;
        }

        .metric-value span {
            color: #315f8c;
            margin-right: 2px;
        }

        /* Chart Cards */
        .chart-card {
            background: #ffffff;
            border: 1px solid #d9dee7;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }

        /* Hero Section Styling - Adapted for Light Mode */
        .hero-card {
            background: #ffffff;
            border: 1px solid #d9dee7;
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 2rem;
            border-left: 5px solid #315f8c;
            box-shadow: 0 2px 4px rgba(0,0,0,0.04);
        }

        .hero-wrap {
            display: flex;
            align-items: center;
            gap: 20px;
        }

        .hero-image {
            width: 64px;
            height: 64px;
            border-radius: 10px;
            object-fit: cover;
            border: 1px solid #e1e4e8;
        }

        .hero-title {
            font-size: 1.8rem;
            font-weight: 700;
            margin: 0;
            color: #172231;
        }

        .hero-subtitle {
            margin: 4px 0 0 0;
            color: #5d6b82;
            font-size: 1rem;
        }

        h1, h2, h3, h4 {
            color: #172231 !important;
            font-weight: 700 !important;
        }

        .stCaption {
            color: #6e7b8f !important;
        }

        .empty-note {
            color: #8c99af;
            font-style: italic;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_hero(title: str, subtitle: str, image_url: str) -> None:
    st.markdown(
        f"""
        <div class='hero-card'>
            <div class='hero-wrap'>
                <img class='hero-image' src='{image_url}' />
                <div>
                    <h1 class='hero-title'>{title}</h1>
                    <p class='hero-subtitle'>{subtitle}</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
