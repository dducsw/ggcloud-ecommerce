import streamlit as st

def apply_theme() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        @import url('https://fonts.googleapis.com/icon?family=Material+Icons');

        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
            color: #0f172a;
        }

        .stApp {
            background-color: #f8fafc;
        }

        .block-container {
            padding-top: 2rem;
            max-width: 1440px;
        }

        /* Sidebar Styling */
        div[data-testid="stSidebar"] {
            background-color: #ffffff;
            border-right: 1px solid #e2e8f0;
        }

        /* Metric Cards */
        .metric-card {
            border: 1px solid #e2e8f0;
            background: #ffffff;
            border-radius: 12px;
            padding: 20px;
            margin-bottom: 1rem;
            box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1);
            transition: all 0.2s ease;
            min-height: 120px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
        }
        
        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1);
            border-color: #cbd5e1;
        }

        .metric-label {
            font-size: 0.75rem;
            font-weight: 700;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }

        .metric-value {
            font-size: 1.85rem;
            font-weight: 700;
            color: #0f172a;
            line-height: 1.2;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }

        .metric-subtitle {
            color: #94a3b8;
            font-size: 0.75rem;
            margin-top: 4px;
            font-weight: 400;
        }

        /* Section Headers */
        .section-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-top: 2.5rem;
            margin-bottom: 1.5rem;
        }
        
        .section-header i {
            font-size: 1.5rem;
            color: #3b82f6;
        }

        /* Hero Section */
        .page-header {
            margin-bottom: 2.5rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px solid #e2e8f0;
        }

        .page-title {
            font-size: 2.25rem;
            font-weight: 800;
            margin: 0;
            color: #0f172a;
            letter-spacing: -0.025em;
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .page-description {
            margin: 8px 0 0 0;
            color: #64748b;
            font-size: 1.1rem;
            font-weight: 400;
        }

        h1, h2, h3, h4 {
            color: #1e293b !important;
            font-weight: 700 !important;
        }

        /* Status Badge */
        .status-badge {
            display: inline-flex;
            align-items: center;
            padding: 4px 12px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
        }
        
        .status-badge-active {
            background-color: #ecfdf5;
            color: #059669;
        }
        
        .status-badge-idle {
            background-color: #fef2f2;
            color: #dc2626;
        }

        /* Material Icon Helper */
        .material-icon {
            font-family: 'Material Icons';
            font-weight: normal;
            font-style: normal;
            font-size: 24px;
            line-height: 1;
            letter-spacing: normal;
            text-transform: none;
            display: inline-block;
            white-space: nowrap;
            word-wrap: normal;
            direction: ltr;
            -webkit-font-smoothing: antialiased;
            text-rendering: optimizeLegibility;
            -moz-osx-font-smoothing: grayscale;
            font-feature-settings: 'liga';
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

def render_page_header(title: str, description: str = None, icon: str = None) -> None:
    icon_html = f'<span class="material-icon" style="font-size: 2.5rem; color: #3b82f6;">{icon}</span>' if icon else ""
    st.markdown(
        f"""
        <div class="page-header">
            <h1 class="page-title">{icon_html} {title}</h1>
            {f'<p class="page-description">{description}</p>' if description else ''}
        </div>
        """,
        unsafe_allow_html=True,
    )

def render_section_header(title: str, icon: str = None) -> None:
    icon_html = f'<span class="material-icon" style="color: #3b82f6; margin-right: 8px;">{icon}</span>' if icon else ""
    st.markdown(f'<div class="section-header"><h3>{icon_html}{title}</h3></div>', unsafe_allow_html=True)
