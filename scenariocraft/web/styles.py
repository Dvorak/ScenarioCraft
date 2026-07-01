from __future__ import annotations

import streamlit as st

from scenariocraft.web.state import WORKSPACE_DESKTOP_HEIGHT, WORKSPACE_MEDIA_ASPECT_RATIO


def inject_css() -> None:
    css = """
        <style>
        :root {
            --workspace-desktop-height: __WORKSPACE_DESKTOP_HEIGHT__;
            --workspace-media-aspect-ratio: __WORKSPACE_MEDIA_ASPECT_RATIO__;
            --sc-bg: #ffffff;
            --sc-bg-subtle: #fafafa;
            --sc-surface: #ffffff;
            --sc-surface-subtle: #f2f2f2;
            --sc-border: #eaeaea;
            --sc-border-strong: #c9c9c9;
            --sc-text: #171717;
            --sc-text-secondary: #4d4d4d;
            --sc-text-muted: #7d7d7d;
            --sc-blue: #006bff;
            --sc-blue-bg: #f0f7ff;
            --sc-red: #ea001d;
            --sc-red-bg: #ffeeef;
            --sc-amber: #ff9300;
            --sc-amber-bg: #fff6de;
            --sc-green: #28a948;
            --sc-green-bg: #ecfdec;
            --sc-purple: #a000f8;
            --sc-white: #ffffff;
            --sc-radius-sm: 6px;
            --sc-radius-md: 12px;
            --sc-space-1: 0.25rem;
            --sc-space-2: 0.5rem;
            --sc-space-3: 0.75rem;
            --sc-space-4: 1rem;
            --sc-shadow-raised: 0 2px 2px rgba(0, 0, 0, 0.04);
            --sc-focus-ring: 0 0 0 2px var(--sc-bg), 0 0 0 4px var(--sc-blue);
            --sc-font-sans: "Geist Sans", Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            --sc-font-mono: "Geist Mono", ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
            color-scheme: light;
        }
        header[data-testid="stHeader"] { display: none; }
        #MainMenu, [data-testid="stDeployButton"] { display: none; }
        .stApp {
            background: var(--sc-bg);
            color: var(--sc-text);
            font-family: var(--sc-font-sans);
        }
        .block-container { max-width: 1680px; padding-top: 0.8rem; padding-bottom: 2rem; }
        h2 { margin-bottom: 0.2rem; letter-spacing: 0; }
        h3 {
            color: var(--sc-text);
            font-size: 1rem !important;
            font-weight: 600 !important;
            line-height: 1.5 !important;
            margin: 0 0 0.65rem 0 !important;
            letter-spacing: 0;
        }
        .st-key-workspace_left_normal,
        .st-key-workspace_left_repair,
        .st-key-workspace_right {
            height: var(--workspace-desktop-height);
            flex: 0 0 var(--workspace-desktop-height) !important;
            min-height: 0;
        }
        .st-key-workspace_left_normal,
        .st-key-workspace_left_repair {
            display: flex;
            flex-direction: column;
            gap: var(--sc-space-3);
            overflow-y: auto;
            overflow-x: hidden;
            scrollbar-gutter: stable;
            padding-right: 0.18rem;
        }
        .st-key-workspace_left_normal > [data-testid="stLayoutWrapper"]:has(.st-key-workspace_brief) {
            flex: 1 1 auto;
            min-height: 12rem;
        }
        .st-key-workspace_left_normal .st-key-workspace_brief { height: 100%; }
        .st-key-workspace_left_normal .st-key-workspace_brief > div { height: 100%; }
        .st-key-workspace_left_repair > [data-testid="stLayoutWrapper"]:has(.st-key-workspace_repair_panel) {
            flex: 0 0 auto;
            min-height: clamp(20rem, 42vh, 28rem);
        }
        .st-key-workspace_left_repair > [data-testid="stLayoutWrapper"]:has(.st-key-workspace_brief) {
            flex: 0 0 auto;
            min-height: 16rem;
        }
        .st-key-workspace_right {
            display: grid;
            grid-template-columns: minmax(0, 1fr);
            grid-template-rows: repeat(2, minmax(0, 1fr));
            gap: var(--sc-space-3);
        }
        .st-key-workspace_right > [data-testid="stLayoutWrapper"] {
            width: 100% !important;
            height: 100% !important;
            min-width: 0;
            min-height: 0;
            align-self: stretch;
        }
        .st-key-workspace_preview_panel,
        .st-key-workspace_playback_panel {
            height: 100%;
            min-height: 0;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            gap: var(--sc-space-2);
        }
        .st-key-workspace_preview_panel > [data-testid="stLayoutWrapper"]:has(.st-key-workspace_preview_stage),
        .st-key-workspace_playback_panel > [data-testid="stLayoutWrapper"]:has(.st-key-workspace_playback_stage) {
            flex: 1 1 0 !important;
            min-height: 0;
            overflow: hidden;
        }
        .st-key-workspace_preview_stage,
        .st-key-workspace_playback_stage {
            height: 100%;
            flex: 1 1 auto;
            min-height: 0;
            display: flex;
            align-items: center;
        }
        .st-key-workspace_preview_stage { overflow: hidden; }
        .st-key-workspace_playback_stage { overflow: auto; }
        .st-key-workspace_preview_stage > div,
        .st-key-workspace_playback_stage > div {
            width: 100%;
            min-height: 0;
        }
        .st-key-workspace_preview_stage [data-testid="stImage"],
        .st-key-workspace_playback_stage [data-testid="stImage"] {
            height: 100% !important;
            max-height: 100% !important;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .st-key-workspace_preview_stage [data-testid="stFullScreenFrame"] > div,
        .st-key-workspace_playback_stage [data-testid="stFullScreenFrame"] > div,
        .st-key-workspace_preview_stage [data-testid="stElementContainer"]:has([data-testid="stImage"]),
        .st-key-workspace_playback_stage [data-testid="stElementContainer"]:has([data-testid="stImage"]),
        .st-key-workspace_preview_stage [data-testid="stFullScreenFrame"],
        .st-key-workspace_playback_stage [data-testid="stFullScreenFrame"],
        .st-key-workspace_preview_stage [data-testid="stImageContainer"],
        .st-key-workspace_playback_stage [data-testid="stImageContainer"] {
            height: 100% !important;
            max-height: 100% !important;
            min-height: 0;
        }
        .st-key-workspace_preview_stage [data-testid="stImage"] img,
        .st-key-workspace_playback_stage [data-testid="stImage"] img {
            width: 100% !important;
            height: 100% !important;
            max-width: 100% !important;
            max-height: 100% !important;
            object-fit: contain;
        }
        .st-key-workspace_playback_stage [data-testid="stVideo"] video {
            width: 100%;
            height: 100%;
            object-fit: contain;
        }
        .st-key-workspace_toolbar [data-testid="stHorizontalBlock"] {
            align-items: end;
            flex-wrap: wrap;
            gap: var(--sc-space-2);
        }
        .st-key-workspace_toolbar [data-testid="column"]:first-child {
            flex: 1 1 10rem !important;
            min-width: 10rem;
        }
        .st-key-workspace_toolbar [data-testid="column"]:not(:first-child) {
            flex: 0 0 2.75rem !important;
            width: 2.75rem !important;
            min-width: 2.75rem;
        }
        .st-key-workspace_generate button,
        .st-key-workspace_repair button {
            width: 2.75rem;
            min-width: 2.75rem;
            height: 2.75rem;
            min-height: 2.75rem;
            padding: 0;
            border-radius: var(--sc-radius-sm);
        }
        .st-key-workspace_generate button p,
        .st-key-workspace_repair button p { font-size: 0; }
        .st-key-workspace_generate button span,
        .st-key-workspace_repair button span { font-size: 1.2rem; }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--sc-surface);
            border-color: var(--sc-border);
            border-radius: var(--sc-radius-sm);
            box-shadow: var(--sc-shadow-raised);
        }
        [data-testid="stTextArea"] textarea,
        [data-testid="stSelectbox"] [data-baseweb="select"] > div {
            background: var(--sc-bg-subtle);
            border-color: var(--sc-border) !important;
            border-radius: var(--sc-radius-sm);
            color: var(--sc-text);
            font-family: var(--sc-font-sans);
            font-size: 0.875rem;
        }
        [data-testid="stTextArea"] textarea {
            line-height: 1.45;
            padding: var(--sc-space-3) var(--sc-space-4);
        }
        [data-testid="stTextArea"] textarea:focus,
        [data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within {
            border-color: var(--sc-blue) !important;
            box-shadow: var(--sc-focus-ring);
        }
        .stButton button {
            border-radius: var(--sc-radius-sm);
            font-family: var(--sc-font-sans);
            font-weight: 500;
            min-height: 2.5rem;
        }
        .stButton button[kind="primary"],
        .st-key-workspace_generate button {
            background: var(--sc-text) !important;
            border-color: var(--sc-text) !important;
            color: var(--sc-bg) !important;
        }
        [data-testid="stMetric"] { padding: 0; }
        [data-testid="stMetricLabel"] {
            color: var(--sc-text-muted);
            font-size: 0.72rem;
            line-height: 1rem;
        }
        [data-testid="stMetricValue"] {
            color: var(--sc-text);
            font-size: 1.08rem;
            line-height: 1.35rem;
            font-weight: 500;
        }
        [data-testid="stAlert"] {
            border-radius: var(--sc-radius-sm);
            border-color: var(--sc-border);
            box-shadow: none;
        }
        [data-testid="stImage"] img { object-fit: contain; }
        .st-key-workspace_status > div { padding-top: 0.1rem; padding-bottom: 0.1rem; }
        .workspace-status-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            column-gap: var(--sc-space-4);
            row-gap: var(--sc-space-2);
            align-items: start;
        }
        .status-item {
            display: flex;
            flex-direction: column;
            gap: var(--sc-space-1);
            min-width: 0;
            border-radius: var(--sc-radius-sm);
            cursor: help;
            outline: 2px solid transparent;
            outline-offset: 3px;
        }
        .status-item:focus-visible { box-shadow: var(--sc-focus-ring); }
        .status-label { color: var(--sc-text-muted); font-size: 0.72rem; line-height: 1.15; white-space: nowrap; }
        @media (prefers-color-scheme: dark) {
            .status-label { color: var(--sc-text-muted); }
        }
        .status-item strong {
            display: flex;
            align-items: center;
            gap: var(--sc-space-2);
            font-size: 0.9rem;
            line-height: 1.15;
            font-weight: 650;
            white-space: nowrap;
        }
        .status-item strong i {
            display: block;
            flex: 0 0 auto;
            width: 0.46rem;
            height: 0.46rem;
            border-radius: 50%;
            background: var(--sc-border-strong);
        }
        .status-passed strong i { background: var(--sc-green); }
        .status-failed strong i { background: var(--sc-red); }
        .status-waiting strong i { background: var(--sc-amber); }
        .repair-failure-list { display: grid; gap: var(--sc-space-2); }
        .repair-failure {
            display: grid;
            gap: var(--sc-space-1);
            padding: var(--sc-space-3) var(--sc-space-4);
            border: 1px solid color-mix(in srgb, var(--sc-red) 28%, transparent);
            border-radius: var(--sc-radius-sm);
            background: var(--sc-red-bg);
            color: var(--sc-red);
            font-size: 0.82rem;
            line-height: 1.35;
        }
        .repair-failure strong { font-size: 0.78rem; overflow-wrap: anywhere; }
        .status-ok, .status-error, .status-muted {
            border-radius: var(--sc-radius-sm);
            padding: var(--sc-space-2) var(--sc-space-3);
            margin: 0.4rem 0 0.8rem 0;
            font-size: 0.92rem;
        }
        .status-ok {
            background: var(--sc-green-bg);
            color: var(--sc-green);
            border: 1px solid color-mix(in srgb, var(--sc-green) 28%, transparent);
        }
        .status-error {
            background: var(--sc-red-bg);
            color: var(--sc-red);
            border: 1px solid color-mix(in srgb, var(--sc-red) 28%, transparent);
        }
        .status-muted {
            background: var(--sc-bg-subtle);
            color: var(--sc-text-secondary);
            border: 1px solid var(--sc-border);
        }
        .preview-shell {
            border: 1px solid var(--sc-border);
            border-radius: var(--sc-radius-sm);
            padding: var(--sc-space-2);
            background: var(--sc-surface);
        }
        .legend {
            display: flex;
            gap: var(--sc-space-3);
            flex-wrap: wrap;
            font-size: 0.78rem;
            color: var(--sc-text-secondary);
            padding: 0 var(--sc-space-1) var(--sc-space-1) var(--sc-space-1);
        }
        .legend b {
            display: inline-block;
            width: 0.72rem;
            height: 0.72rem;
            border-radius: 2px;
            margin-right: 0.32rem;
            vertical-align: -0.08rem;
        }
        .legend .ego { background: var(--sc-text); }
        .legend .van { background: var(--sc-blue); }
        .legend .ped { background: var(--sc-red); }
        .legend .trigger { background: var(--sc-purple); }
        .vehicle-label { fill: var(--sc-white); font-size: 13px; font-weight: 700; }
        .label { fill: var(--sc-text); font-size: 12px; font-weight: 650; }
        .lane-label { fill: var(--sc-bg-subtle); font-size: 13px; font-weight: 650; opacity: 0.92; }
        .advanced-page {
            color: var(--sc-text);
        }
        .advanced-page [data-testid="stExpander"] {
            border-color: var(--sc-border);
            border-radius: var(--sc-radius-sm);
            box-shadow: var(--sc-shadow-raised);
        }
        .advanced-page [data-testid="stExpander"] summary {
            font-family: var(--sc-font-sans);
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--sc-text);
        }
        .advanced-page [data-testid="stTextArea"] textarea {
            font-family: var(--sc-font-mono);
            font-size: 0.8125rem;
            line-height: 1.35;
        }
        @media (max-width: 1100px) {
            .workspace-status-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
        @media (max-width: 900px) {
            [data-testid="stHorizontalBlock"]:has(.st-key-workspace_left_normal, .st-key-workspace_left_repair) {
                flex-direction: column;
                align-items: stretch;
            }
            [data-testid="stHorizontalBlock"]:has(.st-key-workspace_left_normal, .st-key-workspace_left_repair)
            > [data-testid="stColumn"] {
                width: 100% !important;
                flex: 1 1 100% !important;
            }
            .st-key-workspace_left_normal,
            .st-key-workspace_left_repair,
            .st-key-workspace_right {
                height: auto;
                flex: 0 0 auto !important;
                min-height: 0;
                overflow: visible;
                padding-right: 0;
            }
            .st-key-workspace_left_normal,
            .st-key-workspace_left_repair,
            .st-key-workspace_right {
                display: flex;
                flex-direction: column;
            }
            .st-key-workspace_left_normal .st-key-workspace_brief,
            .st-key-workspace_left_repair .st-key-workspace_repair_panel,
            .st-key-workspace_left_repair .st-key-workspace_brief {
                flex: 0 0 auto;
                min-height: 0;
            }
            .st-key-workspace_left_normal > [data-testid="stLayoutWrapper"]:has(.st-key-workspace_brief),
            .st-key-workspace_left_repair > [data-testid="stLayoutWrapper"]:has(.st-key-workspace_repair_panel),
            .st-key-workspace_left_repair > [data-testid="stLayoutWrapper"]:has(.st-key-workspace_brief) {
                flex: 0 0 auto;
                min-height: 0;
            }
            .st-key-workspace_right > [data-testid="stLayoutWrapper"] {
                height: auto !important;
            }
            .st-key-workspace_preview_panel,
            .st-key-workspace_playback_panel { min-height: 28rem; }
            .st-key-workspace_preview_stage,
            .st-key-workspace_playback_stage { min-height: 20rem; }
        }
        @media (max-width: 760px) {
            .block-container { padding-left: 0.8rem; padding-right: 0.8rem; }
            .st-key-workspace_toolbar [data-testid="column"]:first-child {
                flex-basis: 100% !important;
            }
        }
        </style>
        """
    st.markdown(
        css.replace("__WORKSPACE_DESKTOP_HEIGHT__", WORKSPACE_DESKTOP_HEIGHT).replace(
            "__WORKSPACE_MEDIA_ASPECT_RATIO__", WORKSPACE_MEDIA_ASPECT_RATIO
        ),
        unsafe_allow_html=True,
    )
