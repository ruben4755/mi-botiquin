import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión Médica Pro", layout="wide", page_icon="💊")

# Optimización para móvil: reducir márgenes y fuentes
st.markdown("""
    <style>
    .tarjeta-med { color: black !important; border: 1px solid rgba(0,0,0,0.1); border-radius:8px; padding:8px; margin-bottom:8px; font-size: 14px; }
    .stTextInput>div>div>input { font-size: 16px !important; } /* Evita zoom automático en iPhone */
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
        c1, c2, c3, c4 = st.columns([4, 2, 1, 1]) # Ajustado para móvil
        c1.markdown(f'<div class="tarjeta-med" style="background:{bg};"><b>{nombre}</b><br>Stock: {stock}</div>', unsafe_allow_html=True)
        
        if c2.button("💊 Coger", key=f"ret_{idx}_{k}"):
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

# --- 5. BARRA LATERAL ---
with st.sidebar:
    st.subheader(f"👤 {st.session_state.user}")
    
    # BUSCADOR MÓVIL OPTIMIZADO
    # Usamos text_input fuera de formulario. 
    # Para móviles, esto es lo más fiable.
    busqueda_movil = st.text_input("🔍 Buscar Medicamento", placeholder="Escribe aquí...", key="search_box").lower()

    if st.button("🚪 Cerrar Sesión"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()

    if st.session_state.role == "admin":
        st.divider()
        with st.expander("➕ Añadir Nuevo"):
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
st.title("💊 Inventario")

df_visible = df_master[df_master["Stock"] > 0].copy()

# LÓGICA DE FILTRADO DINÁMICO
if busqueda_movil:
    df_filtrado = df_visible[df_visible["Nombre"].str.lower().str.contains(busqueda_movil)]
    if not df_filtrado.empty:
        st.subheader(f"Resultados para '{busqueda_movil}'")
        for _, f in df_filtrado.iterrows():
            pintar_tarjeta(f, "search")
    else:
        st.warning("No hay coincidencias.")
    st.divider()

# Pestañas
tabs = st.tabs(["📋 Todo", "⚠ Alertas", "📁 Vitrina", "📁 Armario"])
with tabs[0]:
    for _, f in df_visible.iterrows(): pintar_tarjeta(f, "all")
# ... (las demás pestañas se mantienen igual)