from __future__ import annotations

import streamlit as st

from scenariocraft.web.state import WORKSPACE_DESKTOP_HEIGHT, WORKSPACE_MEDIA_ASPECT_RATIO


def inject_css() -> None:
    css = """
        <style>
        :root { --workspace-desktop-height: __WORKSPACE_DESKTOP_HEIGHT__; }
        header[data-testid="stHeader"] { display: none; }
        #MainMenu, [data-testid="stDeployButton"] { display: none; }
        .block-container { max-width: 1680px; padding-top: 0.8rem; padding-bottom: 2rem; }
        h2 { margin-bottom: 0.2rem; letter-spacing: 0; }
        h3 { font-size: 1.02rem !important; margin: 0 0 0.65rem 0 !important; letter-spacing: 0; }
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
            gap: 0.75rem;
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
            gap: 0.75rem;
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
            gap: 0.55rem;
        }
        .st-key-workspace_preview_panel > [data-testid="stLayoutWrapper"]:has(.st-key-workspace_preview_stage),
        .st-key-workspace_playback_panel > [data-testid="stLayoutWrapper"]:has(.st-key-workspace_playback_stage) {
            flex: 1 1 0 !important;
            min-height: 0;
            overflow: hidden;
        }
        .st-key-workspace_preview_stage,
        .st-key-workspace_playback_stage {
            --workspace-media-aspect-ratio: __WORKSPACE_MEDIA_ASPECT_RATIO__;
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
            gap: 0.5rem;
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
        }
        .st-key-workspace_generate button p,
        .st-key-workspace_repair button p { font-size: 0; }
        .st-key-workspace_generate button span,
        .st-key-workspace_repair button span { font-size: 1.2rem; }
        [data-testid="stVerticalBlockBorderWrapper"] {
            border-color: #dfe3e8;
            border-radius: 8px;
            box-shadow: none;
        }
        [data-testid="stMetric"] { padding: 0; }
        [data-testid="stMetricLabel"] { font-size: 0.72rem; }
        [data-testid="stMetricValue"] { font-size: 1.15rem; }
        [data-testid="stImage"] img { object-fit: contain; max-height: 390px; }
        .st-key-workspace_status > div { padding-top: 0.1rem; padding-bottom: 0.1rem; }
        .workspace-status-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            column-gap: 1rem;
            row-gap: 0.6rem;
            align-items: start;
        }
        .status-item {
            display: flex;
            flex-direction: column;
            gap: 0.24rem;
            min-width: 0;
            border-radius: 4px;
            cursor: help;
            outline: 2px solid transparent;
            outline-offset: 3px;
        }
        .status-item:focus-visible { outline-color: #ef4444; }
        .status-label { color: #6b7280; font-size: 0.72rem; line-height: 1.15; white-space: nowrap; }
        @media (prefers-color-scheme: dark) {
            .status-label { color: #9ca3af; }
        }
        .status-item strong {
            display: flex;
            align-items: center;
            gap: 0.38rem;
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
            background: #9ca3af;
        }
        .status-passed strong i { background: #16a34a; }
        .status-failed strong i { background: #dc2626; }
        .status-waiting strong i { background: #d97706; }
        .repair-failure-list { display: grid; gap: 0.55rem; }
        .repair-failure {
            display: grid;
            gap: 0.2rem;
            padding: 0.7rem 0.8rem;
            border: 1px solid color-mix(in srgb, #dc2626 28%, transparent);
            border-radius: 6px;
            background: color-mix(in srgb, #dc2626 8%, transparent);
            color: #dc2626;
            font-size: 0.82rem;
            line-height: 1.35;
        }
        .repair-failure strong { font-size: 0.78rem; overflow-wrap: anywhere; }
        .status-ok, .status-error, .status-muted {
            border-radius: 8px;
            padding: 0.6rem 0.75rem;
            margin: 0.4rem 0 0.8rem 0;
            font-size: 0.92rem;
        }
        .status-ok { background: #ecfdf5; color: #047857; border: 1px solid #a7f3d0; }
        .status-error { background: #fef2f2; color: #b91c1c; border: 1px solid #fecaca; }
        .status-muted { background: #f8fafc; color: #475569; border: 1px solid #e2e8f0; }
        .preview-shell {
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            padding: 0.5rem;
            background: #ffffff;
        }
        .legend {
            display: flex;
            gap: 0.85rem;
            flex-wrap: wrap;
            font-size: 0.78rem;
            color: #334155;
            padding: 0 0.25rem 0.25rem 0.25rem;
        }
        .legend b {
            display: inline-block;
            width: 0.72rem;
            height: 0.72rem;
            border-radius: 2px;
            margin-right: 0.32rem;
            vertical-align: -0.08rem;
        }
        .legend .ego { background: #111827; }
        .legend .van { background: #1d4ed8; }
        .legend .ped { background: #dc2626; }
        .legend .trigger { background: #7c3aed; }
        .vehicle-label { fill: white; font-size: 13px; font-weight: 700; }
        .label { fill: #0f172a; font-size: 12px; font-weight: 650; }
        .lane-label { fill: #f8fafc; font-size: 13px; font-weight: 650; opacity: 0.92; }
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
