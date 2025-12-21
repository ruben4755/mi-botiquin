import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión Médica Pro", layout="wide", page_icon="💊")

# CSS: Definimos la estructura base de la tarjeta (el color del borde se cambia dinámicamente)
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

# --- 2. LOGIN SEGURO ---
if "user" not in st.session_state:
    st.title("🔐 Acceso al Inventario")
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
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    ws_log.append_row([fecha, st.session_state.user, accion, med, str(stock)])

def pintar_tarjeta(fila, k):
    nombre, stock, cad, ubi, idx = fila["Nombre"], fila["Stock"], fila["Caducidad"], fila["Ubicacion"], fila["idx_excel"]
    
    # LÓGICA DE COLORES DINÁMICOS
    color_borde = "#28a745"  # Verde (OK)
    texto_alerta = ""
    
    try:
        fecha_cad = datetime.strptime(cad, "%Y-%m-%d")
        hoy = datetime.now()
        if fecha_cad < hoy:
            color_borde = "#dc3545"  # Rojo (Caducado)
            texto_alerta = "⚠ CADUCADO"
        elif fecha_cad <= hoy + timedelta(days=60):
            color_borde = "#ffc107"  # Amarillo (Próximo)
            texto_alerta = "⏳ REVISAR"
    except:
        pass

    with st.container():
        # Aplicamos el color al borde izquierdo dinámicamente
        st.markdown(f"""
            <div class="tarjeta-med" style="border-left: 10px solid {color_borde};">
                <div style="display: flex; justify-content: space-between;">
                    <b style="font-size:18px;">{nombre}</b>
                    <span style="color:{color_borde}; font-weight:bold;">{texto_alerta}</span>
                </div>
                <span>📦 Stock: <b>{stock}</b></span> | 📍 <small>{ubi}</small><br>
                <small>📅 Vence: {cad}</small>
            </div>
        """, unsafe_allow_html=True)
        
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
                registrar_log("ELIMINADO", nombre, "0")
                st.rerun()

# --- 5. INTERFAZ ---
st.title("💊 Gestión de Inventario")

# Buscador Inteligente (Sin Enter)
opciones = sorted(df_visible["Nombre"].unique().tolist())
seleccion = st.selectbox("🔍 BUSCADOR RÁPIDO:", [""] + opciones, index=0)

if seleccion != "":
    fila_sel = df_visible[df_visible["Nombre"] == seleccion].iloc[0]
    st.subheader("Resultado:")
    pintar_tarjeta(fila_sel, "busq")
    st.divider()

# Pestañas
t = st.tabs(["📋 Todo", "⚠ Alertas", "📁 Vitrina", "📁 Armario"])
with t[0]:
    for _, f in df_visible.iterrows(): pintar_tarjeta(f, "all")
with t[1]:
    # Alertas de caducidad (Próximos 45 días)
    limite = datetime.now() + timedelta(days=45)
    for _, f in df_visible.iterrows():
        try:
            if