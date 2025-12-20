import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import time

# --- 1. CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Inventario con Auto-Cierre", layout="wide", page_icon="🛡")

st.markdown("""
    <style>
    @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.1; } 100% { opacity: 1; } }
    .blink-icon { animation: blink 1s infinite; font-size: 1.2rem; margin-right: 5px; }
    .tarjeta-med { color: black !important; border: 1px solid rgba(0,0,0,0.1); }
    .tarjeta-med b, .tarjeta-med span, .tarjeta-med small { color: black !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. GESTIÓN DE SEGURIDAD E INACTIVIDAD ---
# Definimos el tiempo de inactividad (15 minutos = 900 segundos)
TIEMPO_INACTIVIDAD = 900 

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# Lógica de temporizador
if "user" in st.session_state:
    ahora = time.time()
    ultima_actividad = st.session_state.get("last_activity", ahora)
    
    # Si el tiempo transcurrido es mayor al límite, cerramos sesión
    if ahora - ultima_actividad > TIEMPO_INACTIVIDAD:
        logout()
    else:
        # Si hay actividad, actualizamos el marcador de tiempo
        st.session_state["last_activity"] = ahora

# Pantalla de Login
if "user" not in st.session_state:
    st.title("🔐 Control de Acceso")
    st.info("La sesión se cerrará automáticamente tras 15 minutos de inactividad.")
    with st.form("login_form"):
        u = st.text_input("Nombre de Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Acceder"):
            if u in st.secrets["users"] and p == st.secrets["users"][u]:
                st.session_state["user"] = u
                st.session_state["last_activity"] = time.time() # Iniciar reloj
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

# --- 3. CONEXIÓN A DATOS ---
@st.cache_resource
def conectar_google():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except:
        st.error("Error de conexión con la base de datos.")
        return None

def cargar_datos():
    client = conectar_google()
    if client:
        try:
            sh = client.open_by_url(st.secrets["url_excel"])
            worksheet = sh.get_worksheet(0)
            rows = worksheet.get_all_values()
            return rows, worksheet
        except:
            st.error("Error de acceso al Excel.")
    return None, None

rows, worksheet = cargar_datos()

if rows and len(rows) > 0:
    headers = [h.strip() for h in rows[0]]
    df = pd.DataFrame(rows[1:], columns=headers)
    col_nom = next((c for c in df.columns if "Nom" in c), "Nombre")
    col_stock = next((c for c in df.columns if "Sto" in c or "Cant" in c), "Stock")
    col_cad = next((c for c in df.columns if "Cad" in c or "Fec" in c), "Caducidad")
    col_ubi = next((c for c in df.columns if "Ubi" in c), "Ubicacion")
else:
    st.warning("⚠ No hay datos.")
    st.stop()

# --- 4. FUNCIONES DE INTERFAZ ---
def pintar_tarjeta(fila, idx_excel, key_suffix):
    nombre, stock, fecha_s, ubicacion = fila[col_nom], fila[col_stock], fila[col_cad], fila[col_ubi]
    hoy = datetime.now()
    alerta_2meses = hoy + timedelta(days=60)
    bg_color, texto_aviso, icono_alerta = "#d4edda", "", ""

    try:
        dt = datetime.strptime(fecha_s, "%Y-%m-%d")
        if dt < hoy:
            bg_color, icono_alerta = "#f8d7da", '<span class="blink-icon">⚠</span>'
            texto_aviso = "<b>¡CADUCADO!</b>"
        elif dt <= alerta_2meses:
            bg_color, texto_aviso = "#fff3cd", "<b>Próximo a caducar</b>"
    except: pass

    with st.container():
        c1, c2, c3, c4 = st.columns([5, 1, 1, 1])
        c1.markdown(f"""
            <div class="tarjeta-med" style="background-color:{bg_color}; padding:12px; border-radius:8px; margin-bottom:10px;">
                <div style="display:flex; align-items:center;">{icono_alerta} 📍 <b>{ubicacion}</b></div>
                <div style="margin-top:5px;"><span style="font-size:1.1rem;"><b>{nombre}</b></span> | Stock: {stock} <br>
                <small>Vence: {fecha_s} {texto_aviso}</small></div>
            </div>
        """, unsafe_allow_html=True)
        
        # Al pulsar cualquier botón, el temporizador se reinicia automáticamente por el flujo de Streamlit
        if c2.button("＋", key=f"p_{idx_excel}_{key_suffix}"):
            worksheet.update_cell(idx_excel, headers.index(col_stock)+1, int(stock)+1)
            st.rerun()
        if c3.button("－", key=f"m_{idx_excel}_{key_suffix}"):
            worksheet.update_cell(idx_excel, headers.index(col_stock)+1, max(0, int(stock)-1))
            st.rerun()
        if c4.button("🗑", key=f"d_{idx_excel}_{key_suffix}"):
            worksheet.delete_rows(idx_excel)
            st.rerun()

# --- 5. CUERPO DE LA APP ---
with st.sidebar:
    st.write(f"👤 Usuario: *{st.session_state.user}*")
    if st.button("🚪 Cerrar Sesión Ahora"): logout()
    st.divider()
    st.header("➕ Nuevo Registro")
    with st.form("add_safe", clear_on_submit=True):
        n = st.text_input("Medicamento")
        s = st.number_input("Stock", min_value=0)
        c = st.date_input("Caducidad")
        u = st.selectbox("Ubicación", ["Medicación de vitrina", "Medicación de armario"])
        if st.form_submit_button("Guardar"):
            if n:
                worksheet.append_row([n.capitalize(), int(s), str(c), u, st.session_state.user])
                st.rerun()

st.title("💊 Gestión de Medicación")

# Buscador
sel = st.selectbox("🔍 Buscar por nombre...", [""] + sorted(df[col_nom].unique().tolist()))
if sel:
    for i, f in df[df[col_nom] == sel].iterrows():
        pintar_tarjeta(f, i+2, "search")
    st.divider()

# Pestañas
t_alert, t_all, t_vit, t_arm = st.tabs(["⚠ Alertas (1 Mes)", "📋 Todo", "📁 Vitrina", "📁 Armario"])

with t_alert:
    hoy = datetime.now()
    limite = hoy + timedelta(days=30)
    items = 0
    for i, f in df.iterrows():
        try:
            if datetime.strptime(f[col_cad], "%Y-%m-%d") <= limite:
                pintar_tarjeta(f, i+2, "alert")
                items += 1
        except: pass
    if items == 0: st.success("No hay alertas de 1 mes.")

with t_all:
    for i, f in df.iterrows(): pintar_tarjeta(f, i+2, "all")

with t_vit:
    for i, f in df[df[col_ubi] == "Medicación de vitrina"].iterrows(): pintar_tarjeta(f, i+2, "vit")

with t_arm:
    for i, f in df[df[col_ubi] == "Medicación de armario"].iterrows(): pintar_tarjeta(f, i+2, "arm")