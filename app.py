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
    /* Estilo para el panel de admin */
    .admin-panel { background-color: #f0f2f6; padding: 20px; border-radius: 10px; border: 2px dashed #ff4b4b; margin-bottom: 25px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. LOGIN (Simplificado para el ejemplo) ---
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

# --- 4. PANEL DE ADMINISTRACIÓN FIJO ---
if st.session_state.role == "admin":
    with st.expander("➕ PANEL DE ADMINISTRADOR: Añadir nuevo medicamento", expanded=True):
        with st.form("nuevo_fijo", clear_on_submit=True):
            col_a, col_b, col_c, col_d = st.columns([3, 1, 2, 2])
            n_nombre = col_a.text_input("Nombre del Medicamento")
            n_stock = col_b.number_input("Stock Inicial", min_value=1, value=1)
            n_cad = col_c.date_input("Fecha de Caducidad")
            n_ubi = col_d.selectbox("Ubicación", ["Medicación de vitrina", "Medicación de armario"])
            
            if st.form_submit_button("✅ Registrar en Inventario"):
                if n_nombre:
                    ws_inv.append_row([n_nombre.upper(), int(n_stock), str(n_cad), n_ubi])
                    registrar_log("ALTA", n_nombre.upper(), n_stock)
                    st.success(f"{n_nombre} añadido correctamente.")
                    time.sleep(1)
                    st.rerun()

# --- 5. BUSCADOR INSTANTÁNEO ---
st.title("💊 Inventario en Tiempo Real")

# El buscador ahora usa una clave para mantener el estado
busqueda = st.text_input("🔍 Escribe para buscar (se filtra automáticamente)...", key="search_input").lower()

# Filtrado de datos
df_visible = df_master[df_master["Stock"] > 0].copy()
if busqueda:
    df_visible = df_visible[df_visible["Nombre"].str.lower().str.contains(busqueda)]

# --- 6. FUNCIÓN DE TARJETAS ---
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
        
        if c2.button("💊", key=f"ret_{idx}_{k}", help="Retirar 1 unidad"):
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
                registrar_log("BORRADO", nombre, "0")
                st.rerun()

# --- 7. TABS DE VISUALIZACIÓN ---
if busqueda:
    st.subheader(f"Resultados de: '{busqueda}'")
    for _, f in df_visible.iterrows():
        pintar_tarjeta(f, "search")
else:
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