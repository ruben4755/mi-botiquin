import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión Médica Pro", layout="wide", page_icon="💊")

# Estilos CSS corregidos
st.markdown("""
    <style>
    .tarjeta-med { 
        color: black !important; 
        background: #f8f9fa; 
        padding: 15px; 
        border-radius: 8px; 
        margin-bottom: 10px; 
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .stSelectbox div[data-baseweb="select"] { font-size: 18px !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. LOGIN (BLOQUEO TOTAL) ---
if "logueado" not in st.session_state:
    st.session_state["logueado"] = False

if not st.session_state["logueado"]:
    st.title("🔐 Acceso")
    with st.form("login_f"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if "users" in st.secrets and u in st.secrets["users"] and str(p) == str(st.secrets["users"][u]):
                st.session_state["logueado"] = True
                st.session_state["user"] = u
                st.session_state["role"] = st.secrets.get("roles", {}).get(u, "user")
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

# --- 3. CONEXIÓN (SOLO SI ESTÁ LOGUEADO) ---
@st.cache_resource
def iniciar_conexion():
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

ws_inv, ws_log = iniciar_conexion()
if not ws_inv: st.stop()

# --- 4. CARGA DE DATOS ---
try:
    data = ws_inv.get_all_values()
    headers = [h.strip() for h in data[0]]
    df_master = pd.DataFrame(data[1:], columns=headers)
    
    # Asegurar que las columnas existen
    columnas_necesarias = ["Nombre", "Stock", "Caducidad", "Ubicacion"]
    for col in columnas_necesarias:
        if col not in df_master.columns:
            st.error(f"Falta la columna '{col}' en tu Excel. Revisa los nombres.")
            st.stop()

    df_master["Stock"] = pd.to_numeric(df_master["Stock"], errors='coerce').fillna(0).astype(int)
    df_master["idx_excel"] = range(2, len(df_master) + 2)
    df_visible = df_master[df_master["Stock"] > 0].copy()
except Exception as e:
    st.error(f"Error procesando datos: {e}")
    st.stop()

# --- 5. FUNCIONES ---
def pintar_tarjeta(fila, k):
    nombre, stock, cad, ubi, idx = fila["Nombre"], fila["Stock"], fila["Caducidad"], fila["Ubicacion"], fila["idx_excel"]
    
    # Lógica de colores (Borde dinámico)
    color_b = "#28a745"
    alerta = ""
    try:
        f_cad = datetime.strptime(cad, "%Y-%m-%d")
        if f_cad < datetime.now():
            color_b = "#dc3545"
            alerta = "⚠ CADUCADO"
        elif f_cad <= datetime.now() + timedelta(days=60):
            color_b = "#ffc107"
            alerta = "⏳ REVISAR"
    except: pass

    st.markdown(f"""
        <div class="tarjeta-med" style="border-left: 10px solid {color_b};">
            <div style="display:flex; justify-content:space-between;">
                <b>{nombre}</b> <span style="color:{color_b}; font-weight:bold;">{alerta}</span>
            </div>
            <span>Stock: {stock}</span> | <small>{ubi}</small><br>
            <small>Vence: {cad}</small>
        </div>
    """, unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([2, 1, 1])
    if c1.button(f"💊 COGER", key=f"c_{idx}_{k}"):
        n = max(0, int(stock) - 1)
        ws_inv.update_cell(idx, headers.index("Stock")+1, n)
        ws_log.append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state.user, "RETIRADO", nombre, str(n)])
        st.rerun()
    
    if st.session_state.role == "admin":
        if c2.button("➕", key=f"a_{idx}_{k}"):
            ws_inv.update_cell(idx, headers.index("Stock")+1, int(stock) + 1)
            st.rerun()
        if c3.button("🗑", key=f"d_{idx}_{k}"):
            ws_inv.delete_rows(idx)
            st.rerun()

# --- 6. INTERFAZ ---
st.title("💊 Inventario Médico")

# Buscador Rápido (Funciona en móvil)
opciones = sorted(df_visible["Nombre"].unique().tolist())
sel = st.selectbox("🔍 BUSCAR:", [""] + opciones)

if sel:
    pintar_tarjeta(df_visible[df_visible["Nombre"] == sel].iloc[0], "busq")
    st.divider()

t = st.tabs(["📋 Todo", "⚠ Alertas", "📁 Vitrina", "📁 Armario"])
with t[0]:
    for _, f in df_visible.iterrows(): pintar_tarjeta(f, "all")
with t[1]:
    limite = datetime.now() + timedelta(days=60)
    for _, f in df_visible.iterrows():
        try:
            if datetime.strptime(f["Caducidad"], "%Y-%m-%d") <= limite: pintar_tarjeta(f, "w")
        except: pass
with t[2]:
    for _, f in df_visible[df_visible["Ubicacion"] == "Medicación de vitrina"].iterrows(): pintar_tarjeta(f, "v")
with t[3]:
    for _, f in df_visible[df_visible["Ubicacion"] == "Medicación de armario"].iterrows(): pintar_tarjeta(f, "ar")

with st.sidebar:
    st.write(f"Usuario: {st.session_state.user}")
    if st.button("Salir"):
        st.session_state.clear()
        st.rerun()