import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import time

# --- 1. CONFIGURACIÓN Y ESTILOS ---
st.set_page_config(page_title="Gestión Médica Pro", layout="wide", page_icon="💊")

st.markdown("""
    <style>
    @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.1; } 100% { opacity: 1; } }
    .blink-icon { animation: blink 1s infinite; font-size: 1.2rem; margin-right: 5px; }
    /* Forzar texto negro en toda la tarjeta para máxima legibilidad */
    .tarjeta-med { color: black !important; border: 1px solid rgba(0,0,0,0.1); }
    .tarjeta-med b, .tarjeta-med span, .tarjeta-med small, .tarjeta-med div { color: black !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. SEGURIDAD E INACTIVIDAD (5 MINUTOS) ---
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

if "user" not in st.session_state:
    st.title("🔐 Acceso Protegido")
    st.info("La sesión se cerrará tras 5 minutos de inactividad.")
    with st.form("login_form"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if u in st.secrets["users"] and p == st.secrets["users"][u]:
                st.session_state["user"] = u
                st.session_state["role"] = st.secrets["roles"].get(u, "user")
                st.session_state["last_activity"] = time.time()
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
    st.stop()

# --- 3. CONEXIÓN A DATOS Y LOGS ---
@st.cache_resource
def conectar_datos():
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
            ws_log.append_row(["Fecha", "Usuario", "Acción", "Medicamento", "Stock Resultante"])
        return ws_inv, ws_log
    except:
        st.error("Error conectando con Google Sheets")
        return None, None

ws_inv, ws_log = conectar_datos()
rows = ws_inv.get_all_values()
headers = [h.strip() for h in rows[0]]
df = pd.DataFrame(rows[1:], columns=headers)

def registrar_log(accion, medicamento, stock_final):
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    ws_log.append_row([fecha, st.session_state.user, accion, medicamento, str(stock_final)])

# --- 4. FUNCIÓN TARJETAS (ESTILO SEMÁFORO) ---
def pintar_tarjeta(fila, idx_excel, key_suffix):
    nombre = fila.get("Nombre", "S/N")
    stock = int(fila.get("Stock", 0))
    fecha_s = fila.get("Caducidad", "2099-01-01")
    ubicacion = fila.get("Ubicacion", "General")
    
    hoy = datetime.now()
    alerta_2m = hoy + timedelta(days=60)
    bg_color, icono, aviso = "#d4edda", "", "" # Verde

    try:
        dt = datetime.strptime(fecha_s, "%Y-%m-%d")
        if dt < hoy:
            bg_color, icono, aviso = "#f8d7da", '<span class="blink-icon">⚠</span>', "<b>¡CADUCADO!</b>"
        elif dt <= alerta_2m:
            bg_color, aviso = "#fff3cd", "<b>Próximo a caducar</b>"
    except: pass

    with st.container():
        c1, c2, c3, c4 = st.columns([5, 1, 1, 1])
        c1.markdown(f"""
            <div class="tarjeta-med" style="background-color:{bg_color}; padding:12px; border-radius:8px; margin-bottom:10px;">
                <div style="display:flex; align-items:center;">{icono} 📍 <b>{ubicacion}</b></div>
                <div style="margin-top:5px;">
                    <span style="font-size:1.1rem;"><b>{nombre}</b></span> | Stock: {stock} unidades<br>
                    <small>Vence: {fecha_s} {aviso}</small>
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        # BOTÓN COGER (Para todos)
        if c2.button("💊", key=f"get_{idx_excel}_{key_suffix}", help="Retirar 1 unidad"):
            nuevo_stock = max(0, stock - 1)
            ws_inv.update_cell(idx_excel, headers.index("Stock")+1, nuevo_stock)
            registrar_log("RETIRAR", nombre, nuevo_stock)
            st.toast(f"✅ Acción registrada: {st.session_state.user} retiró {nombre}")
            time.sleep(0.5)
            st.rerun()

        # BOTONES SOLO ADMIN
        if st.session_state.role == "admin":
            if c3.button("➕", key=f"add_{idx_excel}_{key_suffix}"):
                ws_inv.update_cell(idx_excel, headers.index("Stock")+1, stock + 1)
                registrar_log("ADMIN_SUMA", nombre, stock + 1)
                st.rerun()
            if c4.button("🗑", key=f"del_{idx_excel}_{key_suffix}"):
                ws_inv.delete_rows(idx_excel)
                registrar_log("ADMIN_BORRAR", nombre, "ELIMINADO")
                st.rerun()

# --- 5. INTERFAZ PRINCIPAL ---
st.title("💊 Gestión Médica")

# BUSCADOR SELECTBOX
opciones = [""] + sorted(df["Nombre"].unique().tolist())
seleccion = st.selectbox("🔍 Buscar medicamento...", opciones)

if seleccion:
    for i, f in df[df["Nombre"] == seleccion].iterrows():
        pintar_tarjeta(f, i+2, "search")
    st.divider()

# PESTAÑAS
pestanas = ["⚠ Alertas (1 mes)", "📋 Todo", "📁 Vitrina", "📁 Armario"]
if st.session_state.role == "admin":