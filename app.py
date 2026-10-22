from __future__ import annotations

import io
import math
import re
from datetime import date
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
import streamlit as st
import sympy as sp
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, Table, TableStyle

APP_TITLE = "Hispanic Heritage Historical Data Explorer"
WORLD_BANK = "https://api.worldbank.org/v2"
COUNTRIES = {
    "Mexico (MX)": "MEX", "Brazil (BR)": "BRA", "Argentina (AR)": "ARG",
    "Colombia (CO)": "COL", "Chile (CL)": "CHL", "Peru (PE)": "PER",
    "Venezuela (VE)": "VEN", "Ecuador (EC)": "ECU", "Uruguay (UY)": "URY",
}
INDICATORS = {
    "Life expectancy at birth": ("SP.DYN.LE00.IN", "years", "Average number of years a newborn would live if current mortality patterns persisted."),
    "Unemployment, national estimate": ("SL.UEM.TOTL.NE.ZS", "% of labor force", "Share of the labor force without work but available for and seeking employment, using national estimates."),
    "GDP per capita (current US$)": ("NY.GDP.PCAP.CD", "current US dollars per person", "Gross domestic product divided by midyear population, in current US dollars; not average wealth or household income."),
    "Crude birth rate": ("SP.DYN.CBRT.IN", "births per 1,000 people per year", "Annual live births per 1,000 people; this is a rate, not a birth count."),
    "Net migration": ("SM.POP.NETM", "people over the period", "Number of immigrants minus emigrants over the period; not an emigration count."),
    "Intentional homicide rate": ("VC.IHR.PSRC.P5", "per 100,000 people", "Intentional homicides per 100,000 people."),
    "Consumer price inflation": ("FP.CPI.TOTL.ZG", "% annual change", "Annual percentage change in the consumer price index."),
    "Central government debt": ("GC.DOD.TOTL.GD.ZS", "% of GDP", "Central government debt as a share of GDP."),
    "Total reserves including gold": ("FI.RES.TOTL.CD", "current US dollars", "Total reserves including gold, valued in current US dollars."),
    "External balance on goods and services": ("NE.RSB.GNFS.ZS", "% of GDP", "External balance on goods and services as a share of GDP."),
}
CONTEXTS = {
    "Business": ("Revenue", "dollars", "Time", "days", "Exponential growth/decay: y = a*exp(k*x)", "Revenue or activity may grow or decline over time; parameters are illustrative unless fitted to data."),
    "Engineering": ("Displacement", "meters", "Time", "seconds", "Quadratic: y = a*x**2 + b*x + c", "Displacement can be modeled by a polynomial over a limited interval."),
    "Medical": ("Concentration", "mg/L", "Time", "hours", "Exponential decay: y = a*exp(-k*x)", "A simplified concentration curve; not medical advice or a dosing model."),
    "Sports science": ("Position", "meters", "Time", "seconds", "Quadratic: y = a*x**2 + b*x + c", "Position changes over time; its derivatives represent velocity and acceleration."),
    "Biology": ("Population", "organisms", "Time", "days", "Logistic-like alternative: use a polynomial or exponential approximation", "Population models are approximations and may not capture resource limits."),
    "Bioengineering": ("Signal", "arbitrary units", "Time", "seconds", "Trigonometric: y = a*sin(b*x) + c", "A periodic signal can be approximated by a trigonometric function."),
    "Economic forecasting": ("GDP per capita", "current US$/person", "Year", "year", "Use the World Bank polynomial fit", "Historical GDP per capita is not household income or average wealth."),
    "Weather": ("Temperature", "°C", "Time", "hours", "Trigonometric: y = a*sin(b*x) + c", "Periodic functions can approximate cycles but do not produce reliable weather forecasts."),
    "Custom": ("Dependent variable", "units", "Independent variable", "units", "Enter a function below", "Describe your own context and model assumptions."),
}
st.set_page_config(page_title=APP_TITLE, layout="wide")

# Appearance customization: presentation-only controls; does not change data or calculations.
st.sidebar.header("Website appearance")
font_choice = st.sidebar.selectbox(
    "Choose a font",
    ["Inter (modern)", "Poppins (rounded)", "Lora (editorial serif)", "Merriweather (classic serif)", "Roboto Mono (technical)", "System default"],
    index=0,
    key="appearance_font",
)
background_choice = st.sidebar.selectbox(
    "Choose a background",
    ["Clean light", "Midnight blue", "Warm paper", "Ocean mist", "Lavender", "Forest"],
    index=0,
    key="appearance_background",
)
font_settings = {
    "Inter (modern)": ("Inter", "'Inter', Arial, sans-serif", "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"),
    "Poppins (rounded)": ("Poppins", "'Poppins', Arial, sans-serif", "https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap"),
    "Lora (editorial serif)": ("Lora", "'Lora', Georgia, serif", "https://fonts.googleapis.com/css2?family=Lora:wght@400;500;600;700&display=swap"),
    "Merriweather (classic serif)": ("Merriweather", "'Merriweather', Georgia, serif", "https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&display=swap"),
    "Roboto Mono (technical)": ("Roboto Mono", "'Roboto Mono', monospace", "https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;500;600;700&display=swap"),
    "System default": ("System", "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif", ""),
}
background_settings = {
    "Clean light": {"page": "#F7F9FC", "panel": "#FFFFFF", "text": "#172033", "muted": "#526078", "border": "#DCE3ED", "accent": "#2563EB"},
    "Midnight blue": {"page": "#101827", "panel": "#182438", "text": "#F0F5FF", "muted": "#B7C4D8", "border": "#34445D", "accent": "#7CB8FF"},
    "Warm paper": {"page": "#F5EFE4", "panel": "#FFFAF1", "text": "#382F27", "muted": "#74675A", "border": "#DED0BC", "accent": "#9A5B35"},
    "Ocean mist": {"page": "#EAF5F6", "panel": "#F8FFFF", "text": "#15363C", "muted": "#4C6D73", "border": "#C6E0E3", "accent": "#087E8B"},
    "Lavender": {"page": "#F3EFFB", "panel": "#FCFAFF", "text": "#302748", "muted": "#716487", "border": "#DDD2F0", "accent": "#7954A1"},
    "Forest": {"page": "#EEF4EC", "panel": "#FAFFF8", "text": "#243B2A", "muted": "#5B715F", "border": "#D0DFD0", "accent": "#36734A"},
}
font_name, font_stack, font_url = font_settings[font_choice]
palette = background_settings[background_choice]
font_import = f"@import url('{font_url}');" if font_url else ""
st.markdown(
    f"""<style>
    {font_import}
    :root {{
      --explorer-page: {palette['page']};
      --explorer-panel: {palette['panel']};
      --explorer-text: {palette['text']};
      --explorer-muted: {palette['muted']};
      --explorer-border: {palette['border']};
      --explorer-accent: {palette['accent']};
      --explorer-font: {font_stack};
    }}
    html, body, [class*="st-"] {{ font-family: var(--explorer-font) !important; }}
    .stApp {{ background: var(--explorer-page); color: var(--explorer-text); }}
    [data-testid="stHeader"] {{ background: transparent; }}
    [data-testid="stSidebar"] {{ background: var(--explorer-panel); border-right: 1px solid var(--explorer-border); }}
    [data-testid="stVerticalBlockBorderWrapper"] > div {{ border-color: var(--explorer-border); }}
    [data-testid="stMetric"] {{ background: var(--explorer-panel); border: 1px solid var(--explorer-border); padding: .8rem; border-radius: .75rem; }}
    [data-testid="stMarkdownContainer"] p, [data-testid="stCaptionContainer"] {{ color: var(--explorer-text); }}
    [data-testid="stCaptionContainer"] {{ color: var(--explorer-muted); }}
    div.stButton > button, div.stDownloadButton > button {{ border-radius: .65rem; border-color: var(--explorer-accent); }}
    div.stButton > button:hover, div.stDownloadButton > button:hover {{ border-color: var(--explorer-accent); color: var(--explorer-accent); }}
    [data-baseweb="input"] > div, [data-baseweb="select"] > div, [data-baseweb="textarea"] > div {{ background: var(--explorer-panel); border-color: var(--explorer-border); }}
    </style>""",
    unsafe_allow_html=True,
)
st.title(APP_TITLE)
st.caption("A student research and function-analysis lab. Historical API observations and illustrative simulations are clearly separated.")
st.sidebar.caption(f"Current style: {font_name} · {background_choice}")

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_world_bank(country_code: str, indicator_code: str, start_year: int, end_year: int):
    url = f"{WORLD_BANK}/country/{country_code}/indicator/{indicator_code}"
    params = {"date": f"{start_year}:{end_year}", "format": "json", "per_page": 20000}
    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
            return pd.DataFrame(columns=["year", "value"]), f"Unexpected API response: {payload[0] if isinstance(payload, list) and payload else 'empty response'}"
        rows = [{"year": int(item["date"]), "value": item["value"]} for item in payload[1] if item.get("date") and item.get("value") is not None]
        df = pd.DataFrame(rows, columns=["year", "value"])
        if not df.empty:
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.dropna().sort_values("year").drop_duplicates("year").reset_index(drop=True)
        return df, None if not df.empty else "The API returned no non-null observations for this period."
    except requests.Timeout:
        return pd.DataFrame(columns=["year", "value"]), "The World Bank API timed out. Try again later."
    except requests.RequestException as exc:
        return pd.DataFrame(columns=["year", "value"]), f"Network/API request failed: {exc}"
    except (ValueError, TypeError, KeyError) as exc:
        return pd.DataFrame(columns=["year", "value"]), f"Could not parse API response: {exc}"

def fit_poly(df: pd.DataFrame, degree: int):
    clean = df[["year", "value"]].copy()
    clean["year"] = pd.to_numeric(clean["year"], errors="coerce")
    clean["value"] = pd.to_numeric(clean["value"], errors="coerce")
    clean = clean.dropna().sort_values("year")
    clean = clean[clean["year"] % 1 == 0]
    clean = clean.drop_duplicates("year")
    if len(clean) < degree + 1 or clean["year"].nunique() < degree + 1:
        raise ValueError(f"Degree {degree} requires at least {degree + 1} distinct valid years; current data has {clean['year'].nunique()}.")
    base_year = int(clean["year"].min())
    t = clean["year"].to_numpy(dtype=float) - base_year
    y = clean["value"].to_numpy(dtype=float)
    coeff = np.polyfit(t, y, degree)
    pred = np.polyval(coeff, t)
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = float(1 - np.sum((y - pred) ** 2) / ss_tot) if ss_tot else float("nan")
    mae = float(np.mean(np.abs(y - pred)))
    residuals = clean.assign(fitted=pred, residual=y-pred, abs_residual=np.abs(y-pred))
    return coeff, base_year, clean, pred, r2, mae, residuals

def poly_equation(coeff, base_year):
    terms=[]
    degree=len(coeff)-1
    for i,c in enumerate(coeff):
        power=degree-i
        if abs(c) < 1e-14: continue
        if power == 0: term=f"{c:.10g}"
        elif power == 1: term=f"{c:.10g}·t"
        else: term=f"{c:.10g}·t^{power}"
        terms.append(term)
    return "y = " + (" + ".join(terms).replace("+ -", "- ") if terms else "0") + f", where t = year − {base_year}"

def safe_expression(expr_text: str, x_symbol):
    """Parse a restricted mathematical expression; never use eval()."""
    normalized = expr_text.replace("^", "**")
    local = {"x": x_symbol, "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
             "exp": sp.exp, "log": sp.log, "ln": sp.log, "sqrt": sp.sqrt,
             "abs": sp.Abs, "pi": sp.pi, "E": sp.E}
    try:
        expr = sp.sympify(normalized, locals=local, evaluate=True)
        if expr.free_symbols - {x_symbol}:
            raise ValueError("Use x as the only variable.")
        if expr.has(sp.zoo, sp.nan, sp.oo, -sp.oo):
            raise ValueError("Expression contains an undefined/infinite constant.")
        return expr
    except Exception as exc:
        raise ValueError(f"Could not parse function. Use x, +, -, *, /, **, parentheses, and sin/cos/tan/exp/log/sqrt. Details: {exc}")

def evaluate_expr(expr, x_symbol, xs):
    fn = sp.lambdify(x_symbol, expr, modules=["numpy"])
    with np.errstate(all="ignore"):
        ys = np.asarray(fn(xs), dtype=float)
    if ys.ndim == 0:
        ys = np.full_like(np.asarray(xs, dtype=float), float(ys))
    return np.where(np.isfinite(ys), ys, np.nan)

def fig_to_png(fig):
    out=io.BytesIO()
    fig.savefig(out, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    out.seek(0)
    return out

def csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8")

def make_excel(summary, working, results, residuals):
    out=io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        pd.DataFrame([summary]).to_excel(writer, sheet_name="Summary", index=False)
        working.to_excel(writer, sheet_name="Working data", index=False)
        results.to_excel(writer, sheet_name="Calculated years", index=False)
        residuals.to_excel(writer, sheet_name="Residuals", index=False)
        for sheet in writer.sheets.values():
            sheet.freeze_panes(1,0)
            sheet.set_column(0, 10, 18)
    return out.getvalue()

def make_pdf(summary, working, results, chart_png, findings):
    out=io.BytesIO()
    doc=SimpleDocTemplate(out, pagesize=landscape(letter), rightMargin=28,leftMargin=28,topMargin=28,bottomMargin=28)
    styles=getSampleStyleSheet()
    story=[Paragraph(APP_TITLE, styles["Title"]), Paragraph("Generated: "+date.today().isoformat(),styles["Normal"]),Spacer(1,8)]
    for k,v in summary.items():
        story.append(Paragraph(f"<b>{str(k).replace('&','&amp;')}</b>: {str(v).replace('&','&amp;')}",styles["BodyText"]))
    story += [Spacer(1,8), Paragraph("Findings and limitations",styles["Heading2"])]
    for line in findings:
        story.append(Paragraph(str(line).replace("&","&amp;"),styles["BodyText"]))
    story += [Spacer(1,8), Paragraph("Model chart",styles["Heading2"]), RLImage(chart_png, width=650,height=320),Spacer(1,8),Paragraph("Data preview",styles["Heading2"])]
    preview=working.head(12).fillna("").astype(str)
    table=Table([list(preview.columns)]+preview.values.tolist(), repeatRows=1)
    table.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.lightgrey),("GRID",(0,0),(-1,-1),0.25,colors.grey),("FONTSIZE",(0,0),(-1,-1),7)]))
    story.append(table)
    if not results.empty:
        story += [Spacer(1,8),Paragraph("Calculated-year results",styles["Heading2"])]
        r=results.head(30).fillna("").astype(str)
        t=Table([list(r.columns)]+r.values.tolist(),repeatRows=1)
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.lightgrey),("GRID",(0,0),(-1,-1),0.25,colors.grey),("FONTSIZE",(0,0),(-1,-1),7)]))
        story.append(t)
    doc.build(story)
    return out.getvalue()

# Sidebar: historical data configuration
st.sidebar.header("Historical data")
country_label=st.sidebar.selectbox("Country", list(COUNTRIES), index=0)
indicator_label=st.sidebar.selectbox("Indicator", list(INDICATORS), index=0)
degree=st.sidebar.slider("Polynomial degree", 3, 8, 3)
sample_increment=st.sidebar.slider("Model marker increment (years)",1,10,2)
horizon=st.sidebar.slider("Forward display horizon (years)",0,50,10)
printer=st.sidebar.checkbox("Printer-friendly report view",False)
st.sidebar.caption("The World Bank API may have gaps. The requested window is the previous 70 years, excluding the current year.")
current_year=date.today().year
start_year,end_year=current_year-70,current_year-1
indicator_code, units, definition=INDICATORS[indicator_label]
country_code=COUNTRIES[country_label]
source_url=f"https://api.worldbank.org/v2/country/{country_code}/indicator/{indicator_code}?date={start_year}:{end_year}&format=json"

with st.spinner("Retrieving World Bank observations..."):
    source_df, api_error=fetch_world_bank(country_code,indicator_code,start_year,end_year)
if api_error:
    st.warning(api_error)
st.markdown(f"**Research window:** {start_year}–{end_year}  ·  **Retrieved:** {date.today().isoformat()}")
st.markdown(f"**Indicator definition:** {definition}  \n**Units:** {units}  \n**Source:** [World Bank API]({source_url})")
st.caption("Brazil is included as a Latin American comparison country. Indicator definitions and coverage can differ by country and year.")

# Preserve immutable source and separate editable working copy.
source_key=f"source::{country_code}::{indicator_code}"
edit_key=f"edit::{country_code}::{indicator_code}"
if source_key not in st.session_state or st.session_state.get("source_signature") != (country_code,indicator_code,start_year,end_year):
    st.session_state[source_key]=source_df.copy()
    st.session_state["source_signature"]=(country_code,indicator_code,start_year,end_year)
    st.session_state[edit_key]=source_df.copy()
if edit_key not in st.session_state:
    st.session_state[edit_key]=source_df.copy()
if st.button("Reset edited data to source"):
    st.session_state[edit_key]=source_df.copy()
    st.rerun()
working=st.session_state[edit_key].copy()
st.subheader("Observed and editable data")
st.write(f"Source coverage: **{len(source_df)} non-null observations** across {source_df['year'].min() if len(source_df) else '—'}–{source_df['year'].max() if len(source_df) else '—'}. Actual coverage may be less than 70 years.")
edited=st.data_editor(working, num_rows="dynamic", use_container_width=True, key=f"editor::{country_code}::{indicator_code}", column_config={"year":st.column_config.NumberColumn("Year",step=1,format="%d"),"value":st.column_config.NumberColumn(f"Value ({units})")})
st.session_state[edit_key]=edited.copy()
modified=not edited.reset_index(drop=True).equals(source_df.reset_index(drop=True))
if modified: st.warning("USER-MODIFIED SCENARIO: model and exports use the editable table, not source-only observations.")

def validate_data(df):
    errors=[]
    if not {"year","value"}.issubset(df.columns): return ["Table must contain year and value columns."]
    v=df[["year","value"]].copy()
    v["year_num"]=pd.to_numeric(v["year"],errors="coerce")
    v["value_num"]=pd.to_numeric(v["value"],errors="coerce")
    if v["year_num"].isna().any(): errors.append("Every year must be a number.")
    if v["value_num"].isna().any(): errors.append("Every value must be numeric and non-empty.")
    valid=v.dropna(subset=["year_num","value_num"])
    if not np.all(valid["year_num"]%1==0): errors.append("Years must be integers.")
    if valid["year_num"].duplicated().any(): errors.append("Duplicate years are not allowed.")
    if (valid["year_num"]<1900).any() or (valid["year_num"]>current_year).any(): errors.append(f"Years must be between 1900 and {current_year}.")
    if indicator_label in ["Life expectancy at birth","Crude birth rate","Intentional homicide rate"] and (valid["value_num"]<0).any(): errors.append("This indicator cannot have negative values.")
    if indicator_label=="Life expectancy at birth" and (valid["value_num"]>125).any(): errors.append("Life expectancy above 125 years is implausible; check the value.")
    return errors, valid.rename(columns={"year_num":"year","value_num":"value"})[["year","value"]].astype({"year":int,"value":float})

errors, clean=validate_data(edited)
for err in errors: st.error(err)
model=None
if not errors and len(clean):
    try:
        model=fit_poly(clean,degree)
    except ValueError as exc:
        st.error(str(exc))
else:
    if not len(clean): st.info("No valid observations are available to fit a model.")

st.divider()
st.header("Historical model and fit")
residuals=pd.DataFrame(columns=["year","value","fitted","residual","abs_residual"])
if model:
    coeff,base_year,fit_data,fit_values,r2,mae,residuals=model
    min_year,max_year=int(fit_data.year.min()),int(fit_data.year.max())
    equation=poly_equation(coeff,base_year)
    c1,c2,c3,c4=st.columns(4)
    c1.metric("Observations",len(fit_data))
    c2.metric("In-sample R²",f"{r2:.5f}" if np.isfinite(r2) else "undefined")
    c3.metric("In-sample MAE",f"{mae:.5g} {units}")
    c4.metric("Historical mean",f"{fit_data.value.mean():.5g} {units}")
    st.code(equation)
    st.caption(f"Centered time uses t = year − {base_year}. Fitted historical range: {min_year}–{max_year}. Fit metrics are in-sample, not evidence of future accuracy.")
    st.dataframe(residuals[["year","value","fitted","residual"]].round(6),use_container_width=True)
    # Chronological holdout: last 20% (at least one) if enough points remain for the degree.
    holdout_note="Holdout unavailable: too few observations to reserve a chronological test set and fit the selected degree."
    if len(fit_data)>=degree+4:
        split=max(degree+1,int(len(fit_data)*0.8))
        train=fit_data.iloc[:split]
        test=fit_data.iloc[split:]
        if len(test):
            tc=train.year.to_numpy(float)-base_year
            hc=np.polyfit(tc,train.value.to_numpy(float),degree)
            hp=np.polyval(hc,test.year.to_numpy(float)-base_year)
            holdout_mae=float(np.mean(np.abs(test.value.to_numpy(float)-hp)))
            holdout_note=f"Chronological holdout MAE: {holdout_mae:.5g} {units} on {len(test)} later observations (separate from in-sample MAE)."
    st.info(holdout_note)
    if degree >= 6 and len(fit_data)<30: st.warning("High-degree polynomial with limited observations can oscillate substantially.")
    if horizon:
        future_years=np.arange(max_year+1,max_year+horizon+1)
    else: future_years=np.array([],dtype=int)
    curve_years=np.linspace(min_year,max(max_year, max_year+horizon),max(250, (max_year-min_year+horizon)*3))
    curve_t=curve_years-base_year
    curve_y=np.polyval(coeff,curve_t)
    marker_years=fit_data.year.iloc[::sample_increment].to_numpy(float)
    marker_y=np.polyval(coeff,marker_years-base_year)
    fig,ax=plt.subplots(figsize=(11,5))
    ax.scatter(fit_data.year,fit_data.value,label="Observed data",s=25)
    hist_mask=curve_years<=max_year
    ax.plot(curve_years[hist_mask],curve_y[hist_mask],label="Fitted curve (historical)")
    if horizon:
        ax.plot(curve_years[~hist_mask],curve_y[~hist_mask],"--",label="Extrapolated segment")
    ax.scatter(marker_years,marker_y,marker="x",label=f"Model markers every {sample_increment} years")
    ax.axvline(max_year,color="grey",linestyle=":",label="Historical boundary")
    ax.set_xlabel("Year"); ax.set_ylabel(units); ax.set_title(f"{indicator_label} — {country_label}")
    ax.legend(); ax.grid(alpha=.25)
    chart_png=fig_to_png(fig)
    st.image(chart_png, use_container_width=True)
    if len(future_years):
        future_values=np.polyval(coeff,future_years-base_year)
        if np.any(np.abs(future_values)>max(1,abs(fit_data.value.median()))*100):
            st.warning("Extrapolation flag: the polynomial predicts values far outside the historical scale. Predictions are not clipped and may be implausible.")
    st.caption("Uncertainty is described using residuals and MAE only. No validated 95% prediction interval is claimed.")
else:
    chart_png=None
    coeff=base_year=None
    min_year=max_year=None
    equation="No valid fitted equation"
    r2=mae=float("nan")

st.divider()
st.header("Calculate a year or a batch")
single_year=st.number_input("Single year (1950–2100)",min_value=1950,max_value=2100,value=min(max(current_year,1950),2100),step=1)
if "single_result" not in st.session_state: st.session_state.single_result=None
signature=(country_code,indicator_code,degree,tuple(clean.itertuples(index=False,name=None)) if not errors else ())
if st.session_state.get("model_signature") != signature:
    st.session_state["single_result"]=None
    st.session_state["batch_result"]=pd.DataFrame()
    st.session_state["model_signature"]=signature
if st.button("Calculate Value",disabled=model is None or bool(errors)):
    val=float(np.polyval(coeff,float(single_year)-base_year))
    st.session_state.single_result={"year":int(single_year),"estimate":val,"units":units,"range":(min_year,max_year),"classification":"within fitted historical range" if min_year<=single_year<=max_year else "outside fitted historical range"}
if st.session_state.single_result:
    sr=st.session_state.single_result
    st.success(f"{sr['year']}: estimated {sr['estimate']:.8g} {sr['units']} — {sr['classification']}.")
    if model and sr["year"] in set(fit_data.year):
        actual=float(fit_data.loc[fit_data.year==sr["year"],"value"].iloc[0])
        st.caption(f"This year has an actual observation ({actual:.8g} {units}); the displayed estimate is the fitted value, not the actual observation.")
    elif model:
        st.caption("This is a model estimate, not an observed value.")

batch_mode=st.radio("Batch year input",["Year range","Custom comma-separated years"],horizontal=True)
batch_years=[]
if batch_mode=="Year range":
    b1,b2,b3=st.columns(3)
    range_start=b1.number_input("Start year",1950,2100,2000,1)
    range_end=b2.number_input("End year",1950,2100, min(2030,2100),1)
    range_step=b3.slider("Step (years)",1,10,1)
    if range_start<=range_end: batch_years=list(range(int(range_start),int(range_end)+1,int(range_step)))
    else: st.warning("Start year must be less than or equal to end year.")
else:
    custom_years=st.text_input("Years separated by commas", "2000, 2010, 2020, 2030")
    invalid_custom=[]
    for token in custom_years.split(","):
        token=token.strip()
        if not token: continue
        try:
            number=float(token)
            if not number.is_integer() or not 1950<=number<=2100: invalid_custom.append(token)
            else: batch_years.append(int(number))
        except ValueError: invalid_custom.append(token)
    if invalid_custom: st.warning("Invalid years ignored (must be integers from 1950 to 2100): "+", ".join(invalid_custom))
batch_years=list(dict.fromkeys(batch_years))
if st.button("Calculate batch",disabled=model is None or bool(errors)):
    if batch_years:
        vals=np.polyval(coeff,np.array(batch_years,dtype=float)-base_year)
        st.session_state["batch_result"]=pd.DataFrame({"year":batch_years,"estimate":vals,"units":units,"range_classification":["within fitted historical range" if min_year<=y<=max_year else "outside fitted historical range" for y in batch_years]})
    else:
        st.warning("No valid requested years were supplied.")
batch_result=st.session_state.get("batch_result",pd.DataFrame())
if not batch_result.empty: st.dataframe(batch_result,use_container_width=True)

st.divider()
st.header("Compare countries")
comparison_labels=st.multiselect("Countries to compare (same indicator)",[x for x in COUNTRIES if x!=country_label],default=["Brazil (BR)"] if country_label!="Brazil (BR)" else ["Mexico (MX)"])
comparison_fig,comparison_ax=plt.subplots(figsize=(10,4))
comparison_ax.plot(clean.year,clean.value,marker="o",label=country_label)
comparison_data=[]
comparison_ax.set_xlabel("Year"); comparison_ax.set_ylabel(units); comparison_ax.set_title(f"{indicator_label}: country comparison")
comparison_ax.grid(alpha=.25)
for label in comparison_labels:
    code=COUNTRIES[label]
    df,err=fetch_world_bank(code,indicator_code,start_year,end_year)
    if err:
        st.warning(f"{label}: {err}")
        continue
    if len(df):
        comparison_ax.plot(df.year,df.value,marker=".",label=label)
        comparison_data.append({"country":label,"observations":len(df),"first_year":int(df.year.min()),"last_year":int(df.year.max())})
comparison_ax.legend()
st.pyplot(comparison_fig)
plt.close(comparison_fig)
if comparison_data: st.dataframe(pd.DataFrame(comparison_data),use_container_width=True)
st.caption("Country coverage may differ; gaps are missing observations, not zeros.")

st.divider()
st.header("Function lab: Algebra 2, Precalculus, and Calculus")
mode=st.selectbox("Mathematics pathway",["Honors Algebra 2","Precalculus","Calculus"],index=2)
context=st.selectbox("Context",list(CONTEXTS))
default_dep,default_dep_unit,default_ind,default_ind_unit,suggestion,context_help=CONTEXTS[context]
context_description=st.text_area("Context description",context_help)
dep_name=st.text_input("Dependent variable name",default_dep)
dep_unit=st.text_input("Dependent variable units",default_dep_unit)
ind_name=st.text_input("Independent variable name",default_ind)
ind_unit=st.text_input("Independent variable units",default_ind_unit)
analysis_min,analysis_max=st.slider("Analysis interval for function lab",min_value=-20.0,max_value=100.0,value=(0.0,10.0),step=0.5)
x0=st.slider("Current input x",float(analysis_min),float(analysis_max),float((analysis_min+analysis_max)/2),step=max((analysis_max-analysis_min)/100,0.01))
left,right=st.columns(2)
a=left.number_input("Parameter a",value=1.0)
b=right.number_input("Parameter b",value=0.2)
c=left.number_input("Parameter c",value=0.0)
d=right.number_input("Parameter d",value=0.0)
function_source=st.radio("Function source",["Fit from historical data","Suggested function","Custom expression"],horizontal=True)
if function_source=="Fit from historical data":
    if model:
        x_symbol=sp.Symbol("x", real=True)
        t_symbol=sp.Symbol("t", real=True)
        # Use year x and centered polynomial coefficients via symbolic substitution.
        expr=sum(sp.Float(float(coef), 14)*(x_symbol-base_year)**(len(coeff)-i-1) for i,coef in enumerate(coeff))
        x_meaning="calendar year"
        x_unit="year"
    else:
        expr=None
        x_symbol=sp.Symbol("x", real=True)
        x_meaning=ind_name
        x_unit=ind_unit
elif function_source=="Suggested function":
    x_symbol=sp.Symbol("x", real=True)
    if context in ["Medical","Biology","Business"]:
        expr=sp.Float(a)*sp.exp(-sp.Float(abs(b))*x_symbol)+sp.Float(c)
    elif context in ["Weather","Bioengineering"]:
        expr=sp.Float(a)*sp.sin(sp.Float(b)*x_symbol)+sp.Float(c)
    else:
        expr=sp.Float(a)*x_symbol**2+sp.Float(b)*x_symbol+sp.Float(c)
    x_meaning=ind_name; x_unit=ind_unit
else:
    x_symbol=sp.Symbol("x", real=True)
    custom_expr=st.text_input("Enter f(x), e.g. 2*x**3 - 3*x or sin(x)", "x**3 - 3*x")
    try:
        expr=safe_expression(custom_expr,x_symbol)
    except ValueError as exc:
        expr=None
        st.error(str(exc))
    x_meaning=ind_name; x_unit=ind_unit

if expr is not None:
    try:
        derivative=sp.diff(expr,x_symbol)
        second=sp.diff(derivative,x_symbol)
        st.markdown(f"**Function:** \(f(x)={sp.latex(expr)}\)")
        st.markdown(f"**First derivative:** \(f'(x)={sp.latex(derivative)}\)")
        st.markdown(f"**Second derivative:** \(f''(x)={sp.latex(second)}\)")
        st.caption("Derivatives of the World Bank fit are with respect to calendar year. For other contexts, x and y units are those you define above.")
        f0=float(evaluate_expr(expr,x_symbol,np.array([x0]))[0])
        fp0=float(evaluate_expr(derivative,x_symbol,np.array([x0]))[0])
        fpp0=float(evaluate_expr(second,x_symbol,np.array([x0]))[0])
        st.write(f"At x = {x0:g}: f(x) = {f0:.7g} {dep_unit}; f′(x) = {fp0:.7g} {dep_unit}/{x_unit}; f″(x) = {fpp0:.7g} {dep_unit}/{x_unit}².")
        st.write(f"Interpretation: {context_description} The first derivative describes the local rate of change; the second derivative describes how that rate is changing.")
        l1,l2=st.columns(2)
        secant_left=l1.slider("Secant interval start",float(analysis_min),float(analysis_max),float(analysis_min))
        secant_right=l2.slider("Secant interval end",float(analysis_min),float(analysis_max),float(analysis_max))
        if secant_left>secant_right: secant_left,secant_right=secant_right,secant_left
        fleft=float(evaluate_expr(expr,x_symbol,np.array([secant_left]))[0])
        fright=float(evaluate_expr(expr,x_symbol,np.array([secant_right]))[0])
        avg_rate=(fright-fleft)/(secant_right-secant_left) if secant_right!=secant_left and np.isfinite(fleft+fright) else np.nan
        st.write(f"Average rate of change from {secant_left:g} to {secant_right:g}: {avg_rate:.7g} {dep_unit}/{x_unit}" if np.isfinite(avg_rate) else "Average rate is undefined on this interval.")
        # Numerical curve; NaNs preserve visible gaps around poles/discontinuities.
        xs=np.linspace(analysis_min,analysis_max,900)
        ys=evaluate_expr(expr,x_symbol,xs)
        show_f=st.checkbox("Show function",True)
        show_first=st.checkbox("Show first derivative",True)
        show_second=st.checkbox("Show second derivative",False)
        show_tangent=st.checkbox("Show tangent at current x",True)
        show_secant=st.checkbox("Show secant line",True)
        fig,ax=plt.subplots(figsize=(10,5))
        if show_f: ax.plot(xs,ys,label="f(x)")
        if show_first: ax.plot(xs,evaluate_expr(derivative,x_symbol,xs),label="f′(x)")
        if show_second: ax.plot(xs,evaluate_expr(second,x_symbol,xs),label="f″(x)")
        if show_f and np.isfinite(f0): ax.scatter([x0],[f0],label="Current point")
        if show_tangent and np.isfinite(f0+fp0): ax.plot(xs,fp0*(xs-x0)+f0,"--",label="Tangent at current x")
        if show_secant and secant_left!=secant_right and np.isfinite(avg_rate):
            sec_x=np.array([secant_left,secant_right])
            ax.plot(sec_x,fleft+avg_rate*(sec_x-secant_left),":",label="Secant line")
        ax.axhline(0,color="grey",linewidth=.6); ax.axvline(0,color="grey",linewidth=.6)
        ax.set_xlabel(f"{ind_name} ({ind_unit})"); ax.set_ylabel(f"{dep_name} / derivative scales")
        ax.grid(alpha=.25); ax.legend()
        st.pyplot(fig); plt.close(fig)
        if mode=="Honors Algebra 2":
            st.markdown("**Algebra 2 focus:** The domain is restricted to the selected analysis interval for this display; the range is the numerical range of plotted finite values. End behavior depends on the function and should not be inferred from a short display window.")
            st.markdown(f"Average rate over the selected interval is {avg_rate:.6g} {dep_unit}/{x_unit} where defined.")
        elif mode=="Precalculus":
            st.markdown("**Precalculus focus:** Degree and coefficients control polynomial shape and end behavior. Turning points occur at candidate zeros of f′; concavity is assessed from f″. Numerical roots below are candidates, not automatically extrema or inflection points.")
        else:
            st.markdown("**Calculus focus:** Derivative values give local rates; second derivatives describe changes in those rates. Numerical root checks are approximate and require classification tests.")
        # Numerical critical point / inflection candidate scan, with sign-change confirmation.
        def roots_in_interval(expr_to_scan):
            try:
                roots=sp.solve(sp.Eq(expr_to_scan,0),x_symbol)
                vals=[]
                for root in roots:
                    if root.is_real is True:
                        rv=float(root)
                        if analysis_min<=rv<=analysis_max and np.isfinite(rv): vals.append((rv,"symbolic/exact"))
                if vals: return vals
            except Exception: pass
            grid=np.linspace(analysis_min,analysis_max,2001)
            vals_grid=evaluate_expr(expr_to_scan,x_symbol,grid)
            vals=[]
            for i in range(len(grid)-1):
                if np.isfinite(vals_grid[i]) and np.isfinite(vals_grid[i+1]) and vals_grid[i]*vals_grid[i+1]<0:
                    vals.append(((grid[i]+grid[i+1])/2,"numerical approximation"))
            return vals
        critical=roots_in_interval(derivative)
        if critical:
            st.markdown("**Critical-point candidates**")
            rows=[]
            for rx,kind in critical:
                delta=max((analysis_max-analysis_min)/10000,1e-5)
                left_s=float(evaluate_expr(derivative,x_symbol,np.array([max(analysis_min,rx-delta)]))[0])
                right_s=float(evaluate_expr(derivative,x_symbol,np.array([min(analysis_max,rx+delta)]))[0])
                fval=float(evaluate_expr(expr,x_symbol,np.array([rx]))[0])
                classification="local minimum (f′ changes − to +)" if left_s<0<right_s else "local maximum (f′ changes + to −)" if left_s>0>right_s else "not classified as a local extremum by this sign test"
                rows.append({"x":rx,"f(x)":fval,"method":kind,"classification":classification})
            st.dataframe(pd.DataFrame(rows),use_container_width=True)
        inflections=roots_in_interval(second)
        inflection_rows=[]
        for rx,kind in inflections:
            delta=max((analysis_max-analysis_min)/10000,1e-5)
            lval=float(evaluate_expr(second,x_symbol,np.array([max(analysis_min,rx-delta)]))[0])
            rval=float(evaluate_expr(second,x_symbol,np.array([min(analysis_max,rx+delta)]))[0])
            if np.isfinite(lval+rval) and lval*rval<0:
                inflection_rows.append({"x":rx,"f(x)":float(evaluate_expr(expr,x_symbol,np.array([rx]))[0]),"method":kind,"evidence":"concavity changes"})
        if inflection_rows:
            st.markdown("**Verified inflection candidates (concavity changes)**")
            st.dataframe(pd.DataFrame(inflection_rows),use_container_width=True)
        else:
            st.write("No inflection point with a confirmed concavity change was found in the selected interval.")
        # Closed-interval absolute extrema: endpoints plus interior critical candidates.
        candidates=[analysis_min,analysis_max]+[r for r,_ in critical]
        evals=[float(evaluate_expr(expr,x_symbol,np.array([xx]))[0]) for xx in candidates]
        finite=[(xx,yy) for xx,yy in zip(candidates,evals) if np.isfinite(yy)]
        if finite:
            st.write(f"Closed-interval numerical absolute minimum: x={min(finite,key=lambda z:z[1])[0]:.6g}, f(x)={min(finite,key=lambda z:z[1])[1]:.6g}; maximum: x={max(finite,key=lambda z:z[1])[0]:.6g}, f(x)={max(finite,key=lambda z:z[1])[1]:.6g}. These results apply only when the function is defined and continuous across the interval.")
        st.caption("Domain/discontinuity note: graph gaps represent undefined or non-finite values. This numerical scan cannot prove all domain restrictions or detect every discontinuity; inspect rational denominators and logarithm/square-root domains.")
    except Exception as exc:
        st.error(f"Could not analyze this function safely: {exc}")
else:
    st.info("Choose valid source data or fix the custom expression to enable function analysis.")

st.divider()
st.header("Simulation")
visual=st.selectbox("Contextual visual",["Walking person with a prosthetic leg","Moving object / projectile","Tank or concentration indicator","Population / cell colony","Thermometer / weather indicator","Business / economic indicator"])
play_speed=st.slider("Playback speed (steps per second)",1,10,3)
play=st.checkbox("Play animation (updates on rerun)",False)
if "sim_x" not in st.session_state: st.session_state.sim_x=float(x0)
if st.button("Reset simulation"): st.session_state.sim_x=float(analysis_min)
if play:
    st.session_state.sim_x += (analysis_max-analysis_min)/max(10,play_speed*10)
    if st.session_state.sim_x>analysis_max: st.session_state.sim_x=float(analysis_min)
    st.info("Playback advances when the app reruns; use the slider or Reset to control the point. Streamlit reruns are user-driven unless your deployment adds a timer component.")
sim_x=st.slider("Simulation input",float(analysis_min),float(analysis_max),float(np.clip(st.session_state.sim_x,analysis_min,analysis_max)),key="sim_slider")
st.session_state.sim_x=sim_x
st.caption(f"Selected visual: {visual}. This is a schematic indicator, not a realistic anatomical, projectile, pharmacokinetic, population, weather, or financial simulation. Vertical scaling follows the selected function's value and is normalized for display.")
if expr is not None:
    sim_value=float(evaluate_expr(expr,x_symbol,np.array([sim_x]))[0])
    fig,ax=plt.subplots(figsize=(8,2.6))
    ax.axis("off")
    if visual=="Walking person with a prosthetic leg":
        ax.text(.04,.65,"●",fontsize=35); ax.plot([.09,.09],[.57,.28],linewidth=4); ax.plot([.09,.14],[.48,.40],linewidth=3); ax.plot([.09,.04],[.48,.40],linewidth=3)
        leg_height=.18+.08*np.tanh(sim_value/(abs(sim_value)+1) if np.isfinite(sim_value) else 0)
        ax.plot([.09,.06],[.28,.12],linewidth=4); ax.plot([.09,.14],[.28,leg_height],linewidth=4); ax.plot([.14,.18],[leg_height,leg_height],linewidth=4)
        ax.text(.24,.5,f"Input: {sim_x:.2f} {x_unit}\nFunction value: {sim_value:.4g} {dep_unit}",fontsize=11)
    elif visual=="Moving object / projectile":
        norm=.5+.35*np.tanh(sim_value/(abs(sim_value)+1) if np.isfinite(sim_value) else 0)
        ax.plot([.05,.95],[.1,.1]); ax.scatter([.1+.8*(sim_x-analysis_min)/(analysis_max-analysis_min or 1)],[norm],s=100)
        ax.text(.05,.85,f"{sim_value:.4g} {dep_unit}",fontsize=11)
    elif visual=="Tank or concentration indicator":
        norm=float(np.clip(.5+.45*np.tanh(sim_value/(abs(sim_value)+1) if np.isfinite(sim_value) else 0),.05,.95))
        ax.add_patch(plt.Rectangle((.08,.1),.18,.75,fill=False,linewidth=2)); ax.add_patch(plt.Rectangle((.08,.1),.18,.75*norm,alpha=.5))
        ax.text(.34,.5,f"{sim_value:.4g} {dep_unit}",fontsize=12)
    elif visual=="Population / cell colony":
        count=int(np.clip(4+12*(.5+.5*np.tanh(sim_value/(abs(sim_value)+1) if np.isfinite(sim_value) else 0)),1,16))
        for i in range(count):
            ang=2*np.pi*i/count; ax.scatter(.15+.05*np.cos(ang),.5+.2*np.sin(ang),s=160)
        ax.text(.35,.5,f"Indicator: {sim_value:.4g} {dep_unit}",fontsize=12)
    elif visual=="Thermometer / weather indicator":
        norm=float(np.clip(.5+.45*np.tanh(sim_value/(abs(sim_value)+1) if np.isfinite(sim_value) else 0),.05,.95))
        ax.add_patch(plt.Rectangle((.1,.15),.08,.65,fill=False,linewidth=2)); ax.add_patch(plt.Rectangle((.1,.15),.08,.65*norm,alpha=.5))
        ax.text(.3,.5,f"{sim_value:.4g} {dep_unit}",fontsize=12)
    else:
        ax.plot([.08,.92],[.3,.3],linewidth=2); ax.scatter([.08+.84*(sim_x-analysis_min)/(analysis_max-analysis_min or 1)],[.3],s=150)
        ax.text(.08,.65,f"{dep_name}: {sim_value:.4g} {dep_unit}",fontsize=12)
    st.pyplot(fig); plt.close(fig)

st.divider()
st.header("Export current analysis")
summary={
    "app":APP_TITLE,"retrieval_date":date.today().isoformat(),"country":country_label,
    "indicator":indicator_label,"indicator_code":indicator_code,"units":units,
    "requested_years":f"{start_year}-{end_year}","source_observations":len(source_df),
    "working_observations":len(clean) if not errors else 0,"user_modified_scenario":modified,
    "degree":degree,"base_year":base_year if model else "not fitted",
    "equation":equation,"in_sample_r_squared":r2,"in_sample_mae":mae,
    "mathematics_pathway":mode,"context":context,"function_source":function_source,
    "function":str(expr) if expr is not None else "not available",
    "fitted_range":f"{min_year}-{max_year}" if model else "not available",
}
findings=[
    f"Indicator: {indicator_label}. Definition: {definition}",
    f"Actual source coverage: {len(source_df)} observations; requested window {start_year}–{end_year}.",
    "Polynomial models describe patterns in the available data; they do not establish causes.",
    "Extrapolations can be unstable, especially for high-degree polynomials. No validated 95% prediction interval is provided.",
    "User-modified data are a scenario and must not be represented as original World Bank observations.",
]
if model:
    st.download_button("Download working data CSV",csv_bytes(clean),file_name="working_data.csv",mime="text/csv")
    st.download_button("Download calculated results CSV",csv_bytes(batch_result),file_name="calculated_years.csv",mime="text/csv")
    xlsx=make_excel(summary,clean,batch_result,residuals)
    st.download_button("Download Excel workbook (.xlsx)",xlsx,file_name="hispanic_heritage_analysis.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    if chart_png is not None:
        pdf=make_pdf(summary,clean,batch_result,chart_png,findings)
        st.download_button("Download PDF report",pdf,file_name="hispanic_heritage_report.pdf",mime="application/pdf")
else:
    st.info("Exports that require a fitted model become available when enough valid observations remain.")
st.markdown(f"**Indicator source link:** [Open World Bank indicator API]({source_url})")
st.caption("Educational research tool only. It does not make causal claims, guarantee forecasts, or replace expert interpretation.")
