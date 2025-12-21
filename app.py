import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión Médica Pro", layout="wide", page_icon="💊")

# CSS para que las tarjetas se vean bien en móvil
st.markdown("""
    <style>
    .tarjeta-med { color: black !important; border-left: 5px solid #28a745; background: #f8f9fa; padding:12px; border-radius:8px; margin-bottom:10px; }
    .stSelectbox div[data-baseweb="select"] { font-size: 18px !important; } 
    </style>
""", unsafe_allow_html=True)

# --- 2. LOGIN (BLOQUEADO PARA EVITAR ERRORES) ---
if "user" not in st.session_state:
    st.title("🔐 Acceso")
    with st.form("login_form"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if "users" in st.secrets and u in st.secrets["users"] and str(p) == str(st.secrets["users"][u]):
                st.session_state["user"] = u
                st.session_state["role"] = st.secrets.get("roles", {}).get(u, "user")
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
    st.stop() # Detiene la ejecución aquí si no está logueado

# --- 3. CONEXIÓN (SOLO SI HAY LOGIN) ---
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
        return ws_inv, ws_log
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None, None

ws_inv, ws_log = conectar()
if not ws_inv: st.stop()

# Carga de datos
data = ws_inv.get_all_values()
headers = [h.strip() for h in data[0]]
df_master = pd.DataFrame(data[1:], columns=headers)
df_master["Stock"] = pd.to_numeric(df_master["Stock"], errors='coerce').fillna(0).astype(int)
df_master["idx_excel"] = range(2, len(df_master) + 2)
df_visible = df_master[df_master["Stock"] > 0].copy()

# --- 4. FUNCIONES ---
def registrar_log(accion, med, stock):
    fecha = datetime.now().strftime("%H:%M")
    ws_log.append_row([fecha, st.session_state.user, accion, med, str(stock)])

def pintar_tarjeta(fila, k):
    nombre, stock, cad, ubi, idx = fila["Nombre"], fila["Stock"], fila["Caducidad"], fila["Ubicacion"], fila["idx_excel"]
    with st.container():
        st.markdown(f'<div class="tarjeta-med"><b>{nombre}</b> | Stock: {stock}<br><small>{ubi} - Vence: {cad}</small></div>', unsafe_allow_html=True)
        c1, c2, c3 = st.columns([2, 1, 1])
        if c1.button(f"💊 RETIRAR", key=f"btn_{idx}_{k}"):
            n = max(0, int(stock) - 1)
            ws_inv.update_cell(idx, headers.index("Stock")+1, n)
            registrar_log("RETIRADO", nombre, n)
            st.rerun()
        if st.session_state.role == "admin":
            if c2.button("➕", key=f"add_{idx}_{k}"):
                ws_inv.update_cell(idx, headers.index("Stock")+1, int(stock) + 1)
                st.rerun()
            if c3.button("🗑", key=f"del_{idx}_{k}"):
                ws_inv.delete_rows(idx)
                st.rerun()

# --- 5. INTERFAZ PRINCIPAL ---
st.title("💊 Inventario Rápido")

# BUSCADOR MÁGICO: El selectbox de Streamlit filtra mientras escribes SIN ENTER.
# Al seleccionar, la tarjeta aparece debajo al instante.
opciones = sorted(df_visible["Nombre"].unique().tolist())
seleccion = st.selectbox("🔍 BUSCAR (Escribe el nombre aquí...)", [""] + opciones, index=0)

if seleccion != "":
    fila_sel = df_visible[df_visible["Nombre"] == seleccion].iloc[0]
    st.subheader("📍 Resultado:")
    pintar_tarjeta(fila_sel, "busqueda")
    st.divider()

# Pestañas normales
t = st.tabs(["📋 Todo", "⚠ Alertas", "📁 Vitrina", "📁 Armario"])
with t[0]:
    for _, f in df_visible.iterrows(): pintar_tarjeta(f, "all")
with t[1]:
    lim = datetime.now() + timedelta(days=45)
    for _, f in df_visible.iterrows():
        try:
            if datetime.strptime(f["Caducidad"], "%Y-%m-%d") <= lim: pintar_tarjeta(f, "warn")
        except: pass
with t[2]:
    for _, f in df_visible[df_visible["Ubicacion"] == "Medicación de vitrina"].iterrows(): pintar_tarjeta(f, "v")
with t[3]:
    for _, f in df_visible[df_visible["Ubicacion"] == "Medicación de armario"].iterrows(): pintar_tarjeta(f, "a")

# --- 6. SIDEBAR ---
with st.sidebar:
    st.write(f"Usuario: {st.session_state.user}")
    if st.button("Salir"):
        st.session_state.clear()
        st.rerun()
    if st.session_state.role == "admin":
        st.divider()
        with st.form("nuevo"):
            st.write("Añadir Medicamento")
            n = st.text_input("Nombre")
            s = st.number_input("Stock", 1)
            c = st.date_input("Caducidad")
            u = st.selectbox("Ubi", ["Medicación de vitrina", "Medicación de armario"])
            if st.form_submit_button("Guardar"):
                ws_inv.append_row([n.upper(), int(s), str(c), u])
                st.rerun()