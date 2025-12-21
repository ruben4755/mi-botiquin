import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Gestión Médica Pro", layout="wide", page_icon="💊")

# Estilos CSS
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

# --- 2. CONTROL DE ACCESO (LOGIN) ---
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False

if not st.session_state["autenticado"]:
    st.title("🔐 Acceso al Sistema")
    with st.form("login_form"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if "users" in st.secrets and u in st.secrets["users"] and str(p) == str(st.secrets["users"][u]):
                st.session_state["autenticado"] = True
                st.session_state["user"] = u
                st.session_state["role"] = st.secrets.get("roles", {}).get(u, "user")
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

# --- 3. CONEXIÓN A DATOS (SOLO TRAS LOGIN) ---
@st.cache_resource
def obtener_conexion():
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

ws_inv, ws_log = obtener_conexion()

if ws_inv is None:
    st.warning("Error al conectar con Google Sheets. Revisa tus Secrets.")
    st.stop()

# Carga de datos fresca
data = ws_inv.get_all_values()
if not data:
    st.error("El Excel está vacío.")
    st.stop()

headers = [h.strip() for h in data[0]]
df_master = pd.DataFrame(data[1:], columns=headers)
df_master["Stock"] = pd.to_numeric(df_master["Stock"], errors='coerce').fillna(0).astype(int)
df_master["idx_excel"] = range(2, len(df_master) + 2)
df_visible = df_master[df_master["Stock"] > 0].copy()

# --- 4. FUNCIONES DE INTERFAZ ---
def registrar_log(accion, med, stock):
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    ws_log.append_row([fecha, st.session_state.user, accion, med, str(stock)])

def pintar_tarjeta(fila, k):
    nombre, stock, cad, ubi, idx = fila["Nombre"], fila["Stock"], fila["Caducidad"], fila["Ubicacion"], fila["idx_excel"]
    
    color_borde = "#28a745"
    texto_alerta = ""
    
    try:
        fecha_cad = datetime.strptime(cad, "%Y-%m-%d")
        hoy = datetime.now()
        if fecha_cad < hoy:
            color_borde = "#dc3545"
            texto_alerta = "⚠ CADUCADO"
        elif fecha_cad <= hoy + timedelta(days=60):
            color_borde = "#ffc107"
            texto_alerta = "⏳ REVISAR"
    except:
        pass

    with st.container():
        st.markdown(f"""
            <div class="tarjeta-med" style="border-left: 10px solid {color_borde};">
                <div style="display: flex; justify-content: space-between;">
                    <b style="font-size:18px;">{nombre}</b>
                    <span style="color:{color_borde}; font-weight:bold;">{texto_alerta}</span>
                </div>
                <span>Stock: <b>{stock}</b></span> | <small>{ubi}</small><br>
                <small>Vence: {cad}</small>
            </div>
        """, unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns([2, 1, 1])
        if c1.button(f"💊 COGER", key=f"btn_{idx}_{k}"):
            nuevo_stock = max(0, int(stock) - 1)
            ws_inv.update_cell(idx, headers.index("Stock")+1, nuevo_stock)
            registrar_log("RETIRADO", nombre, nuevo_stock)
            st.rerun()
        
        if st.session_state.role == "admin":
            if c2.button("➕", key=f"add_{idx}_{k}"):
                ws_inv.update_cell(idx, headers.index("Stock")+1, int(stock) + 1)
                st.rerun()
            if c3.button("🗑", key=f"del_{idx}_{k}"):