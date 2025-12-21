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
    @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.1; } 100% { opacity: 1; } }
    .blink-icon { animation: blink 1s infinite; font-size: 1.2rem; margin-right: 5px; }
    .tarjeta-med { color: black !important; border: 1px solid rgba(0,0,0,0.1); border-radius:8px; padding:10px; margin-bottom:10px; }
    </style>
""", unsafe_allow_html=True)

# --- 2. LOGIN ---
if "user" not in st.session_state:
    st.title("🔐 Acceso")
    if "users" not in st.secrets:
        st.error("No hay usuarios configurados.")
        st.stop()
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if u in st.secrets["users"] and str(p) == str(st.secrets["users"][u]):
                st.session_state["user"] = u
                st.session_state["role"] = st.secrets.get("roles", {}).get(u, "user")
                st.session_state["last_activity"] = time.time()
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

# --- 3. CONEXIÓN ---
@st.cache_resource
def conectar():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(st.secrets["url_excel"])
        ws_inv = sh.get_worksheet(0)
        try:
            ws_log = sh.worksheet("Registro")
        except:
            ws_log = sh.add_worksheet(title="Registro", rows="1000", cols="5")
            ws_log.append_row(["Fecha", "Usuario", "Acción", "Medicamento", "Stock Final"])
        return ws_inv, ws_log
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None, None

ws_inv, ws_log = conectar()
data = ws_inv.get_all_values()
headers = [h.strip() for h in data[0]]
df_master = pd.DataFrame(data[1:], columns=headers)
df_master["Stock"] = pd.to_numeric(df_master["Stock"], errors='coerce').fillna(0).astype(int)
df_master["idx_excel"] = range(2, len(df_master) + 2)

# Filtro: Solo lo que tiene Stock
df_visible = df_master[df_master["Stock"] > 0].copy()

def registrar_log(accion, med, stock):
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    ws_log.append_row([fecha, st.session_state.user, accion, med, str(stock)])

# --- 4. FUNCIÓN TARJETAS ---
def pintar_tarjeta(fila, key_suffix):
    nombre = fila["Nombre"]
    stock = int(fila["Stock"])
    caducidad = fila["Caducidad"]
    idx = int(fila["idx_excel"])
    es_admin = st.session_state.role == "admin"
    
    bg = "#d4edda"
    try:
        dt = datetime.strptime(caducidad, "%Y-%m-%d")
        if dt < datetime.now(): bg = "#f8d7da"
        elif dt <= datetime.now() + timedelta(days=60): bg = "#fff3cd"
    except: pass

    with st.container():
        c1, c2, c3, c4, c5 = st.columns([4, 1, 1, 1, 1])
        c1.markdown(f'<div class="tarjeta-med" style="background:{bg};"><b>{nombre}</b> | Stock: {stock}<br><small>Vence: {caducidad}</small></div>', unsafe_allow_html=True)
        
        if c2.button("💊", key=f"ret_{idx}_{key_suffix}"):
            n = max(0, stock - 1)
            ws_inv.update_cell(idx, headers.index("Stock")+1, n)
            registrar_log("RETIRADO", nombre, n)
            st.rerun()
        if es_admin:
            if c3.button("➕", key=f"add_{idx}_{key_suffix}"):
                ws_inv.update_cell(idx, headers.index("Stock")+1, stock + 1)
                registrar_log("AÑADIDO (ADMIN)", nombre, stock + 1)
                st.rerun()
            if c4.button("➖", key=f"sub_{idx}_{key_suffix}"):
                n = max(0, stock - 1)
                ws_inv.update_cell(idx, headers.index("Stock")+1, n)
                registrar_log("QUITADO (ADMIN)", nombre, n)
                st.rerun()
            if c5.button("🗑", key=f"del_{idx}_{key_suffix}"):
                ws_inv.delete_rows(idx)
                registrar_log("ELIMINADO", nombre, "X")
                st.rerun()

# --- 5. INTERFAZ Y BUSCADOR MEJORADO ---
st.title("💊 Gestión de Inventario")

# BUSCADOR DE COINCIDENCIA REAL
# Usamos un text_input en lugar de selectbox para que sea libre
termino_busqueda = st.text_input("🔍 Escribe el nombre para filtrar resultados...", "").lower()

if termino_busqueda:
    # Filtramos el dataframe si el nombre contiene lo que escribimos
    df_filtrado = df_visible[df_visible["Nombre"].str.lower().str.contains(termino_busqueda)]
    
    if not df_filtrado.empty:
        st.subheader(f"Resultados para: '{termino_busqueda}'")
        for _, fila in df_filtrado.iterrows():
            pintar_tarjeta(fila, "search_live")
    else:
        st.warning("No se encontraron coincidencias.")
    st.divider()

# Tabs normales (aquí sigue apareciendo todo el inventario organizado)
tabs = st.tabs(["⚠ Alertas", "📋 Todo", "📁 Vitrina", "📁 Armario"])

with tabs[0]:
    limite = datetime.now() + timedelta(days=30)
    for _, f in df_visible.iterrows():
        try:
            if datetime.strptime(f["Caducidad"], "%Y-%m-%d") <= limite:
                pintar_tarjeta(f, "tab_alert")
        except: pass

with tabs[1]:
    for _, f in df_visible.iterrows():
        pintar_tarjeta(f, "tab_all")

# ... (El resto del sidebar y tabs de Vitrina/Armario/Registro se mantienen igual)