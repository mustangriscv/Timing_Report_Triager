# app.py — Timing Report Analyzer (concise behavior + plotting + UI tweaks)
import os, io, re, tempfile
from io import StringIO
from collections import OrderedDict
import pandas as pd
import numpy as np
import streamlit as st
import pprint 

st.set_page_config(page_title="Timing Report Analyzer", layout="wide")

# Compact header
st.markdown(
    "<div style='font-size:20px;font-weight:600;margin:4px 0 10px 0'>Timing Report Analyzer</div>",
    unsafe_allow_html=True,
)

# ---- Debug toggle (optional) ----
DEBUG = st.sidebar.toggle("Debug mode", value=False)
def debug(msg, obj=None):
    if DEBUG:
        st.write(f"🔎 {msg}")
        if obj is not None:
            st.write(obj)

# ---- Plotly (histogram + pattern bars) ----
try:
    import plotly.express as px
    from plotly.subplots import make_subplots
    import plotly.graph_objects as go
    PLOTLY_OK = True
except Exception:
    PLOTLY_OK = False

# ---- Your custom functions (module alias) ----
# Must provide: read_file(path), cd_rpt(p_list, temp_dir=...),
#               filterSummaryCsv_ver2(...), processMultiPatterns(...)
import custom_func as cf


# ============================ Helpers ============================

CLK_LC_RE = re.compile(r"^LC_CLK:(.+)$")
CLK_CP_RE = re.compile(r"^CP_CLK:(.+)$")

NUMFILT_MAP = {  # 1=SP, 2=EP, 3=LC, 4=CP, 5=PathGroup
    "Startpoint": 1,
    "Endpoint": 2,
    "Launch Clock": 3,
    "Capture Clock": 4,
    "PathGroup": 5,
}
import math

def load_pure_summary_csv(path: str) -> pd.DataFrame | None:
    """
    Load temp_dir/pure_summary.csv as a DataFrame.
    Assumes a normal CSV with a header row.
    Trims spaces after commas.
    """
    if not os.path.exists(path):
        return None
    try:
        df = pd.read_csv(path, engine="python", sep=",", skipinitialspace=True)
        # Standardize a few common column names if needed
        # (uncomment/extend if your headers vary)
        # colmap = {
        #     "Startpoint": "SP", "Endpoint": "EP",
        #     "launch clock": "LAUNCH_CLK", "capture clock": "CAPTURE_CLK",
        #     "path group": "PATHGROUP", "cppr point": "CPPR", "unc": "UNC",
        #     "Slack": "SLACK", "Id": "PID",
        # }
        # df = df.rename(columns={k:v for k,v in colmap.items() if k in df.columns})
        return df
    except Exception as e:
        if DEBUG:
            debug("pure_summary.csv read error", str(e))
        return None

def show_paged_table(df: pd.DataFrame, per_page: int, key_prefix: str, sort_by: str | None = None, ascending: bool = True):
    """
    Render a paginated dataframe (per_page rows).
    Maintains page state in st.session_state with the given key_prefix.
    """
    if df is None or df.empty:
        st.info("No paths.")
        return

    if sort_by and sort_by in df.columns:
        try:
            df = df.sort_values(sort_by, ascending=ascending)
        except Exception:
            pass

    total = len(df)
    pages = max(1, math.ceil(total / per_page))
    page_key = f"{key_prefix}_page"
    if page_key not in st.session_state:
        st.session_state[page_key] = 1
    # Page selector
    left, right = st.columns([1.2, 6])
    with left:
        st.number_input(
            "Page", min_value=1, max_value=pages, step=1,
            key=page_key, label_visibility="collapsed"
        )
    with right:
        st.caption(f"Showing {per_page} per page · Total paths: {total} · Pages: {pages}")

    page = st.session_state[page_key]
    start = (page - 1) * per_page
    end   = start + per_page
    df_page = df.iloc[start:end].reset_index(drop=True)

    st.dataframe(df_page, use_container_width=True, hide_index=True, height=380)

def compute_numFilt(target_label: str, default_val: int = 2) -> int:
    return NUMFILT_MAP.get(target_label, default_val)

def base_no_ext(fname: str) -> str:
    fname = (fname or "").strip().strip("\"'")
    return os.path.splitext(os.path.basename(fname))[0] or "report"

def _to_float(x):
    try:
        return float(str(x).strip())
    except Exception:
        return None

def read_text_if_exists(path: str) -> str | None:
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    except Exception:
        pass
    return None

def cd_rpt_to_df(path_dict: OrderedDict, report_id: str) -> pd.DataFrame:
    """
    Normalize cd_rpt's path_dict into a flat DF for the unfiltered/histogram views.
    """
    rows, pid = [], 1
    for _, od in (path_dict or {}).items():
        if not isinstance(od, dict):
            continue
        sp  = od.get("SP:", "")
        ep  = od.get("EP:", "")
        pg  = od.get("PG:", "")
        unc = _to_float(od.get("CLK_UNC:", od.get("UNC:", None)))
        slk = _to_float(od.get("SLACK:", None))
        lc_name = cp_name = None
        for k in od.keys():
            m_lc = CLK_LC_RE.match(k); m_cp = CLK_CP_RE.match(k)
            if m_lc: lc_name = m_lc.group(1)
            if m_cp: cp_name = m_cp.group(1)
        cppr = od.get("CPPR:", od.get("CPPR_POINT:", ""))

        rows.append({
            "PID": pid, "SP": sp, "EP": ep, "SLACK": slk,
            "LAUNCH_CLK": lc_name, "CAPTURE_CLK": cp_name,
            "PATHGROUP": pg, "CPPR": cppr, "UNC": unc,
            "REPORT_ID": report_id,
        })
        pid += 1
    return pd.DataFrame(rows)

def show_hist(df: pd.DataFrame, bins=30, by_report=True):
    if df.empty or "SLACK" not in df.columns:
        st.info("No data for histogram.")
        return
    if PLOTLY_OK:
        fig = px.histogram(df, x="SLACK", nbins=bins, color="REPORT_ID" if by_report else None, marginal=None)
        fig.update_layout(height=240, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.write(df[["SLACK"]].describe())

def show_paths(df: pd.DataFrame, limit=20):
    """Compact table (no 'open report' buttons)."""
    if df.empty:
        st.info("No paths.")
        return
    cols = [c for c in ["PID","SP","EP","SLACK","LAUNCH_CLK","CAPTURE_CLK","PATHGROUP","CPPR","UNC"] if c in df.columns]
    view = df.sort_values("SLACK").head(limit)[cols].reset_index(drop=True)
    st.dataframe(view, use_container_width=True, hide_index=True, height=380)

def load_pat_summary_csv(path: str) -> pd.DataFrame | None:
    """
    Robust patSummary loader:
    - handles trailing commas & extra spaces
    - coerces numerics
    Columns: pattern, wns, tns, group, view, count
    """
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read()
    except Exception:
        return None
    # remove trailing comma before newline: "...,16,\n" -> "...,16\n"
    txt = re.sub(r",\s*(\r?\n)", r"\1", txt)
    df = pd.read_csv(
        StringIO(txt),
        engine="python",
        sep=",",
        header=None,
        names=["pattern", "wns", "tns", "group", "view", "count"],
        usecols=[0,1,2,3,4,5],
        skipinitialspace=True,
        dtype={"pattern": "string", "group": "string", "view": "string"},
    )
    # drop header row if present
    if len(df) and isinstance(df.loc[0, "pattern"], str) and df.loc[0, "pattern"].strip().lower() == "pattern":
        df = df.iloc[1:].reset_index(drop=True)
    # numerics
    df["wns"] = pd.to_numeric(df["wns"], errors="coerce")
    df["tns"] = pd.to_numeric(df["tns"], errors="coerce")
    df["count"] = pd.to_numeric(df["count"], errors="coerce").astype("Int64")
    # tidy strings
    for c in ("pattern", "group", "view"):
        df[c] = df[c].astype("string").str.strip()
    return df

def parse_filtered_section(filtered_txt: str, pid: int) -> pd.DataFrame:
    """
    Extract block between FILTERED:{pid}:Start and FILTERED:{pid}:End from
    filtDir/{file_name}_filtered.csv and build a table.
    """
    start_tag = f"FILTERED:{pid}:Start"
    end_tag   = f"FILTERED:{pid}:End"
    if start_tag not in filtered_txt or end_tag not in filtered_txt:
        return pd.DataFrame()
    section = filtered_txt.split(start_tag, 1)[1].split(end_tag, 1)[0]
    rows = []
    for ln in section.splitlines():
        ln = ln.strip()
        if not ln.startswith("Path:"):
            continue
        fields = [x.strip() for x in ln.split(",") if x.strip()]
        rec = {"PID": None, "SP": "", "EP": "", "LC_CLK": "", "CP_CLK": "", "VIEW": "", "PG": "", "SLACK": None}
        for f in fields:
            if ":" not in f:
                continue
            k, v = f.split(":", 1)
            k = k.strip(); v = v.strip()
            if   k == "Path":     rec["PID"] = v
            elif k == "SP":       rec["SP"] = v
            elif k == "EP":       rec["EP"] = v
            elif k == "LC_CLK":   rec["LC_CLK"] = v
            elif k == "CP_CLK":   rec["CP_CLK"] = v
            elif k == "VIEW":     rec["VIEW"] = v
            elif k == "PG":       rec["PG"] = v
            elif k == "SLACK":
                try: rec["SLACK"] = float(v)
                except: rec["SLACK"] = v
        rows.append(rec)
    return pd.DataFrame(rows)

def parse_comma_patterns(s: str) -> list[str]:
    """Split by comma, trim, drop empties, de-dupe preserving order."""
    if not s:
        return []
    parts = [p.strip() for p in s.split(",")]
    out, seen = [], set()
    for p in parts:
        if p and p not in seen:
            out.append(p); seen.add(p)
    return out


# ============================ Upload rows ============================

def upload_row(label: str, key_suffix: str):
    # Row: "ReportA: [Browse] [Path box]"
    c_lab, c_browse, c_path = st.columns([0.6, 1.4, 3.0])
    with c_lab:
        st.markdown(f"<div style='padding-top:6px'>{label}:</div>", unsafe_allow_html=True)
    with c_browse:
        up = st.file_uploader(
            label=f"{label} file",
            key=f"up_{key_suffix}",
            label_visibility="collapsed"
        )
    with c_path:
        path = st.text_input(
            label=f"{label} path",
            placeholder="/abs/path/to/report.rpt",
            key=f"path_{key_suffix}",
            label_visibility="collapsed"
        )

    data = name = src_path = None
    if up is not None:
        data, name = up.getvalue(), up.name
    elif path:
        if os.path.exists(path):
            try:
                with open(path, "rb") as f:
                    data = f.read()
                name = os.path.basename(path)
                src_path = path
            except Exception as e:
                st.error(f"{label}: read failed: {e}")
        else:
            st.warning(f"{label}: path not found")
    return data, name, src_path

dataA, nameA, pathA = upload_row("ReportA", "A")
dataB, nameB, pathB = upload_row("ReportB", "B")
dataC, nameC, pathC = upload_row("ReportC", "C")

uploads, names, src_paths = {}, {}, {}
if dataA: uploads["A"]=dataA; names["A"]=nameA or "A.rpt"; src_paths["A"]=pathA
if dataB: uploads["B"]=dataB; names["B"]=nameB or "B.rpt"; src_paths["B"]=pathB
if dataC: uploads["C"]=dataC; names["C"]=nameC or "C.rpt"; src_paths["C"]=pathC

st.markdown("---")

# ============================ Controls ============================

c1, c2, c3, c4, c5, c6 = st.columns([1.2, 1.6, 2.4, 2.4, 1, 1.1])
with c1:
    auto_filter = st.checkbox("Auto filter", value=True, help="If on, also run parser's pat_list")
with c2:
    auto_target = st.selectbox("Target", ["Endpoint", "Startpoint", "Launch Clock", "Capture Clock", "PathGroup"], index=0)
with c3:
    pattern_text = st.text_area("Patterns (comma‑separated regex)", height=80,
                                placeholder="EP:port_pad_data_out.*, EP:.*p_reg.*/D")
with c4:
    pattern_file = st.file_uploader("Pattern file (optional)", type=["txt"], key="patfile")
with c5:
    bins = st.slider("Bins", 5, 100, 30, step=5)
with c6:
    rows_per_report = st.slider("Rows/report", 5, 200, 20, step=5)

c_run1, c_run2 = st.columns([1,4])
with c_run1:
    run = st.button("Run", type="primary")
with c_run2:
    st.caption("Usage: upload 1–3 reports → (optionally) patterns and/or auto → Run")


# ============================ RUN (compute & persist) ============================

if run:
    if not uploads:
        st.error("Please upload at least one report.")
        st.stop()

    # Prepare session containers for persisted results
    st.session_state.setdefault("PARSED", {})    # per-report parsed dfs + artifacts
    st.session_state.setdefault("RESULTS", {})   # per-report outputs (summary, patSummary, filtered log)
    st.session_state["PARSED"].clear()
    st.session_state["RESULTS"].clear()

    frames = []
    for rid, b in uploads.items():
        raw_name = names.get(rid) or src_paths.get(rid) or f"report_{rid}.rpt"
        file_name = base_no_ext(raw_name)

        # Absolute working dir
        rpt_temp_dir = os.path.abspath(f"{file_name}_RPT{rid}")
        os.makedirs(rpt_temp_dir, exist_ok=True)

        # Write input bytes to temp path, then cf.read_file -> cf.cd_rpt
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b); tmp.flush()
            tmp_path = tmp.name

        try:
            p_list = cf.read_file(tmp_path)
        except Exception as e:
            st.error(f"{rid}: cf.read_file() failed"); st.exception(e); continue

        try:
            # cd_rpt -> path_dict, field_list, sp_ep_dict, pat_list
            path_dict, field_list, sp_ep_dict, pat_list,lastCommonPinDict = cf.cd_rpt(p_list, temp_dir=rpt_temp_dir)
            #pprint.pprint(path_dict)
        except Exception as e:
            st.error(f"{rid}: cf.cd_rpt() failed"); st.exception(e); continue

        debug(f"{rid} file_name/temp_dir", {"file_name": file_name, "temp_dir": rpt_temp_dir})
        debug(f"{rid} sizes", {
            "paths": len(path_dict) if path_dict else 0,
            "patterns": len(pat_list) if pat_list else 0,
            "fields": len(field_list) if field_list else 0,
            "sp->ep": len(sp_ep_dict) if sp_ep_dict else 0,
        })

        try:
            df = cd_rpt_to_df(path_dict, rid)
        except Exception as e:
            st.error(f"{rid}: normalization failed"); st.exception(e); continue

        if df is None or df.empty:
            st.warning(f"{rid}: no paths parsed"); continue

        df["REPORT_ID"] = rid
        if "PID" not in df.columns:
            df.insert(0, "PID", range(1, len(df)+1))

        # Persist parsed artifacts for UI rendering later
        st.session_state["PARSED"][rid] = {
            "df": df,
            "path_dict": path_dict,
            "field_list": field_list,
            "sp_ep_dict": sp_ep_dict,
            "pat_list": list(pat_list) if pat_list else [],
            "file_name": file_name,
            "temp_dir": rpt_temp_dir,
        }
        frames.append(df)

    if not frames:
        st.error("No data parsed from the uploaded reports.")
        st.stop()

    # Build combined DF for histogram & cache filter inputs
    all_df = pd.concat(frames, ignore_index=True)
    st.session_state["all_df"] = all_df
    st.session_state["filters"] = {
        "auto_filter": auto_filter,
        "auto_target": auto_target,
        "patterns": parse_comma_patterns(pattern_text),
        "pattern_file_bytes": pattern_file.getvalue() if pattern_file else None,
        "numFilt": compute_numFilt(auto_target, default_val=2),
    }

    # Now run filters per concise behavior
    for rid, art in st.session_state["PARSED"].items():
        path_dict  = art["path_dict"]
        file_name  = art["file_name"]
        temp_dir   = art["temp_dir"]
        cd_patlist = art["pat_list"] or []  # pat_list from cd_rpt

        auto_flag  = st.session_state["filters"]["auto_filter"]
        patterns   = st.session_state["filters"]["patterns"]
        pfile_bytes= st.session_state["filters"]["pattern_file_bytes"]
        numFilt    = st.session_state["filters"]["numFilt"]

        ran_filters = False

        if auto_flag and not patterns and (pfile_bytes is None):
            # Case: only auto
            if cd_patlist:
                try:
                    cf.processMultiPatterns(path_dict, cd_patlist, file_name, int(numFilt), temp_dir=temp_dir)
                    ran_filters = True
                except Exception as e:
                    st.error(f"{rid}: processMultiPatterns(auto) failed"); st.exception(e)

        elif patterns:
            # Case: explicit patterns (comma-separated)
            try:
                if len(patterns) > 1:
                    cf.processMultiPatterns(path_dict, patterns, file_name, int(numFilt), temp_dir=temp_dir)
                else:
                    cf.filterSummaryCsv_ver2(path_dict, patterns[0], file_name, int(numFilt), temp_dir=temp_dir)
                ran_filters = True
            except Exception as e:
                st.error(f"{rid}: pattern filtering failed"); st.exception(e)

            # If auto also on, run auto AFTER explicit patterns
            if auto_flag and cd_patlist:
                try:
                    cf.processMultiPatterns(path_dict, cd_patlist, file_name, int(numFilt), temp_dir=temp_dir)
                    ran_filters = True
                except Exception as e:
                    st.error(f"{rid}: processMultiPatterns(auto after patterns) failed"); st.exception(e)

        elif pfile_bytes is not None:
            # Case: pattern file
            with tempfile.NamedTemporaryFile(delete=False) as ptmp:
                ptmp.write(pfile_bytes); ptmp.flush()
                pfile_path = ptmp.name
            try:
                pats_from_file = cf.read_file(pfile_path) or []
            except Exception as e:
                st.error(f"{rid}: cf.read_file(pattern_file) failed"); st.exception(e); pats_from_file = []

            if pats_from_file:
                try:
                    cf.processMultiPatterns(path_dict, pats_from_file, file_name, int(numFilt), temp_dir=temp_dir)
                    ran_filters = True
                except Exception as e:
                    st.error(f"{rid}: processMultiPatterns(pattern_file) failed"); st.exception(e)

            # If auto also on, run auto AFTER file patterns
            if auto_flag and cd_patlist:
                try:
                    cf.processMultiPatterns(path_dict, cd_patlist, file_name, int(numFilt), temp_dir=temp_dir)
                    ran_filters = True
                except Exception as e:
                    st.error(f"{rid}: processMultiPatterns(auto after pattern_file) failed"); st.exception(e)
        else:
            # No filters requested
            pass

        # Load generated outputs into session state for rendering
        summary_csv = os.path.join(temp_dir, "summary.csv")
        try:
            df_summary = pd.read_csv(summary_csv) if os.path.exists(summary_csv) else None
        except Exception:
            df_summary = None

        pat_summary_csv = os.path.join(temp_dir, "patSummary.csv")
        df_pat = load_pat_summary_csv(pat_summary_csv) if ran_filters else None
        if df_pat is not None and not df_pat.empty:
            df_pat = df_pat.reset_index(drop=True)
            df_pat.insert(0, "PId", df_pat.index + 1)

        filtered_log_path = os.path.join(temp_dir, "filtDir", f"{file_name}_filtered.csv")
        filtered_log_txt = read_text_if_exists(filtered_log_path) if ran_filters else None

        st.session_state["RESULTS"][rid] = {
            "ran_filters": ran_filters,
            "summary_df": df_summary,
            "pat_summary_df": df_pat,
            "filtered_log_txt": filtered_log_txt,
        }


# ============================ RENDER (from persisted state) ============================

if "PARSED" in st.session_state and st.session_state["PARSED"]:
    # Top caption + histogram
    all_df = st.session_state.get("all_df", pd.DataFrame())
    n_reports = all_df["REPORT_ID"].nunique() if "REPORT_ID" in all_df.columns else 0
    st.caption(f"Loaded **{len(all_df)}** paths from **{n_reports}** report(s).")

    st.subheader("Slack histogram (all parsed paths)")
    show_hist(all_df, bins=bins if "bins" in locals() else 30, by_report=True)

    # Per-report sections
    for rid in ["A", "B", "C"]:
        if rid not in st.session_state["PARSED"]:
            continue

        art = st.session_state["PARSED"][rid]
        df_r = art["df"]
        file_name = art["file_name"]
        temp_dir  = art["temp_dir"]

        st.markdown(f"### Path Summary Report {rid}")
        #>>AMT:show_paths(df_r, limit=rows_per_report if "rows_per_report" in locals() else 20)


	# Prefer temp_dir/pure_summary.csv; fallback to parsed df if missing
        pure_summary_path = os.path.join(temp_dir, "pure_summary.csv")
        df_pure = load_pure_summary_csv(pure_summary_path)

        if df_pure is not None and not df_pure.empty:
            # Show ALL rows, 25 per page, sorted by SLACK ascending if present
            show_paged_table(
                df_pure,
                per_page=25,
                key_prefix=f"pure_{rid}",
                sort_by="SLACK",
                ascending=True
            )
        else:
            st.caption("pure_summary.csv not found or empty — showing parsed summary instead.")
            show_paged_table(
                df_r,
                per_page=25,
                key_prefix=f"parsed_{rid}",
                sort_by="SLACK",
                ascending=True
            )

        st.markdown(f"### Filtering and Summaries Report {rid}")

        res = st.session_state.get("RESULTS", {}).get(rid, {})
        # summary.csv expander
        df_summary = res.get("summary_df")
        with st.expander(f"{rid} · summary.csv", expanded=False):
            if df_summary is not None and not df_summary.empty:
                st.dataframe(df_summary, use_container_width=True, height=220)
            else:
                st.caption("summary.csv not found or empty")

        # patSummary + drilldown + PLOT
        if res.get("ran_filters") and isinstance(res.get("pat_summary_df"), pd.DataFrame):
            df_pat = res["pat_summary_df"]
            if not df_pat.empty:
                st.dataframe(df_pat, use_container_width=True, height=260)

                # Pattern selection (stable across reruns)
                sel_key = f"sel_pid_{rid}"
                if sel_key not in st.session_state:
                    st.session_state[sel_key] = int(df_pat.loc[0, "PId"])

                pat_choices = [f"{int(r.PId)} — {str(r.pattern)}" for r in df_pat.itertuples(index=False)]
                try:
                    current_index = int(df_pat.index[df_pat["PId"] == st.session_state[sel_key]][0])
                except Exception:
                    current_index = 0
                    st.session_state[sel_key] = int(df_pat.loc[0, "PId"])

                new_index = st.selectbox(
                    f"{rid}: Open paths for pattern",
                    options=list(range(len(pat_choices))),
                    format_func=lambda i: pat_choices[i],
                    index=current_index,
                    key=f"pat_select_{rid}",
                )
                st.session_state[sel_key] = int(df_pat.loc[new_index, "PId"])

                # Drilldown: show matching paths from filtered log
                filtered_log_txt = res.get("filtered_log_txt")
                if filtered_log_txt:
                    pid_to_show = st.session_state[sel_key]
                    df_sec = parse_filtered_section(filtered_log_txt, pid_to_show)
                    if df_sec is not None and not df_sec.empty:
                        show_cols = [c for c in ["PID","SP","EP","SLACK","LC_CLK","CP_CLK","PG","VIEW"] if c in df_sec.columns]
                        st.dataframe(df_sec[show_cols].sort_values("SLACK"), use_container_width=True, height=320)
                    else:
                        st.info("No matching section found in filtered log.")

                # ---- New: Plot button for WNS/TNS/Count per pattern ----
                if PLOTLY_OK:
                    if st.button(f"Plot pattern metrics ({rid})", key=f"plot_btn_{rid}"):
                        # Ensure numeric columns
                        df_plot = df_pat.copy()
                        df_plot["wns"] = pd.to_numeric(df_plot["wns"], errors="coerce")
                        df_plot["tns"] = pd.to_numeric(df_plot["tns"], errors="coerce")
                        df_plot["count"] = pd.to_numeric(df_plot["count"], errors="coerce")

                        fig = make_subplots(specs=[[{"secondary_y": True}]])
                        x = df_plot["pattern"].astype(str).tolist()

                        fig.add_trace(go.Bar(name="WNS", x=x, y=df_plot["wns"]), secondary_y=False)
                        fig.add_trace(go.Bar(name="TNS", x=x, y=df_plot["tns"]), secondary_y=False)
                        fig.add_trace(go.Bar(name="Count", x=x, y=df_plot["count"]), secondary_y=True)

                        fig.update_layout(
                            barmode="group",
                            height=360,
                            margin=dict(l=10, r=10, t=10, b=10),
                            xaxis_title="Pattern",
                            yaxis_title="WNS / TNS",
                            legend_title="Metric",
                        )
                        fig.update_xaxes(tickangle=45)
                        fig.update_yaxes(title_text="Count", secondary_y=True)

                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("Plotly not available; cannot draw pattern metrics chart.")
        else:
            st.caption("No filters were run for this report.")
else:
    st.info("Upload 1–3 reports, choose options, and click Run.")

From adityatumsare Sat Sep  6 10:16:36 2025
To: , -s, adityatumsare0692@gmail.com, app_new_v5.py
Subject: app


