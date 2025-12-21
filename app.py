import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import time

# --- 1. CONFIGURACIÓN Y TIEMPO (5 MINUTOS) ---
st.set_page_config(page_title="Gestión Médica Pro", layout="wide", page_icon="💊")
TIEMPO_INACTIVIDAD = 300 

def logout():
    for key in list(st.session_state.keys()): 
        del st.session_state[key]
    st.rerun()

if "user" in st.session_state:
    ahora = time.time()
    if ahora - st.session_state.get("last_activity", ahora) > TIEMPO_INACTIVIDAD:
        logout()
    st.session_state["last_activity"] = ahora

st.markdown("""
    <style>
    @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.1; } 100% { opacity: 1; } }
    .blink-icon { animation: blink 1s infinite; font-size: 1.2rem; margin-right: 5px; }
    .tarjeta-med { color: black !important; border: 1px solid rgba(0,0,0,0.1); }
    .tarjeta-med * { color: black !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. LOGIN Y ROLES ---
if "user" not in st.session_state:
    st.title("🔐 Acceso")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if u in st.secrets["users"] and p == st.secrets["users"][u]:
                st.session_state["user"] = u
                st.session_state["role"] = st.secrets["roles"].get(u, "user")
                st.session_state["last_activity"] = time.time()
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

# --- 3. CONEXIÓN A GOOGLE SHEETS ---
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
        ws_log.append_row(["Fecha", "Usuario", "Acción", "Medicamento", "Stock Final"])
    return ws_inv, ws_log

ws_inv, ws_log = conectar()
rows = ws_inv.get_all_values()
headers = [h.strip() for h in rows[0]]
df = pd.DataFrame(rows[1:], columns=headers)

def registrar_log(accion, med, stock):
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    ws_log.append_row([fecha, st.session_state.user, accion, med, str(stock)])

# --- 4. FUNCIÓN TARJETAS ---
def pintar_tarjeta(fila, idx_excel, key_suffix):
    nombre = fila["Nombre"]
    stock = int(fila["Stock"])
    caducidad = fila["Caducidad"]
    ubi = fila["Ubicacion"]
    es_admin = st.session_state.role == "admin"
    
    hoy = datetime.now()
    limite_2m = hoy + timedelta(days=60)
    bg, icono, nota = "#d4edda", "", ""

    try:
        dt = datetime.strptime(caducidad, "%Y-%m-%d")
        if dt < hoy: bg, icono, nota = "#f8d7da", '<span class="blink-icon">⚠</span>', "<b>¡CADUCADO!</b>"
        elif dt <= limite_2m: bg, nota = "#fff3cd", "<b>Caduca pronto</b>"
    except: pass

    with st.container():
        c1, c2, c3, c4, c5 = st.columns([4, 1, 1, 1, 1])
        c1.markdown(f"""<div class="tarjeta-med" style="background:{bg}; padding:10px; border-radius:8px; margin-bottom:10px;">
                    {icono} 📍 <b>{ubi}</b><br><b>{nombre}</b> | Stock: {stock}<br>
                    <small>Vence: {caducidad} {nota}</small></div>""", unsafe_allow_html=True)
        
        # BOTÓN COGER (Para todos)
        if c2.button("💊", key=f"get_{idx_excel}_{key_suffix}", help="Coger 1"):
            n_stock = max(0, stock - 1)
            ws_inv.update_cell(idx_excel, headers.index("Stock")+1, n_stock)
            registrar_log("RETIRAR", nombre, n_stock)
            st.rerun()

        # BOTONES AJUSTE (Visibles para todos)
        if c3.button("➕", key=f"add_{idx_excel}_{key_suffix}"):
            ws_inv.update_cell(idx_excel, headers.index("Stock")+1, stock + 1)
            registrar_log("AJUSTE_SUMA", nombre, stock + 1)
            st.rerun()
            
        if c4.button("➖", key=f"min_{idx_excel}_{key_suffix}"):
            n_stock = max(0, stock - 1)
            ws_inv.update_cell(idx_excel, headers.index("Stock")+1, n_stock)
            registrar_log("AJUSTE_RESTA", nombre, n_stock)
            st.rerun()

        # BOTÓN BORRAR (Solo Admin)
        if es_admin:
            if c5.button("🗑", key=f"del_{idx_excel}_{key_suffix}"):
                ws_inv.delete_rows(idx_excel)
                registrar_log("BORRADO", nombre, "ELIMINADO")
                st.rerun()

# --- 5. INTERFAZ PRINCIPAL ---
st.title("💊 Inventario Médico")

opcion = st.selectbox("🔍 Buscar medicamento...", [""] + sorted(df["Nombre"].unique().tolist()))
if opcion:
    for i, f in df[df["Nombre"] == opcion].iterrows():
        pintar_tarjeta(f, i+2, "busc")
    st.divider()

lista_tabs = ["⚠ Alertas", "📋 Todo", "📁 Vitrina", "📁 Armario"]
if st.session_state.role == "admin": 
    lista_tabs.append("📜 Registro")
tabs =