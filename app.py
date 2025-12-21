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
    .tarjeta-med { color: black !important; border: 1px solid rgba(0,0,0,0.1); }
    .tarjeta-med * { color: black !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. LOGIN ---
if "user" not in st.session_state:
    st.title("🔐 Acceso")
    if "users" not in st.secrets:
        st.error("⚠ Error: No se encuentra la sección [users] en Secrets.")
        st.stop()

    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            lista_usuarios = st.secrets["users"]
            if u in lista_usuarios and str(p) == str(lista_usuarios[u]):
                st.session_state["user"] = u
                rol_asignado = st.secrets.get("roles", {}).get(u, "user")
                st.session_state["role"] = rol_asignado
                st.session_state["last_activity"] = time.time()
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
    st.stop()

# --- 3. INACTIVIDAD (5 MIN) ---
TIEMPO_INACTIVIDAD = 300
if time.time() - st.session_state.get("last_activity", time.time()) > TIEMPO_INACTIVIDAD:
    for key in list(st.session_state.keys()): del st.session_state[key]
    st.rerun()
st.session_state["last_activity"] = time.time()

# --- 4. CONEXIÓN ---
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
rows = ws_inv.get_all_values()
headers = [h.strip() for h in rows[0]]
df_completo = pd.DataFrame(rows[1:], columns=headers)

# Filtro visual: Solo stock > 0
df_completo["Stock"] = pd.to_numeric(df_completo["Stock"], errors='coerce').fillna(0).astype(int)
df = df_completo[df_completo["Stock"] > 0].copy()

def registrar_log(accion, med, stock):
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    ws_log.append_row([fecha, st.session_state.user, accion, med, str(stock)])

# --- 5. FUNCIÓN TARJETAS ---
def pintar_tarjeta(fila, idx_excel, key_suffix):
    nombre = fila["Nombre"]
    stock = int(fila["Stock"])
    caducidad = fila["Caducidad"]
    ubi = fila["Ubicacion"]
    es_admin = st.session_state.get("role") == "admin"
    
    bg = "#d4edda"
    try:
        dt = datetime.strptime(caducidad, "%Y-%m-%d")
        if dt < datetime.now(): bg = "#f8d7da"
        elif dt <= datetime.now() + timedelta(days=60): bg = "#fff3cd"
    except: pass

    with st.container():
        c1, c2, c3, c4, c5 = st.columns([4, 1, 1, 1, 1])
        c1.markdown(f'<div class="tarjeta-med" style="background:{bg}; padding:10px; border-radius:8px; margin-bottom:10px;"><b>{nombre}</b> | Stock: {stock}<br><small>{ubi} - Vence: {caducidad}</small></div>', unsafe_allow_html=True)
        
        # BOTÓN COGER (Para todos) -> LOG: RETIRADO
        if c2.button("💊", key=f"p_{idx_excel}_{key_suffix}"):
            n = max(0, stock - 1)
            ws_inv.update_cell(idx_excel, headers.index("Stock")+1, n)
            registrar_log("RETIRADO", nombre, n)
            st.rerun()

        if es_admin:
            if c3.button("➕", key=f"a_{idx_excel}_{key_suffix}"):
                ws_inv.update_cell(idx_excel, headers.index("Stock")+1, stock + 1)
                registrar_log("AÑADIDO (ADMIN)", nombre, stock + 1)
                st.rerun()
            if c4.button("➖", key=f"m_{idx_excel}_{key_suffix}"):
                n = max(0, stock - 1)
                ws_inv.update_cell(idx_excel, headers.index("Stock")+1, n)
                registrar_log("QUITADO (ADMIN)", nombre, n)
                st.rerun()
            if c5.button("🗑", key=f"d_{idx_excel}_{key_suffix}"):
                ws_inv.delete_rows(idx_excel)
                registrar_log("ELIMINADO", nombre, "X")
                st.rerun()

# --- 6. INTERFAZ ---
st.title("💊 Inventario Médico")

# BUSCADOR DINÁMICO
# El selectbox permite escribir y va filtrando las opciones automáticamente
opciones_busqueda = sorted(df["Nombre"].unique().tolist())
busqueda = st.selectbox(
    "🔍 Escribe el nombre del medicamento para buscar...", 
    [""] + opciones_busqueda,
    help="Empieza a escribir y la lista se filtrará sola"
)

if busqueda:
    # Mostramos el resultado de la búsqueda
    for i, f in df[df["Nombre"] == busqueda].iterrows():
        # Calculamos el índice real en el Excel
        # i es el índice del dataframe original antes de filtrar
        # Si no coincide exactamente, buscamos la fila en df_completo
        idx_excel = df_completo[df_completo['Nombre'] == f['Nombre']].index[0] + 2
        pintar_tarjeta(f, idx_excel, "busqueda")
    st.divider()

# Pestañas
p_nombres = ["⚠ Alertas", "📋 Todo", "📁 Vitrina", "📁 Armario"]
if st.session_state.get("role") == "admin": p_nombres.append("📜 Registro")
t = st.tabs(p_nombres)

with t[0]: # Alertas (Próximas caducidades)
    l1 = datetime.now() + timedelta(days=30)
    for i, f in df.iterrows():
        try:
            if datetime.strptime(f["Caducidad"], "%Y-%m-%d") <= l1:
                idx_excel = df_completo[df_completo['Nombre'] == f['Nombre']].index[0] + 2
                pintar_tarjeta(f, idx_excel, "alert")
        except: pass

with t[1]: # Todo (Disponible)
    for i, f in df.iterrows():
        idx_excel = df_completo[df_completo['Nombre'] == f['Nombre']].index[0] + 2
        pintar_tarjeta(f, idx_excel, "all")

with t[2]: # Vitrina
    for i, f in df[df["Ubicacion"] == "Medicación de vitrina"].iterrows():
        idx_excel = df_completo[df_completo['Nombre'] == f['Nombre']].index[0] + 2
        pintar_tarjeta(f, idx_excel, "vit")

with t[3]: # Armario
    for i, f in df[df["Ubicacion"] == "Medicación de armario"].iterrows():
        idx_excel = df_completo[df_completo['Nombre'] == f['Nombre']].index[0] + 2
        pintar_tarjeta(f, idx_excel, "arm")

if st.session_state.get("role") == "admin":
    with t[-1]:
        st.subheader("🕵 Historial de movimientos")
        logs = ws_log.get_all_records()
        if logs:
            st.table(pd.DataFrame(logs).iloc[::-1])

with st.sidebar:
    st.write(f"Usuario: *{st.session_state.user}*")
    if st.button("🚪 Salir"):
        for key in list(st.session_state.keys()): del st.session_state[key]
        st.rerun()
    
    if st.session_state.get("role") == "admin":
        st.divider()
        st.subheader("➕ Nuevo Medicamento")
        with st.form("nuevo", clear_on_submit=True):
            n = st.text_input("Nombre")
            s = st.number_input("Stock Inicial", min_value=1)
            c = st.date_input("Caducidad")
            u = st.selectbox("Ubicación", ["Medicación de vitrina", "Medicación de armario"])
            if st.form_submit_button("Añadir"):
                if n:
                    ws_inv.append_row([n.capitalize(), int(s), str(c), u])
                    registrar_log("NUEVO REGISTRO", n.capitalize(), s)
                    st.rerun()