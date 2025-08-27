import streamlit as st
import pandas as pd
import math
from datetime import datetime, date, time, timedelta
from dateutil.relativedelta import relativedelta
from collections import defaultdict

# ------------------ Basisconfig ------------------
st.set_page_config(page_title="SKC • Shift Kalender Calculator", page_icon="🗓️", layout="wide")

# ------------------ Thema / CSS ------------------
st.markdown("""
<style>
:root{
  --bg:#ffffff;
  --panel: rgba(240,242,246,0.7);
  --ink:#111111;
  --muted:#666;
  --accent:#ffd84d;
  --redbg:#fde8e8;
  --bluebg:#e8f0ff;
  --greenbg:#e6f6ee;
  --purplebg:#f1e6fa;
  --tableHeader:#f3f5f9;
  --border:#e1e5ef;
}

.stApp, .stApp header, .block-container { background-color: var(--bg) !important; color: var(--ink) !important; }
[data-testid="stHeader"] { background-color: var(--bg) !important; }
h1,h2,h3,h4 { color: var(--ink) !important; }

.skc-logo { 
  font-size:64px; font-weight:900; letter-spacing:2px; line-height:0.9;
  color:#d80000; -webkit-text-stroke: 2px #ffffff; text-shadow: 0 0 1px #fff; margin:0;
}
.skc-sub { 
  font-size: 12px; text-align:center; margin-top:2px; 
  color:#111; opacity:.85; font-weight:500; white-space:nowrap; display:block;
}
.skc-band{height:4px;background:var(--accent);margin:10px 0 16px;border-radius:2px;}

.panel{ background: var(--panel); border: 1px solid var(--border); border-radius: 14px; padding: 12px 14px; backdrop-filter: blur(2px); }
.grid2{ display:grid; grid-template-columns: 1.2fr 1fr; gap: 16px; }
.grid3{ display:grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; }
.grid1{ display:grid; grid-template-columns: 1fr; gap: 14px; }
@media (max-width: 980px){
  .grid2, .grid3{ grid-template-columns: 1fr; }
}

.controls{ display: flex; align-items:center; gap:8px; flex-wrap:wrap; }
.controls .stButton>button, .controls .stDownloadButton>button { padding:6px 10px; border-radius:10px; }
.controls .stSelectbox, .controls .stNumberInput { min-width: 140px; }

thead tr th { background: var(--tableHeader) !important; color:#111 !important; border-bottom:1px solid var(--border) !important; }
[data-testid="stDataFrame"] div[role="gridcell"],
[data-testid="stDataFrame"] th, 
[data-testid="stDataFrame"] td { background: #fff !important; color:#111 !important; border-color: var(--border) !important; }
[data-testid="stDataFrame"] thead tr th > div { background: var(--tableHeader) !important; }

.small-note { color: var(--muted); font-size:12px; }

.weekwrap{ position: relative; }
.weeknr{ position:absolute; right:8px; top:8px; font-size:12px; color:var(--muted); }

.card-row{ display:flex; gap:12px; flex-wrap:wrap; margin:8px 0; }
.card{ background:#fff; border:1px solid var(--border); border-radius: 10px; padding:10px 12px; }
.card strong{ display:block; font-size: 18px; }

@media print {
  .no-print { display:none !important; }
  .print-only { display:block !important; }
  body, .stApp, .block-container { background:#fff !important; color:#111 !important; }
  .skc-logo{ color:#d80000; -webkit-text-stroke:1px #fff; }
  .skc-sub{ color:#000; }
}
.print-only { display:none; }
</style>
""", unsafe_allow_html=True)

# ------------------ Kleuren ------------------
COLORS = {
    "bg_shift":   "#fde8e8",
    "bg_bijs":    "#e8f0ff",
    "bg_free":    "#e6f6ee",
    "bg_night":   "#f1e6fa",
    "text":       "#111111",
}

# ------------------ Helpers ------------------
DUTCH_DAYNAMES = {0:"maandag",1:"dinsdag",2:"woensdag",3:"donderdag",4:"vrijdag",5:"zaterdag",6:"zondag"}
MONTH_NL = {
    1:"januari",2:"februari",3:"maart",4:"april",5:"mei",6:"juni",
    7:"juli",8:"augustus",9:"september",10:"oktober",11:"november",12:"december"
}

def fmt_dutch_range(dmin, dmax):
    dmin = dmin.date() if isinstance(dmin, pd.Timestamp) else dmin
    dmax = dmax.date() if isinstance(dmax, pd.Timestamp) else dmax
    if dmin.month == dmax.month:
        return f"{dmin.day}–{dmax.day} {MONTH_NL[dmin.month]}"
    return f"{dmin.day} {MONTH_NL[dmin.month]} – {dmax.day} {MONTH_NL[dmax.month]}"

def parse_hhmm(s: str) -> time:
    if not s: return None
    h,m = s.split(":")
    return time(int(h), int(m))

def hours_between(start: time, end: time) -> float:
    dt0 = datetime.combine(date.today(), start)
    dt1 = datetime.combine(date.today(), end)
    if dt1 <= dt0:
        dt1 += timedelta(days=1)
    return (dt1 - dt0).total_seconds()/3600.0

def ceil_to_min(hours: float) -> float:
    if hours is None: return 0.0
    return math.ceil(hours * 60.0) / 60.0

def month_dates(year: int, month: int):
    d0 = date(year, month, 1)
    d1 = d0 + relativedelta(months=1)
    d = d0
    while d < d1:
        yield d
        d += timedelta(days=1)

def fmt_date(d, fmt="%d-%m-%Y") -> str:
    if isinstance(d, pd.Timestamp): d = d.date()
    return d.strftime(fmt)

def month_key(y: int, m: int) -> str:
    return f"{y}-{m:02d}"

def normalize_codes(s: str) -> str:
    if not s: return ""
    s = s.strip().lower().replace(" ", "").replace(",", "+")
    while "++" in s:
        s = s.replace("++", "+")
    return s.strip("+")

def split_codes(s: str):
    s = normalize_codes(s)
    return [c for c in s.split("+") if c] if s else []

def ensure_session():
    if "shiftcodes" not in st.session_state:
        st.session_state.shiftcodes = {
            "bijs":   {"start": None, "end": None, "pauze": 0, "label": "Bijscholing (uren invullen)"},
            "fdrecup":{"start": None, "end": None, "pauze": 0, "label": "Betaalde feestdag (0u)"},
        }
    if "months" not in st.session_state: st.session_state.months = {}
    if "calc" not in st.session_state: st.session_state.calc = {}
    if "nav" not in st.session_state: st.session_state.nav = {}
ensure_session()

# ------------------ Header ------------------
hc1, hc2 = st.columns([5,2])
with hc1:
    st.markdown('<div class="skc-logo">SKC</div>', unsafe_allow_html=True)
    st.markdown('<span class="skc-sub">Shift Kalender Calculator</span>', unsafe_allow_html=True)
with hc2:
    st.write(""); st.write("")
    st.button("🖨️ Afdrukken", help="Print deze maand", on_click=lambda: st.markdown("<script>window.print()</script>", unsafe_allow_html=True))
st.markdown('<div class="skc-band"></div>', unsafe_allow_html=True)

# ------------------ Maandkiezer ------------------
today = date.today()
c_prev, c_today, c_next, c_year, c_month, c_ok = st.columns([1,1,1,2,2,2])
year  = c_year.number_input("Jaar", min_value=2000, max_value=2100, value=st.session_state.nav.get("year", today.year), step=1)
month = c_month.selectbox("Maand", list(range(1,13)), index=(st.session_state.nav.get("month", today.month)-1),
                          format_func=lambda m: ["","jan","feb","mrt","apr","mei","jun","jul","aug","sep","okt","nov","dec"][m])
if c_prev.button("← Vorige"):
    d = date(int(year), int(month), 1) - relativedelta(months=1); year, month = d.year, d.month
if c_today.button("Vandaag"):
    year, month = today.year, today.month
if c_next.button("Volgende →"):
    d = date(int(year), int(month), 1) + relativedelta(months=1); year, month = d.year, d.month
st.session_state.nav["year"] = int(year)
st.session_state.nav["month"] = int(month)
mkey = month_key(int(year), int(month))

# ------------------ Init maanddata ------------------
def init_month_df(y: int, m: int) -> pd.DataFrame:
    rows = []
    for d in month_dates(y, m):
        rows.append({
            "Datum": pd.to_datetime(d),
            "DagNr": d.weekday(),
            "Dag": DUTCH_DAYNAMES[d.weekday()],
            "Codes": "",
            "BIJSuren": 0.0,
            "OverurenMin": 0,
        })
    return pd.DataFrame(rows)

if mkey not in st.session_state.months:
    st.session_state.months[mkey] = init_month_df(int(year), int(month))
df = st.session_state.months[mkey].copy()

# ------------------ BIJS + Legende ------------------
colL, colR = st.columns([1,1])
with colL:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### 📘 BIJS (bijscholing)")
    bijs_mask = df["Codes"].astype(str).str.contains("bijs", case=False, na=False)
    if bijs_mask.any():
        subset = df.loc[bijs_mask].sort_values("Datum").copy()
        for i, row in subset.iterrows():
            label = f"{row['Dag']} {fmt_date(row['Datum'])}"
            new_val = st.number_input(f"Uren {label}", min_value=0.0, max_value=24.0, step=0.25,
                                      value=float(df.at[i,"BIJSuren"]), key=f"bijs_{mkey}_{i}")
            df.at[i,"BIJSuren"] = new_val
    else:
        st.caption("Geen BIJS-dagen in deze maand.")
    st.markdown("</div>", unsafe_allow_html=True)

with colR:
    st.markdown('<div class="panel">', unsafe_allow_html=True)
    st.markdown("### 📖 Legende")
    leg_rows = []
    for code, info in sorted(st.session_state.shiftcodes.items()):
        tijd = f"{info['start']}–{info['end']}" if info["start"] and info["end"] else "variabel"
        if code == "n10": kleur, kbg = "Paars", COLORS["bg_night"]
        elif code == "bijs": kleur, kbg = "Blauw", COLORS["bg_bijs"]
        elif code == "fdrecup": kleur, kbg = "Groen", COLORS["bg_free"]
        else: kleur, kbg = "Rood", COLORS["bg_shift"]
        leg_rows.append({"Code": code, "Betekenis": info["label"], "Tijd": tijd, "Kleur": kleur})
    if leg_rows:
        st.dataframe(pd.DataFrame(leg_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Nog geen codes ingesteld.")
    st.markdown("</div>", unsafe_allow_html=True)

# ------------------ Week-editor ------------------
iso = df["Datum"].dt.isocalendar()
df["Week"] = iso.week.astype(int); df["Jaar"] = iso.year.astype(int)
week_groups = list(df.sort_values("Datum").groupby(["Jaar","Week"]))
for (jaar, week), groep in week_groups:
    edit = groep[["Datum","Dag","Codes","OverurenMin"]].copy()
    edit["Datum"] = edit["Datum"].dt.strftime("%d-%m-%Y")
    st.markdown(f"**Week {week} • {edit['Datum'].iloc[0]} – {edit['Datum'].iloc[-1]}**")
    edited = st.data_editor(
        edit, num_rows="fixed", hide_index=True, use_container_width=True,
        key=f"edit_{mkey}_{jaar}_{week}",
        column_config={
            "Codes": st.column_config.Column("Codes"),
            "OverurenMin": st.column_config.NumberColumn("Overuren (minuten)", min_value=0, step=5)
        }
    )
    edited2 = edited.copy()
    edited2["Datum"] = pd.to_datetime(edited2["Datum"], format="%d-%m-%Y")
    for _, r in edited2.iterrows():
        idx = df.index[(df["Datum"]==r["Datum"]) & (df["Dag"]==r["Dag"])]
        if len(idx):
            df.at[idx[0], "Codes"] = normalize_codes(r["Codes"])
            df.at[idx[0], "OverurenMin"] = int(r["OverurenMin"] or 0)

# ------------------ Berekening ------------------
def calc_shift_hours_for_code(code: str) -> float:
    if code == "bijs": return 0.0
    info = st.session_state.shiftcodes.get(code)
    if not info: return 0.0
    s, e, p = info["start"], info["end"], info["pauze"]
    if not s and not e: return 0.0
    bruto = hours_between(parse_hhmm(s), parse_hhmm(e))
    netto = max(0.0, bruto - (p/60.0))
    return ceil_to_min(netto)

def calc_row_hours(codes_str: str) -> float:
    return ceil_to_min(sum(calc_shift_hours_for_code(c) for c in split_codes(codes_str)))

def recompute(df_in: pd.DataFrame) -> pd.DataFrame:
    out = df_in.copy()
    out["Codes"] = out["Codes"].astype(str).apply(normalize_codes)
    out["ShiftUren"] = out["Codes"].apply(calc_row_hours)
    out["BIJSuren"] = out["BIJSuren"].apply(lambda x: ceil_to_min(float(x)))
    out["OverurenUur"] = out["OverurenMin"].apply(lambda m: ceil_to_min(float(m)/60.0))
    out["TotaalUren"] = (out["ShiftUren"]+out["BIJSuren"]+out["OverurenUur"]).round(2)
    return out

if st.button("✅ Bereken / Update totalen", key=f"recalc_{mkey}") or mkey not in st.session_state.calc:
    st.session_state.months[mkey] = df.copy()
    st.session_state.calc[mkey] = recompute(df)

calc_df = st.session_state.calc.get(mkey, recompute(df)).copy()

# ------------------ Week weergave ------------------
def row_style(row):
    codes = split_codes(row["Codes"])
    if "n10" in codes: bg = COLORS["bg_night"]
    elif float(row["TotaalUren"]) == 0.0: bg = COLORS["bg_free"]
    else: bg = COLORS["bg_shift"]
    return [f"background-color:{bg}; color:{COLORS['text']}"]*len(row)

for (jaar, week), groep in calc_df.sort_values("Datum").groupby(["Jaar","Week"]):
    dmin, dmax = groep["Datum"].min(), groep["Datum"].max()
    totaal_week = groep["TotaalUren"].sum(); gewerkt = int((groep["TotaalUren"]>0).sum()); vrij = len(groep)-gewerkt
    st.markdown(f'<div class="weekwrap"><div class="weeknr">Week {week}</div><h4>{fmt_dutch_range(dmin,dmax)}</h4></div>', unsafe_allow_html=True)
    c1,c2,c3 = st.columns(3)
    c1.markdown(f'<div class="card"><span class="small-note">Totaal</span><strong>{totaal_week:.2f} u</strong></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="card"><span class="small-note">Gewerkt</span><strong>{gewerkt} d.</strong></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="card"><span class="small-note">Vrij</span><strong>{vrij} d.</strong></div>', unsafe_allow_html=True)
    blok = groep.copy(); blok["Datum"] = blok["Datum"].dt.strftime("%d-%m-%Y")
    blok = blok[["Datum","Dag","Codes","ShiftUren","OverurenUur","TotaalUren"]]
    st.dataframe(blok.style.apply(row_style, axis=1), use_container_width=True, hide_index=True)

# ------------------ Samenvatting ------------------
c1,c2,c3 = st.columns(3)
c1.markdown(f'<div class="card"><span class="
