import streamlit as st
import pandas as pd
import json
from datetime import datetime
from pathlib import Path
import plotly.express as px

# ─── Config ───────────────────────────────────────────────────────────────────
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

OPP_FILE = DATA_DIR / "opportunities.csv"
COL_FILE  = DATA_DIR / "collections.csv"
SET_FILE  = DATA_DIR / "settings.json"

MONTHS = [
    "January","February","March","April","May","June",
    "July","August","September","October","November","December",
]
MONTH_NUM = {m: i + 1 for i, m in enumerate(MONTHS)}
STATUS_OPTIONS = ["Open", "Commit", "Best Case", "Won", "Lost"]


# ─── Helpers ──────────────────────────────────────────────────────────────────
def get_fy_quarter(month_num: int, cal_year: int) -> tuple:
    """Return (quarter, fy_label) for a calendar month + year.
    FY runs April–March: e.g. April 2024 → Q1 FY2024-25.
    """
    if month_num >= 4:
        fy_start = cal_year
        if month_num <= 6:
            q = "Q1"
        elif month_num <= 9:
            q = "Q2"
        else:
            q = "Q3"
    else:
        fy_start = cal_year - 1
        q = "Q4"
    return q, f"FY{fy_start}-{str(fy_start + 1)[2:]}"


def load_settings() -> dict:
    if SET_FILE.exists():
        return json.loads(SET_FILE.read_text())
    default = {"am_pct": 5.0, "csm_pct": 3.0, "reps": []}
    SET_FILE.write_text(json.dumps(default, indent=2))
    return default


def save_settings(s: dict):
    SET_FILE.write_text(json.dumps(s, indent=2))


def load_opportunities() -> pd.DataFrame:
    cols = [
        "id", "opportunity_name", "client_name", "rep_name", "rep_type",
        "value", "close_month", "close_year", "quarter", "fy", "status",
    ]
    if OPP_FILE.exists():
        return pd.read_csv(OPP_FILE)
    return pd.DataFrame(columns=cols)


def save_opportunities(df: pd.DataFrame):
    df.to_csv(OPP_FILE, index=False)


def load_collections() -> pd.DataFrame:
    cols = ["id", "rep_name", "rep_type", "month", "year", "amount"]
    if COL_FILE.exists():
        return pd.read_csv(COL_FILE)
    return pd.DataFrame(columns=cols)


def save_collections(df: pd.DataFrame):
    df.to_csv(COL_FILE, index=False)


def next_id(df: pd.DataFrame) -> int:
    return int(df["id"].max()) + 1 if not df.empty else 1


def current_fy_label() -> str:
    now = datetime.now()
    _, label = get_fy_quarter(now.month, now.year)
    return label


# ─── Dashboard ────────────────────────────────────────────────────────────────
def page_dashboard():
    st.title("Dashboard")
    opp_df = load_opportunities()

    fy_label = current_fy_label()
    st.subheader(f"Pipeline Overview — {fy_label}")

    if opp_df.empty:
        st.info("No opportunities yet. Add some in the Opportunities page.")
        return

    fy_df = opp_df[opp_df["fy"] == fy_label] if "fy" in opp_df.columns else opp_df
    open_statuses = ["Open", "Commit", "Best Case"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Open Pipeline", f"₹{fy_df[fy_df['status'].isin(open_statuses)]['value'].sum():,.0f}")
    c2.metric("Won", f"₹{fy_df[fy_df['status'] == 'Won']['value'].sum():,.0f}")
    c3.metric("Lost", f"₹{fy_df[fy_df['status'] == 'Lost']['value'].sum():,.0f}")
    c4.metric("Total Deals", len(fy_df))

    st.divider()

    # Pipeline by Quarter & Status
    q_data = (
        fy_df.groupby(["quarter", "status"])["value"]
        .sum()
        .reset_index()
    )
    if not q_data.empty:
        fig = px.bar(
            q_data, x="quarter", y="value", color="status",
            barmode="group", title="Pipeline by Quarter",
            labels={"value": "Value (₹)", "quarter": "Quarter"},
            category_orders={"quarter": ["Q1", "Q2", "Q3", "Q4"]},
        )
        st.plotly_chart(fig, use_container_width=True)

    col_l, col_r = st.columns(2)

    # Status pie
    with col_l:
        status_data = fy_df.groupby("status")["value"].sum().reset_index()
        if not status_data.empty:
            fig2 = px.pie(status_data, names="status", values="value", title="By Status")
            st.plotly_chart(fig2, use_container_width=True)

    # Rep pipeline
    with col_r:
        rep_data = (
            fy_df[fy_df["status"].isin(open_statuses + ["Won"])]
            .groupby(["rep_name", "rep_type"])["value"]
            .sum()
            .reset_index()
            .rename(columns={"rep_name": "Rep", "rep_type": "Type", "value": "Value (₹)"})
        )
        if not rep_data.empty:
            fig3 = px.bar(
                rep_data, x="Rep", y="Value (₹)", color="Type",
                title="Pipeline by Rep",
                color_discrete_map={"AM": "#1f77b4", "CSM": "#ff7f0e"},
            )
            st.plotly_chart(fig3, use_container_width=True)


# ─── Opportunities ────────────────────────────────────────────────────────────
def page_opportunities():
    st.title("Opportunities")
    settings = load_settings()
    reps = settings.get("reps", [])
    rep_names = [r["name"] for r in reps]

    tab_view, tab_add = st.tabs(["View & Edit", "Add New"])

    # ── View & Edit ──
    with tab_view:
        df = load_opportunities()
        if df.empty:
            st.info("No opportunities yet.")
        else:
            c1, c2, c3 = st.columns(3)
            fy_opts = ["All"] + sorted(df["fy"].unique().tolist(), reverse=True)
            sel_fy     = c1.selectbox("Financial Year", fy_opts)
            sel_q      = c2.selectbox("Quarter", ["All", "Q1", "Q2", "Q3", "Q4"])
            sel_status = c3.selectbox("Status", ["All"] + STATUS_OPTIONS)

            filtered = df.copy()
            if sel_fy     != "All": filtered = filtered[filtered["fy"]     == sel_fy]
            if sel_q      != "All": filtered = filtered[filtered["quarter"] == sel_q]
            if sel_status != "All": filtered = filtered[filtered["status"]  == sel_status]

            show = filtered[[
                "opportunity_name", "client_name", "rep_name", "rep_type",
                "value", "close_month", "close_year", "quarter", "fy", "status",
            ]].rename(columns={
                "opportunity_name": "Opportunity", "client_name": "Client",
                "rep_name": "Rep", "rep_type": "Type", "value": "Value (₹)",
                "close_month": "Month", "close_year": "Year",
                "quarter": "Quarter", "fy": "FY", "status": "Status",
            })
            st.dataframe(show, use_container_width=True, hide_index=True)
            st.caption(f"**{len(filtered)} deals · Total: ₹{filtered['value'].sum():,.0f}**")

            # Edit / Delete
            if not filtered.empty:
                st.divider()
                st.subheader("Edit or Delete")
                opp_id = st.selectbox(
                    "Select deal",
                    options=filtered["id"].tolist(),
                    format_func=lambda i: filtered[filtered["id"] == i]["opportunity_name"].values[0],
                )
                row = df[df["id"] == opp_id].iloc[0]

                with st.form("edit_form"):
                    e_name   = st.text_input("Opportunity Name", row["opportunity_name"])
                    e_client = st.text_input("Client Name", row["client_name"])
                    if rep_names:
                        idx = rep_names.index(row["rep_name"]) if row["rep_name"] in rep_names else 0
                        e_rep = st.selectbox("Rep", rep_names, index=idx)
                    else:
                        e_rep = st.text_input("Rep", row["rep_name"])
                    e_value  = st.number_input("Value (₹)", value=float(row["value"]), min_value=0.0, step=1000.0)
                    ec1, ec2 = st.columns(2)
                    e_month = ec1.selectbox(
                        "Close Month", MONTHS,
                        index=MONTHS.index(row["close_month"]) if row["close_month"] in MONTHS else 0,
                    )
                    e_year   = ec2.number_input("Close Year", value=int(row["close_year"]), min_value=2020, max_value=2035)
                    e_status = st.selectbox(
                        "Status", STATUS_OPTIONS,
                        index=STATUS_OPTIONS.index(row["status"]) if row["status"] in STATUS_OPTIONS else 0,
                    )

                    bc1, bc2 = st.columns(2)
                    save_btn   = bc1.form_submit_button("Save Changes", type="primary")
                    delete_btn = bc2.form_submit_button("Delete", type="secondary")

                    if save_btn:
                        rep_type = next((r["type"] for r in reps if r["name"] == e_rep), row["rep_type"])
                        q, fy = get_fy_quarter(MONTH_NUM[e_month], int(e_year))
                        df.loc[df["id"] == opp_id, [
                            "opportunity_name", "client_name", "rep_name", "rep_type",
                            "value", "close_month", "close_year", "quarter", "fy", "status",
                        ]] = [e_name, e_client, e_rep, rep_type, e_value, e_month, int(e_year), q, fy, e_status]
                        save_opportunities(df)
                        st.success("Updated!")
                        st.rerun()

                    if delete_btn:
                        save_opportunities(df[df["id"] != opp_id])
                        st.success("Deleted!")
                        st.rerun()

    # ── Add New ──
    with tab_add:
        if not reps:
            st.warning("Add reps in Settings first.")
            return

        with st.form("add_opp_form"):
            opp_name    = st.text_input("Opportunity Name *")
            client_name = st.text_input("Client Name *")
            rep_name    = st.selectbox("Assign Rep *", rep_names)
            value       = st.number_input("Value (₹) *", min_value=0.0, step=1000.0)
            ac1, ac2    = st.columns(2)
            close_month = ac1.selectbox("Expected Close Month *", MONTHS, index=MONTHS.index("March"))
            close_year  = ac2.number_input("Expected Close Year *", value=datetime.now().year, min_value=2020, max_value=2035)
            status      = st.selectbox("Status *", STATUS_OPTIONS)

            if st.form_submit_button("Add Opportunity", type="primary"):
                if not opp_name or not client_name:
                    st.error("Opportunity Name and Client Name are required.")
                else:
                    df   = load_opportunities()
                    rt   = next((r["type"] for r in reps if r["name"] == rep_name), "AM")
                    q, fy = get_fy_quarter(MONTH_NUM[close_month], int(close_year))
                    df = pd.concat([df, pd.DataFrame([{
                        "id": next_id(df), "opportunity_name": opp_name,
                        "client_name": client_name, "rep_name": rep_name,
                        "rep_type": rt, "value": value, "close_month": close_month,
                        "close_year": int(close_year), "quarter": q, "fy": fy, "status": status,
                    }])], ignore_index=True)
                    save_opportunities(df)
                    st.success(f"Added '{opp_name}' → {q} {fy}")
                    st.rerun()


# ─── Collections ──────────────────────────────────────────────────────────────
def page_collections():
    st.title("Collections")
    settings = load_settings()
    reps = settings.get("reps", [])

    if not reps:
        st.warning("Add reps in Settings first.")
        return

    tab_view, tab_add = st.tabs(["View", "Record Collection"])

    with tab_view:
        df = load_collections()
        if df.empty:
            st.info("No collections recorded yet.")
        else:
            c1, c2, c3 = st.columns(3)
            year_opts = ["All"] + sorted(df["year"].unique().astype(str).tolist(), reverse=True)
            sel_year  = c1.selectbox("Year",     year_opts)
            sel_month = c2.selectbox("Month",    ["All"] + MONTHS)
            sel_type  = c3.selectbox("Rep Type", ["All", "AM", "CSM"])

            filtered = df.copy()
            if sel_year  != "All": filtered = filtered[filtered["year"].astype(str) == sel_year]
            if sel_month != "All": filtered = filtered[filtered["month"] == sel_month]
            if sel_type  != "All": filtered = filtered[filtered["rep_type"] == sel_type]

            st.dataframe(
                filtered[["rep_name", "rep_type", "month", "year", "amount"]].rename(columns={
                    "rep_name": "Rep", "rep_type": "Type", "month": "Month",
                    "year": "Year", "amount": "Amount (₹)",
                }),
                use_container_width=True, hide_index=True,
            )
            st.metric("Total Collections", f"₹{filtered['amount'].sum():,.0f}")

            # Monthly trend
            if not filtered.empty:
                trend = (
                    filtered.groupby(["year", "month"])["amount"].sum()
                    .reset_index()
                    .assign(period=lambda d: d["month"] + " " + d["year"].astype(str))
                )
                fig = px.bar(trend, x="period", y="amount", title="Monthly Collections",
                             labels={"amount": "Amount (₹)", "period": "Month"})
                st.plotly_chart(fig, use_container_width=True)

    with tab_add:
        with st.form("add_col_form"):
            rep_name = st.selectbox("Rep", [r["name"] for r in reps])
            ac1, ac2 = st.columns(2)
            month  = ac1.selectbox("Month", MONTHS, index=datetime.now().month - 1)
            year   = ac2.number_input("Year", value=datetime.now().year, min_value=2020, max_value=2035)
            amount = st.number_input("Amount Collected (₹)", min_value=0.0, step=1000.0)

            if st.form_submit_button("Record Collection", type="primary"):
                df  = load_collections()
                rt  = next((r["type"] for r in reps if r["name"] == rep_name), "AM")
                df = pd.concat([df, pd.DataFrame([{
                    "id": next_id(df), "rep_name": rep_name, "rep_type": rt,
                    "month": month, "year": int(year), "amount": amount,
                }])], ignore_index=True)
                save_collections(df)
                st.success(f"Recorded ₹{amount:,.0f} for {rep_name} — {month} {year}")
                st.rerun()


# ─── Incentives ───────────────────────────────────────────────────────────────
def page_incentives():
    st.title("Incentive Calculator")
    settings  = load_settings()
    reps      = settings.get("reps", [])
    am_pct    = settings.get("am_pct", 5.0)
    csm_pct   = settings.get("csm_pct", 3.0)

    col_df = load_collections()
    if col_df.empty:
        st.info("No collections data yet.")
        return

    c1, c2, c3 = st.columns(3)
    year_opts = ["All"] + sorted(col_df["year"].unique().astype(str).tolist(), reverse=True)
    sel_year  = c1.selectbox("Year",     year_opts)
    sel_month = c2.selectbox("Month",    ["All"] + MONTHS)
    sel_type  = c3.selectbox("Rep Type", ["All", "AM", "CSM"])

    filtered = col_df.copy()
    if sel_year  != "All": filtered = filtered[filtered["year"].astype(str) == sel_year]
    if sel_month != "All": filtered = filtered[filtered["month"] == sel_month]
    if sel_type  != "All": filtered = filtered[filtered["rep_type"] == sel_type]

    # Aggregate collections per rep
    rep_totals = (
        filtered.groupby(["rep_name", "rep_type"])["amount"]
        .sum()
        .reset_index()
        .rename(columns={"rep_name": "Rep", "rep_type": "Type", "amount": "Collections"})
    )

    def incentive_rate(rep_name, rep_type):
        for r in reps:
            if r["name"] == rep_name and "custom_pct" in r:
                return r["custom_pct"]
        return am_pct if rep_type == "AM" else csm_pct

    rep_totals["Rate (%)"]     = rep_totals.apply(lambda r: incentive_rate(r["Rep"], r["Type"]), axis=1)
    rep_totals["Incentive (₹)"] = rep_totals["Collections"] * rep_totals["Rate (%)"] / 100

    # Summary
    mc1, mc2, mc3 = st.columns(3)
    mc1.metric("Total Collections",    f"₹{rep_totals['Collections'].sum():,.0f}")
    mc2.metric("Total Incentive Payout", f"₹{rep_totals['Incentive (₹)'].sum():,.0f}")
    mc3.metric("Default AM% / CSM%",   f"{am_pct}% / {csm_pct}%")

    # Table
    st.subheader("Breakdown by Rep")
    display = rep_totals.copy()
    display["Collections"]   = display["Collections"].apply(lambda x: f"₹{x:,.0f}")
    display["Incentive (₹)"] = display["Incentive (₹)"].apply(lambda x: f"₹{x:,.0f}")
    display["Rate (%)"]      = display["Rate (%)"].apply(lambda x: f"{x}%")
    st.dataframe(display, use_container_width=True, hide_index=True)

    # Chart
    fig = px.bar(
        rep_totals, x="Rep", y="Incentive (₹)", color="Type",
        title="Incentive Payout by Rep",
        color_discrete_map={"AM": "#1f77b4", "CSM": "#ff7f0e"},
        text=rep_totals["Incentive (₹)"].apply(lambda x: f"₹{x:,.0f}"),
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, use_container_width=True)


# ─── Settings ─────────────────────────────────────────────────────────────────
def page_settings():
    st.title("Settings")
    settings = load_settings()

    # Incentive rates
    st.subheader("Default Incentive Rates")
    sc1, sc2 = st.columns(2)
    am_pct  = sc1.number_input("AM Incentive %",  value=float(settings.get("am_pct",  5.0)), min_value=0.0, max_value=100.0, step=0.5)
    csm_pct = sc2.number_input("CSM Incentive %", value=float(settings.get("csm_pct", 3.0)), min_value=0.0, max_value=100.0, step=0.5)
    if st.button("Save Rates", type="primary"):
        settings["am_pct"]  = am_pct
        settings["csm_pct"] = csm_pct
        save_settings(settings)
        st.success("Rates saved!")

    st.divider()

    # Existing reps
    st.subheader("Reps")
    reps = settings.get("reps", [])
    if reps:
        rep_df = pd.DataFrame(reps)
        st.dataframe(
            rep_df.rename(columns={"name": "Name", "type": "Type", "custom_pct": "Custom Rate (%)"}),
            use_container_width=True, hide_index=True,
        )
        to_delete = st.selectbox("Remove rep", [""] + [r["name"] for r in reps])
        if to_delete and st.button("Delete Rep", type="secondary"):
            settings["reps"] = [r for r in reps if r["name"] != to_delete]
            save_settings(settings)
            st.success(f"Removed {to_delete}")
            st.rerun()
    else:
        st.info("No reps added yet.")

    st.divider()

    # Add rep
    st.subheader("Add Rep")
    with st.form("add_rep_form"):
        new_name    = st.text_input("Name")
        new_type    = st.selectbox("Type", ["AM", "CSM"])
        use_custom  = st.checkbox("Override incentive rate for this rep")
        custom_pct  = st.number_input(
            "Custom Rate (%)", min_value=0.0, max_value=100.0,
            value=settings.get("am_pct", 5.0), step=0.5,
        )

        if st.form_submit_button("Add Rep", type="primary"):
            if not new_name:
                st.error("Name is required.")
            elif any(r["name"].lower() == new_name.lower() for r in reps):
                st.error("A rep with this name already exists.")
            else:
                new_rep = {"name": new_name, "type": new_type}
                if use_custom:
                    new_rep["custom_pct"] = custom_pct
                settings.setdefault("reps", []).append(new_rep)
                save_settings(settings)
                st.success(f"Added {new_name} ({new_type})")
                st.rerun()


# ─── App entry ────────────────────────────────────────────────────────────────
def main():
    st.set_page_config(
        page_title="Sales Forecasting & Incentive Tool",
        page_icon="📈",
        layout="wide",
    )

    pages = {
        "Dashboard":      page_dashboard,
        "Opportunities":  page_opportunities,
        "Collections":    page_collections,
        "Incentives":     page_incentives,
        "Settings":       page_settings,
    }

    with st.sidebar:
        st.markdown("## 📈 Sales Tool")
        st.divider()
        selection = st.radio("", list(pages.keys()), label_visibility="collapsed")

    pages[selection]()


if __name__ == "__main__":
    main()
