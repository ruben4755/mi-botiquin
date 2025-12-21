import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión Médica Pro", layout="wide", page_icon="💊")

st.markdown("""
    <style>
    .tarjeta-med { color: black !important; border: 1px solid rgba(0,0,0,0.1); border-radius:8px; padding:10px; margin-bottom:10px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. LOGIN ---
if "user" not in st.session_state:
    st.title("🔐 Acceso")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if u in st.secrets["users"] and str(p) == str(st.secrets["users"][u]):
                st.session_state["user"] = u
                st.session_state["role"] = st.secrets.get("roles", {}).get(u, "user")
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

# --- 3. CONEXIÓN ---
@st.cache_resource
def conectar():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    sh = client.open_by_url(st.secrets["url_excel"])
    ws_inv = sh.get_worksheet(0)
    try:
        ws_log = sh.worksheet("Registro")
    except:
        ws_log = sh.add_worksheet(title="Registro", rows="1000", cols="5")
    return ws_inv, ws_log

ws_inv, ws_log = conectar()
data = ws_inv.get_all_values()
headers = [h.strip() for h in data[0]]
df_master = pd.DataFrame(data[1:], columns=headers)
df_master["Stock"] = pd.to_numeric(df_master["Stock"], errors='coerce').fillna(0).astype(int)
df_master["idx_excel"] = range(2, len(df_master) + 2)

def registrar_log(accion, med, stock):
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    ws_log.append_row([fecha, st.session_state.user, accion, med, str(stock)])

# --- 4. FUNCIÓN DE TARJETAS ---
def pintar_tarjeta(fila, k):
    nombre, stock, cad, ubi, idx = fila["Nombre"], fila["Stock"], fila["Caducidad"], fila["Ubicacion"], fila["idx_excel"]
    bg = "#d4edda"
    try:
        dt = datetime.strptime(cad, "%Y-%m-%d")
        if dt < datetime.now(): bg = "#f8d7da"
        elif dt <= datetime.now() + timedelta(days=60): bg = "#fff3cd"
    except: pass

    with st.container():
        c1, c2, c3, c4 = st.columns([5, 1, 1, 1])
        c1.markdown(f'<div class="tarjeta-med" style="background:{bg};"><b>{nombre}</b> | Stock: {stock}<br><small>{ubi} - Vence: {cad}</small></div>', unsafe_allow_html=True)
        
        if c2.button("💊", key=f"ret_{idx}_{k}"):
            n = max(0, int(stock) - 1)
            ws_inv.update_cell(idx, headers.index("Stock")+1, n)
            registrar_log("RETIRADO", nombre, n)
            st.rerun()
        
        if st.session_state.role == "admin":
            if c3.button("➕", key=f"add_{idx}_{k}"):
                ws_inv.update_cell(idx, headers.index("Stock")+1, int(stock) + 1)
                st.rerun()
            if c4.button("🗑", key=f"del_{idx}_{k}"):
                ws_inv.delete_rows(idx)
                registrar_log("ELIMINADO", nombre, "0")
                st.rerun()

# --- 5. BARRA LATERAL (ORIGINAL) ---
with st.sidebar:
    st.title(f"Hola, {st.session_state.user}")
    if st.button("🚪 Cerrar Sesión"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
    
    # BUSCADOR EN EL LATERAL (Filtra sin necesidad de Enter constante)
    st.divider()
    st.subheader("🔍 Buscador rápido")
    termino = st.text_input("Escribe nombre...", label_visibility="collapsed")

    if st.session_state.role == "admin":
        st.divider()
        st.subheader("➕ Añadir Medicamento")
        with st.form("nuevo", clear_on_submit=True):
            n = st.text_input("Nombre")
            s = st.number_input("Stock", min_value=1)
            c = st.date_input("Caducidad")
            u = st.selectbox("Ubi", ["Medicación de vitrina", "Medicación de armario"])
            if st.form_submit_button("Guardar"):
                ws_inv.append_row([n.upper(), int(s), str(c), u])
                registrar_log("ALTA", n.upper(), s)
                st.rerun()

# --- 6. CUERPO PRINCIPAL ---
st.title("💊 Inventario Médico")

# Filtramos según el buscador del sidebar
df_visible = df_master[df_master["Stock"] > 0].copy()

if termino:
    df_filtrado = df_visible[df_visible["Nombre"].str.lower().str.contains(termino.lower())]
    st.subheader(f"Resultados para: {termino}")
    if not df_filtrado.empty:
        for _, f in df_filtrado.iterrows():
            pintar_tarjeta(f, "search")
    else:
        st.warning("No se han encontrado medicamentos.")
    st.divider()

# Pestañas de siempre
tabs = st.tabs(["📋 Todo", "⚠ Alertas", "📁 Vitrina", "📁 Armario"])
with tabs[0]:
    for _, f in df_visible.iterrows(): pintar_tarjeta(f, "all")
with tabs[1]:
    limite = datetime.now() + timedelta(days=45)
    for _, f in df_visible.iterrows():
        try:
            if datetime.strptime(f["Caducidad"], "%Y-%m-%d") <= limite: pintar_tarjeta(f, "warn")
        except: pass
with tabs[2]:
    for _, f in df_visible[df_visible["Ubicacion"] == "Medicación de vitrina"].iterrows(): pintar_tarjeta(f, "vit")
with tabs[3]:
    for _, f in df_visible[df_visible["Ubicacion"] == "Medicación de armario"].iterrows(): pintar_tarjeta(f, "arm")