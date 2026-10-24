"""Bank Loan Calculator Dashboard  |  run:  streamlit run app.py"""
from datetime import date
from decimal import ROUND_HALF_UP, ROUND_HALF_EVEN
from itertools import accumulate

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from bank_calc import (CalcSettings, build_schedule, normalize_cash_flows,
                       pmt, reconcile, xirr, xnpv)

st.set_page_config(page_title="Bank Loan Calculator", page_icon="🏦", layout="wide")
BLUE, GREEN, ORANGE = "#2563eb", "#16a34a", "#ea580c"

# ---------------- Sidebar: calculator settings + loan inputs ----------------
with st.sidebar:
    st.header("Loan inputs")
    P = st.number_input("Loan amount", 1_000, 100_000_000, 1_000_000, 10_000)
    rate = st.number_input("Annual rate (%)", 0.0, 60.0, 12.0, 0.25) / 100
    n = st.number_input("Term (months)", 2, 360, 36, 1)

    st.subheader("Prepayments")
    c1, c2 = st.columns(2)
    m1 = c1.number_input("Month", 0, 359, 6, key="m1")
    a1 = c2.number_input("Amount", 0, 100_000_000, 100_000, 5_000, key="a1")
    m2 = c1.number_input("Month ", 0, 359, 12, key="m2")
    a2 = c2.number_input("Amount ", 0, 100_000_000, 50_000, 5_000, key="a2")
    mode = st.radio("After prepayment", ["shorten_term", "reduce_payment"],
                    format_func=lambda x: x.replace("_", " ").title())

    st.header("Calculator settings")
    rounding = st.selectbox("Rounding", ["Half-up", "Banker's (half-even)"])
    day_count = st.selectbox("Day count", ["ACT/365", "ACT/360", "30/360"])
    places = st.selectbox("Decimals", [2, 0, 3], index=0)

s = CalcSettings(places=places,
                 rounding=ROUND_HALF_UP if rounding == "Half-up" else ROUND_HALF_EVEN,
                 day_count=day_count)

# ---------------- Calculations ----------------
reductions = {}
for m, a in ((m1, a1), (m2, a2)):
    if 1 <= m < n and a > 0:
        reductions[int(m)] = reductions.get(int(m), 0) + a

base = build_schedule(P, rate, int(n), s)
red = build_schedule(P, rate, int(n), s, reductions=reductions, mode=mode)
rec = reconcile(base, red, P, s)
fl = lambda rows, k: [float(r[k]) for r in rows]

st.title("🏦 Bank Loan Calculator Dashboard")
st.caption("Decimal-based calculations, configurable rounding & day count, prepayment reconciliation and XIRR.")

k = st.columns(5)
k[0].metric("Monthly payment", f"{pmt(P, rate, int(n), s):,.2f}")
k[1].metric("Total interest (base)", f"{sum(r['interest'] for r in base):,.2f}")
k[2].metric("Interest saved", f"{rec['interest_saved']:,.2f}")
k[3].metric("Months saved", rec["periods_saved"])
k[4].metric("Final payment", f"{red[-1]['payment']:,.2f}")

# ---------------- Charts ----------------
def style(fig, title):
    fig.update_layout(title=title, height=360, margin=dict(l=10, r=10, t=50, b=10),
                      legend=dict(orientation="h", y=-0.2), hovermode="x unified")
    return fig

left, right = st.columns(2)

f1 = go.Figure()
f1.add_scatter(x=[0] + [r["period"] for r in base], y=[float(P)] + fl(base, "balance"),
               name="Base", line=dict(color=BLUE, width=3))
f1.add_scatter(x=[0] + [r["period"] for r in red], y=[float(P)] + fl(red, "balance"),
               name="With prepayments", line=dict(color=GREEN, width=3))
left.plotly_chart(style(f1, "Outstanding balance"), width="stretch")

f2 = go.Figure()
x = [r["period"] for r in red]
f2.add_bar(x=x, y=fl(red, "interest"), name="Interest", marker_color=ORANGE)
f2.add_bar(x=x, y=fl(red, "principal"), name="Principal", marker_color=BLUE)
f2.add_bar(x=x, y=fl(red, "extra"), name="Prepayment", marker_color=GREEN)
f2.update_layout(barmode="stack")
right.plotly_chart(style(f2, "Monthly payment split"), width="stretch")

left2, right2 = st.columns(2)
cb, cr = list(accumulate(fl(base, "interest"))), list(accumulate(fl(red, "interest")))
f3 = go.Figure()
f3.add_scatter(x=list(range(1, len(cb) + 1)), y=cb, name="Base", line=dict(color=BLUE, width=3))
f3.add_scatter(x=list(range(1, len(cr) + 1)), y=cr, name="With prepayments",
               line=dict(color=GREEN, width=3), fill="tonexty", fillcolor="rgba(22,163,74,.12)")
left2.plotly_chart(style(f3, "Cumulative interest paid"), width="stretch")

# ---------------- XIRR ----------------
right2.subheader("XIRR cash flows")
df = pd.DataFrame({"date": [date(2026, 1, 1), date(2026, 7, 1), date(2026, 7, 1), date(2027, 1, 1)],
                   "amount": [-1_000_000.0, 400_000.0, 100_000.0, 650_000.0]})
edited = right2.data_editor(df, num_rows="dynamic", width="stretch", hide_index=True)

irr = None
try:
    rows = [(r.date, r.amount) for r in edited.dropna().itertuples()]
    flows = normalize_cash_flows(rows, s)
    irr = xirr(flows, s)
    right2.metric("XIRR", f"{irr * 100:.2f}% p.a.")
    rs = [i / 100 for i in range(0, 61)]
    f4 = go.Figure()
    f4.add_scatter(x=[r * 100 for r in rs], y=[xnpv(r, flows, s) for r in rs],
                   name="NPV", line=dict(color=BLUE, width=3))
    f4.add_scatter(x=[irr * 100], y=[0], mode="markers", name="XIRR",
                   marker=dict(color=ORANGE, size=11))
    f4.update_xaxes(title="Annual rate (%)")
    st.plotly_chart(style(f4, "NPV vs discount rate"), width="stretch")
except Exception as e:
    right2.warning(f"XIRR not available: {e}")

# ---------------- Schedule table + download ----------------
st.subheader("Amortization schedule (with prepayments)")
table = pd.DataFrame(red).astype(float)
st.dataframe(table, width="stretch", hide_index=True)
st.download_button("Download schedule (CSV)", table.to_csv(index=False), "schedule.csv", "text/csv")