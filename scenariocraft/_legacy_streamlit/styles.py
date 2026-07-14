from __future__ import annotations

import streamlit as st

from scenariocraft._legacy_streamlit.state import WORKSPACE_DESKTOP_HEIGHT, WORKSPACE_MEDIA_ASPECT_RATIO


def inject_css() -> None:
    css = """
        <style>
        :root {
            --workspace-desktop-height: __WORKSPACE_DESKTOP_HEIGHT__;
            --workspace-media-aspect-ratio: __WORKSPACE_MEDIA_ASPECT_RATIO__;
            --sc-bg: #fbfaf7;
            --sc-bg-subtle: #f7f6f2;
            --sc-surface: #ffffff;
            --sc-surface-subtle: #f4f2ed;
            --sc-border: #e4e0d8;
            --sc-border-strong: #cdc7bb;
            --sc-text: #171717;
            --sc-text-secondary: #4d4d4d;
            --sc-text-muted: #7d7d7d;
            --sc-blue: #ff4e4e;
            --sc-blue-bg: #f0f7ff;
            --sc-red: #ea001d;
            --sc-red-bg: #ffeeef;
            --sc-amber: #ff9300;
            --sc-amber-bg: #fff6de;
            --sc-green: #28a948;
            --sc-green-bg: #ecfdec;
            --sc-purple: #a000f8;
            --sc-white: #ffffff;
            --sc-radius-sm: 10px;
            --sc-radius-md: 12px;
            --sc-space-1: 0.25rem;
            --sc-space-2: 0.5rem;
            --sc-space-3: 0.75rem;
            --sc-space-4: 1rem;
            --sc-shadow-raised: 0 1px 2px rgba(15, 15, 15, 0.04), 0 8px 24px -14px rgba(15, 15, 15, 0.10);
            --sc-focus-ring: 0 0 0 2px var(--sc-bg), 0 0 0 4px color-mix(in srgb, var(--sc-blue) 46%, transparent);
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
        .block-container {
            max-width: 1500px;
            padding: 1.05rem 1.1rem 1.2rem;
            margin-top: 0.45rem;
            border: 1px solid var(--sc-border);
            border-radius: var(--sc-radius-md);
            background: color-mix(in srgb, var(--sc-bg) 88%, #fff);
            box-shadow: 0 2px 12px rgba(30,40,65,.035);
        }
        h2 { margin-bottom: 0.2rem; letter-spacing: 0; }
        h3 {
            color: var(--sc-text);
            font-size: 0.84rem !important;
            font-weight: 600 !important;
            line-height: 1.35 !important;
            margin: 0 0 0.62rem 0 !important;
            letter-spacing: 0;
        }
        .st-key-workspace_left_normal,
        .st-key-workspace_left_repair,
        .st-key-workspace_right {
            height: var(--workspace-desktop-height);
            flex: 0 0 var(--workspace-desktop-height) !important;
            min-height: 0;
        }
        [data-testid="stHorizontalBlock"]:has(.st-key-workspace_left_normal) {
            gap: 1rem;
        }
        [data-testid="stHorizontalBlock"]:has(.st-key-workspace_left_repair) {
            gap: 1rem;
        }
        [data-testid="stHorizontalBlock"]:has(.st-key-workspace_left_normal)
        > [data-testid="stColumn"]:has(.st-key-workspace_left_normal) {
            flex: 0 1 clamp(30rem, 34vw, 32rem) !important;
            width: clamp(30rem, 34vw, 32rem) !important;
            min-width: 29rem;
        }
        [data-testid="stHorizontalBlock"]:has(.st-key-workspace_left_repair)
        > [data-testid="stColumn"]:has(.st-key-workspace_left_repair) {
            flex: 0 1 clamp(31rem, 36vw, 34rem) !important;
            width: clamp(31rem, 36vw, 34rem) !important;
            min-width: 29rem;
        }
        [data-testid="stHorizontalBlock"]:has(.st-key-workspace_left_normal)
        > [data-testid="stColumn"]:has(.st-key-workspace_right),
        [data-testid="stHorizontalBlock"]:has(.st-key-workspace_left_repair)
        > [data-testid="stColumn"]:has(.st-key-workspace_right) {
            flex: 1 1 0 !important;
            width: auto !important;
            min-width: 0;
        }
        .st-key-workspace_left_normal,
        .st-key-workspace_left_repair {
            display: flex;
            flex-direction: column;
            gap: 0.68rem;
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
            gap: 0.68rem;
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
        .st-key-workspace_preview_stage [data-testid="stImageContainer"],
        .st-key-workspace_playback_stage [data-testid="stImageContainer"] {
            display: flex;
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
        .st-key-workspace_preview_stage [data-testid="stFullScreenFrame"] > div,
        .st-key-workspace_playback_stage [data-testid="stFullScreenFrame"] > div {
            width: 100%;
            display: flex;
            justify-content: center;
        }
        .st-key-workspace_preview_stage [data-testid="stImage"] img,
        .st-key-workspace_playback_stage [data-testid="stImage"] img {
            width: min(100%, 980px) !important;
            height: auto !important;
            max-width: 100% !important;
            max-height: 100% !important;
            object-fit: contain;
        }
        .st-key-workspace_playback_stage [data-testid="stVideo"] video {
            width: min(100%, 980px);
            height: auto;
            max-height: 100%;
            object-fit: contain;
        }
        .st-key-workspace_toolbar [data-testid="stHorizontalBlock"] {
            align-items: center;
            flex-wrap: nowrap;
            gap: 0.48rem;
        }
        .st-key-workspace_toolbar [data-testid="stVerticalBlock"],
        .st-key-workspace_toolbar [data-testid="stElementContainer"],
        .st-key-workspace_toolbar [data-testid="stMarkdownContainer"] {
            margin-top: 0 !important;
            margin-bottom: 0 !important;
        }
        .st-key-workspace_toolbar [data-testid="stElementContainer"]:has(.workspace-provider-status) {
            width: 100% !important;
            height: 2.62rem !important;
            min-height: 2.62rem !important;
            display: flex;
            align-items: center;
        }
        .st-key-workspace_toolbar [data-testid="stElementContainer"]:has(.workspace-provider-status)
        [data-testid="stMarkdownContainer"] {
            width: 100% !important;
        }
        .st-key-workspace_toolbar [data-testid="stSelectbox"],
        .st-key-workspace_toolbar [data-testid="stButton"] {
            height: 2.62rem;
            min-height: 2.62rem;
            display: flex;
            align-items: center;
        }
        .st-key-workspace_toolbar [data-testid="column"]:first-child,
        .st-key-workspace_toolbar [data-testid="stColumn"]:first-child {
            flex: 0 1 4.6rem !important;
            width: 4.6rem !important;
            min-width: 4.6rem;
        }
        .st-key-workspace_toolbar [data-testid="column"]:nth-child(2),
        .st-key-workspace_toolbar [data-testid="stColumn"]:nth-child(2) {
            flex: 1 1 auto !important;
            width: auto !important;
            min-width: 8rem;
            max-width: none !important;
        }
        .st-key-workspace_toolbar [data-testid="column"]:nth-child(n+3),
        .st-key-workspace_toolbar [data-testid="stColumn"]:nth-child(n+3) {
            flex: 0 0 2.5rem !important;
            width: 2.62rem !important;
            min-width: 2.5rem;
        }
        .workspace-provider-status {
            width: 100%;
            height: 2.62rem;
            min-height: 2.62rem;
            display: flex;
            align-items: center;
            padding: 0 0.9rem;
            border: 1px solid var(--sc-border);
            border-radius: var(--sc-radius-sm);
            background: var(--sc-bg-subtle);
            color: var(--sc-text-muted);
            font-size: 0.82rem;
            font-weight: 520;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .workspace-micro-status {
            min-height: 1rem;
            margin: -0.08rem 0 0.38rem 0;
            color: var(--sc-text-muted);
            font-size: 0.74rem;
            line-height: 1.05rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .st-key-workspace_shuffle_prompt button,
        .st-key-workspace_generate button,
        .st-key-workspace_repair button {
            width: 2.5rem;
            min-width: 2.5rem;
            height: 2.62rem;
            min-height: 2.62rem;
            padding: 0;
            border-radius: var(--sc-radius-sm);
        }
        .st-key-workspace_shuffle_prompt button p,
        .st-key-workspace_generate button p,
        .st-key-workspace_repair button p { font-size: 0; }
        .st-key-workspace_shuffle_prompt button span,
        .st-key-workspace_generate button span,
        .st-key-workspace_repair button span { font-size: 1.2rem; }
        [data-testid="stVerticalBlockBorderWrapper"] {
            background: var(--sc-surface);
            border-color: var(--sc-border);
            border-radius: var(--sc-radius-sm);
            box-shadow: var(--sc-shadow-raised);
        }
        [data-testid="stVerticalBlockBorderWrapper"] > div {
            padding: 0.9rem 1rem;
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
        .workspace-loop-status {
            display: grid;
            gap: 0.44rem;
        }
        .workspace-loop-title {
            color: var(--sc-text-muted);
            font-size: 0.7rem;
            line-height: 1rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .workspace-status-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            column-gap: 0.62rem;
            row-gap: 0.36rem;
            align-items: start;
        }
        .status-item {
            display: flex;
            align-items: center;
            gap: 0.36rem;
            min-width: 0;
            border-radius: var(--sc-radius-sm);
            cursor: help;
            outline: 2px solid transparent;
            outline-offset: 3px;
        }
        .status-item:focus-visible { box-shadow: var(--sc-focus-ring); }
        .status-label {
            color: var(--sc-text-muted);
            font-size: 0.64rem;
            line-height: 1.05;
            white-space: nowrap;
            min-width: 2.75rem;
        }
        @media (prefers-color-scheme: dark) {
            .status-label { color: var(--sc-text-muted); }
        }
        .status-item strong {
            display: flex;
            align-items: center;
            gap: 0.3rem;
            font-size: 0.74rem;
            line-height: 1.15;
            font-weight: 650;
            white-space: nowrap;
            min-width: 0;
        }
        .status-item strong i {
            display: block;
            flex: 0 0 auto;
            width: 0.36rem;
            height: 0.36rem;
            border-radius: 50%;
            background: var(--sc-border-strong);
        }
        .status-passed strong i { background: var(--sc-green); }
        .status-failed strong i { background: var(--sc-red); }
        .status-waiting strong i { background: var(--sc-amber); }
        .workspace-brief {
            display: grid;
            gap: 0.54rem;
        }
        .workspace-brief-title {
            color: var(--sc-text);
            font-size: 0.95rem;
            line-height: 1.2;
            font-weight: 650;
            overflow-wrap: anywhere;
        }
        .workspace-brief-metrics {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.4rem;
        }
        .workspace-brief-metric {
            min-width: 0;
            padding: 0.44rem 0.52rem;
            border: 1px solid var(--sc-border);
            border-radius: var(--sc-radius-sm);
            background: var(--sc-bg-subtle);
            outline: 2px solid transparent;
            outline-offset: 2px;
            cursor: help;
        }
        .workspace-brief-metric:focus-visible { box-shadow: var(--sc-focus-ring); }
        .workspace-brief-metric span {
            display: block;
            color: var(--sc-text-muted);
            font-size: 0.64rem;
            line-height: 1.05;
            margin-bottom: 0.28rem;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .workspace-brief-metric strong {
            display: block;
            color: var(--sc-text);
            font-size: 0.86rem;
            line-height: 1.15;
            font-weight: 650;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .workspace-brief-details {
            display: flex;
            flex-wrap: wrap;
            gap: 0.32rem;
            color: var(--sc-text-muted);
            font-size: 0.68rem;
            line-height: 1.15;
        }
        .workspace-brief-details span {
            max-width: 100%;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            padding: 0.24rem 0.38rem;
            border: 1px solid var(--sc-border);
            border-radius: 999px;
            background: var(--sc-bg-subtle);
        }
        .st-key-workspace_request [data-testid="stExpander"] {
            border-color: var(--sc-border);
            border-radius: var(--sc-radius-sm);
            box-shadow: none;
            margin-top: 0.55rem;
        }
        .st-key-workspace_request [data-testid="stExpander"] summary {
            min-height: 2.2rem;
            font-size: 0.78rem;
            color: var(--sc-text-secondary);
        }
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
        .advanced-page-marker {
            display: none;
        }
        .advanced-pipeline-timeline {
            display: grid;
            grid-template-columns: repeat(8, minmax(0, 1fr));
            gap: 0;
            margin: 0.05rem 0 0.9rem 0;
            padding: 0.25rem 0.4rem 0.05rem 0.4rem;
            background: transparent;
        }
        .advanced-pipeline-node {
            position: relative;
            display: grid;
            grid-template-rows: auto auto auto auto;
            justify-items: center;
            row-gap: 0.18rem;
            align-items: center;
            min-width: 0;
            padding: 0.1rem 0.25rem;
            border-radius: var(--sc-radius-sm);
            outline: 2px solid transparent;
            outline-offset: 2px;
            cursor: help;
            text-align: center;
        }
        .advanced-pipeline-node:not(:last-child)::after {
            content: "";
            position: absolute;
            top: 1.05rem;
            left: calc(50% + 1.25rem);
            width: calc(100% - 2.5rem);
            border-top: 1px solid #dfe3ea;
        }
        .advanced-pipeline-node:focus-visible { box-shadow: var(--sc-focus-ring); }
        .advanced-pipeline-icon {
            display: grid;
            place-items: center;
            width: 2.1rem;
            height: 2.1rem;
            border: 1px solid #e2e7ef;
            border-radius: 50%;
            background: var(--sc-surface);
            color: var(--sc-text-muted);
            font-size: 0.78rem;
            font-weight: 650;
            box-shadow: 0 1px 3px rgba(24, 35, 54, 0.06);
            z-index: 1;
        }
        .advanced-pipeline-icon.status-passed { color: var(--sc-green); border-color: color-mix(in srgb, var(--sc-green) 28%, #e2e7ef); }
        .advanced-pipeline-icon.status-failed { color: var(--sc-red); border-color: color-mix(in srgb, var(--sc-red) 28%, #e2e7ef); }
        .advanced-pipeline-icon.status-waiting { color: var(--sc-amber); border-color: color-mix(in srgb, var(--sc-amber) 32%, #e2e7ef); }
        .advanced-pipeline-node strong {
            min-width: 0;
            color: var(--sc-text);
            font-size: 0.78rem;
            line-height: 1.1;
            font-weight: 650;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .advanced-pipeline-node small {
            color: var(--sc-text-muted);
            font-size: 0.64rem;
            line-height: 1.05;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .advanced-pipeline-dot {
            width: 0.42rem;
            height: 0.42rem;
            border-radius: 50%;
            background: var(--sc-border-strong);
        }
        .advanced-pipeline-dot.status-passed { background: var(--sc-green); }
        .advanced-pipeline-dot.status-failed { background: var(--sc-red); }
        .advanced-pipeline-dot.status-waiting { background: var(--sc-amber); }
        .advanced-card-heading {
            display: grid;
            gap: 0.12rem;
            margin-bottom: 0.6rem;
        }
        .advanced-card-heading strong {
            color: var(--sc-text);
            font-size: 0.96rem;
            line-height: 1.2;
            font-weight: 650;
        }
        .advanced-card-heading span {
            color: var(--sc-text-muted);
            font-size: 0.72rem;
            line-height: 1.25;
        }
        .advanced-summary-list {
            display: grid;
            gap: 0.38rem;
            margin-bottom: 0.55rem;
        }
        .advanced-summary-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: var(--sc-space-3);
            min-height: 1.82rem;
            padding: 0.36rem 0.56rem;
            border: 1px solid var(--sc-border);
            border-radius: var(--sc-radius-sm);
            background: var(--sc-bg-subtle);
            font-size: 0.78rem;
            line-height: 1.15;
        }
        .advanced-summary-row span {
            color: var(--sc-text-muted);
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }
        .advanced-summary-row strong {
            color: var(--sc-text);
            font-size: 0.78rem;
            font-weight: 600;
            text-align: right;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 55%;
        }
        .advanced-metric-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.45rem;
        }
        .advanced-metric-tile {
            min-height: 3.05rem;
            padding: 0.48rem 0.6rem;
            border: 1px solid var(--sc-border);
            border-radius: var(--sc-radius-sm);
            background: var(--sc-bg-subtle);
        }
        .advanced-metric-tile span {
            display: block;
            color: var(--sc-text-muted);
            font-size: 0.68rem;
            line-height: 1.05;
            margin-bottom: 0.3rem;
        }
        .advanced-metric-tile strong {
            color: var(--sc-text);
            font-size: 1rem;
            line-height: 1.15;
            font-weight: 650;
        }
        .stApp:has(.advanced-page-marker) [data-testid="stExpander"] {
            border-color: var(--sc-border);
            border-radius: var(--sc-radius-sm);
            box-shadow: var(--sc-shadow-raised);
        }
        .stApp:has(.advanced-page-marker) [data-testid="stExpander"] summary {
            font-family: var(--sc-font-sans);
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--sc-text);
        }
        .stApp:has(.advanced-page-marker) [data-testid="stTextArea"] textarea {
            font-family: var(--sc-font-mono);
            font-size: 0.8125rem;
            line-height: 1.35;
        }
        @media (max-width: 1100px) {
            .workspace-status-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .advanced-pipeline-timeline { grid-template-columns: repeat(4, minmax(0, 1fr)); }
            .advanced-pipeline-node:nth-child(4n)::after { display: none; }
            .advanced-metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
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
            .advanced-pipeline-timeline { grid-template-columns: repeat(2, minmax(0, 1fr)); }
            .advanced-pipeline-node::after { display: none; }
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
