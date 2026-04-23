import streamlit as st


def apply_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');

        :root {
            --text-primary: #e8f1ff;
            --text-secondary: #bdd0ee;
            --card-bg: rgba(11, 24, 46, 0.78);
            --card-border: rgba(119, 151, 201, 0.38);
        }

        html, body, [class*="css"] {
            font-family: 'Outfit', sans-serif;
            color: var(--text-primary);
        }

        .stApp {
            background:
                radial-gradient(circle at 8% 12%, rgba(55, 108, 207, 0.30), transparent 34%),
                radial-gradient(circle at 90% 5%, rgba(22, 158, 164, 0.24), transparent 36%),
                linear-gradient(130deg, #0a1428 0%, #0c1a33 48%, #081224 100%);
        }

        h1, h2, h3, h4, h5, h6,
        .stMarkdown,
        .stMarkdown p,
        .stCaption,
        label {
            color: var(--text-primary) !important;
        }

        .block-container {
            padding-top: 1.4rem;
            max-width: 1500px;
        }

        div[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #121a2d 0%, #0c1321 100%);
            border-right: 1px solid rgba(102, 128, 179, 0.28);
        }

        div[data-testid="stSidebar"] * {
            color: #d6e6ff !important;
        }

        .hero-card {
            border: 1px solid rgba(116, 162, 255, 0.25);
            background: linear-gradient(135deg, rgba(8, 20, 45, 0.88), rgba(7, 38, 58, 0.72));
            border-radius: 16px;
            padding: 14px 18px;
            margin-bottom: 0.9rem;
        }

        .hero-wrap {
            display: flex;
            align-items: center;
            gap: 14px;
        }

        .hero-image {
            width: 52px;
            height: 52px;
            border-radius: 12px;
            border: 1px solid rgba(138, 174, 255, 0.45);
            object-fit: cover;
            background: rgba(255, 255, 255, 0.12);
        }

        .hero-title {
            font-size: 2.1rem;
            font-weight: 800;
            margin: 0;
            color: #d9e7ff;
            letter-spacing: -0.01em;
        }

        .hero-subtitle {
            margin: 0.15rem 0 0 0;
            color: var(--text-secondary);
            font-size: 0.96rem;
        }

        .metric-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 12px;
            padding: 16px 18px;
            margin-bottom: 1rem;
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 22px rgba(0, 0, 0, 0.3);
            border-color: rgba(103, 193, 255, 0.7);
        }

        .metric-label {
            font-size: 0.88rem;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 6px;
        }

        .metric-value {
            font-size: 2rem;
            font-weight: 700;
            color: #eff5ff;
            line-height: 1.1;
        }

        .metric-value span {
            color: #69d3ff;
        }

        .chart-card {
            background: var(--card-bg);
            border: 1px solid var(--card-border);
            border-radius: 14px;
            padding: 14px 16px 10px 16px;
            margin-bottom: 1rem;
        }

        .empty-note {
            color: #c5d4eb;
            font-size: 0.92rem;
            padding: 0.5rem 0.1rem;
        }

        div[data-testid="stDataFrame"] {
            border-radius: 10px;
            overflow: hidden;
            border: 1px solid rgba(95, 120, 163, 0.25);
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
                <img class='hero-image' src='{image_url}' alt='hero-image'/>
                <div>
                    <h1 class='hero-title'>{title}</h1>
                    <p class='hero-subtitle'>{subtitle}</p>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
