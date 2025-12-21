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

# --- 2. LOGIN RESISTENTE ---
if "user" not in st.session_state:
    st.title("🔐 Acceso")
    if "users" not in st.secrets:
        st.error("No se encuentran usuarios en Secrets.")
        st.stop()

    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            users = st.secrets["users"]
            if u in users and str(p) == str(users[u]):
                st.session_state["user"] = u
                st.session_state["role"] = st.secrets.get("roles", {}).get(u, "user")
                st.session_state["last_activity"] = time.time()
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

# --- 3. TIEMPO DE SESIÓN ---
if time.time() - st.session_state.get("last_activity", time.time()) > 300:
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()
st.session_state["last_activity"] = time.time()

# --- 4. CONEXIÓN Y DATOS ---
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
# Obtenemos datos frescos
data = ws_inv.get_all_values()
headers = [h.strip() for h in data[0]]
# Creamos el DF principal con el índice original del Excel como una columna
df_master = pd.DataFrame(data[1:], columns=headers)
df_master["Stock"] = pd.to_numeric(df_master["Stock"], errors='coerce').fillna(0).astype(int)
df_master["idx_excel"] = range(2, len(df_master) + 2) # Guardamos la fila real del Excel

# Filtro para usuarios: solo lo que tiene Stock
df_visible = df_master[df_master["Stock"] > 0].copy()

def registrar_log(accion, med, stock):
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    ws_log.append_row([fecha, st.session_state.user, accion, med, str(stock)])

# --- 5. FUNCIÓN TARJETAS ---
def pintar_tarjeta(fila, key_suffix):
    nombre = fila["Nombre"]
    stock = int(fila["Stock"])
    caducidad = fila["Caducidad"]
    ubi = fila["Ubicacion"]
    idx = int(fila["idx_excel"]) # Usamos el índice que guardamos antes
    es_admin = st.session_state.get("role") == "admin"
    
    bg = "#d4edda"
    try:
        dt = datetime.strptime(caducidad, "%Y-%m-%d")
        if dt < datetime.now(): bg = "#f8d7da"
        elif dt <= datetime.now() + timedelta(days=60): bg = "#fff3cd"
    except: pass

    with st.container():
        c1, c2, c3, c4, c5 = st.columns([4, 1, 1, 1, 1])
        c1.markdown(f'<div class="tarjeta-med" style="background:{bg};"><b>{nombre}</b> | Stock: {stock}<br><small>{ubi} - Vence: {caducidad}</small></div>', unsafe_allow_html=True)
        
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

# --- 6. INTERFAZ ---
st.title("💊 Inventario Médico")

# Buscador dinámico
opciones = sorted(df_visible["Nombre"].unique().tolist())
busqueda = st.selectbox("🔍 Buscar medicamento...", [""] + opciones)

if busqueda:
    res = df_visible[df_visible["Nombre"] == busqueda]
    for _, fila in res.iterrows():
        pintar_tarjeta(fila, "search")
    st.divider()

# Pestañas
p_nombres = ["⚠ Alertas", "📋 Todo", "📁 Vitrina", "📁 Armario"]
if st.session_state.role == "admin": p_nombres.append("📜 Registro")
tabs = st.tabs(p_nombres)

with tabs[0]: # Alertas
    l1 = datetime.now() + timedelta(days=30)
    for _, f in df_visible.iterrows():
        try:
            if datetime.strptime(f["Caducidad"], "%Y-%m-%d") <= l1:
                pintar_tarjeta(f, "alert")
        except: pass

with tabs[1]: # Todo
    for _, f in df_visible.iterrows():
        pintar_tarjeta(f, "all")

with tabs[2]: # Vitrina
    for _, f in df_visible[df_visible["Ubicacion"] == "Medicación de vitrina"].iterrows():
        pintar_tarjeta(f, "vit")

with tabs[3]: # Armario
    for _, f in df_visible[df_visible["Ubicacion"] == "Medicación de armario"].iterrows():
        pintar_tarjeta(f, "arm")

if st.session_state.role == "admin":
    with tabs[-1]:
        st.subheader("🕵 Historial")
        logs = ws_log.get_all_records()
        if logs: st.table(pd.DataFrame(logs).iloc[::-1])

with st.sidebar:
    st.write(f"Usuario: *{st.session_state.user}*")
    if st.button("🚪 Salir"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
    
    if st.session_state.role == "admin":
        st.divider()
        with st.form("nuevo", clear_on_submit=True):
            n = st.text_input("Nombre")
            s = st.number_input("Stock", min_value=1)
            c = st.date_input("Caducidad")
            u = st.selectbox("Ubi", ["Medicación de vitrina", "Medicación de armario"])
            if st.form_submit_button("Guardar"):
                if n:
                    ws_inv.append_row([n.capitalize(), int(s), str(c), u])
                    registrar_log("NUEVO REGISTRO", n.capitalize(), s)
                    st.rerun()