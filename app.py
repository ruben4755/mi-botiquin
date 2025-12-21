import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import calendar
import time
from st_keyup import st_keyup

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión Médica Pro", layout="wide", page_icon="💊")

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
    .stTextInput input { font-size: 18px !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. LOGIN ---
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

# --- 3. CONEXIÓN ---
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
            ws_log.append_row(["Fecha", "Usuario", "Acción", "Medicamento", "Stock Resultante"])
        return ws_inv, ws_log
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None, None

ws_inv, ws_log = iniciar_conexion()
if not ws_inv: st.stop()

# --- 4. CARGA DE DATOS ---
data = ws_inv.get_all_values()
headers = [h.strip() for h in data[0]]
df_master = pd.DataFrame(data[1:], columns=headers)
df_master["Stock"] = pd.to_numeric(df_master["Stock"], errors='coerce').fillna(0).astype(int)
df_master["idx_excel"] = range(2, len(df_master) + 2)
df_master["Nombre_Clean"] = df_master["Nombre"].str.upper().str.strip()
df_visible = df_master[df_master["Stock"] > 0].copy()

# --- 5. FUNCIÓN TARJETAS ---
def pintar_tarjeta(fila, k):
    nombre, stock, cad, ubi, idx = fila["Nombre"], fila["Stock"], fila["Caducidad"], fila["Ubicacion"], fila["idx_excel"]
    
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
            <small>Vence: {datetime.strptime(cad, "%Y-%m-%d").strftime("%m/%Y") if cad else 'S/D'}</small>
        </div>
    """, unsafe_allow_html=True)
    
    c1, c2, c3 = st.columns([2, 1, 1])
    if c1.button(f"💊 COGER", key=f"c_{idx}_{k}"):
        n = max(0, int(stock) - 1)
        ws_inv.update_cell(idx, headers.index("Stock")+1, n)
        # REGISTRO DE QUIEN COGE
        ws_log.append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state.user, "RETIRADO", nombre, str(n)])
        st.rerun()
    
    if st.session_state.role == "admin":
        if c2.button("➕", key=f"a_{idx}_{k}"):
            n_plus = int(stock) + 1
            ws_inv.update_cell(idx, headers.index("Stock")+1, n_plus)
            ws_log.append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state.user, "AÑADIDO", nombre, str(n_plus)])
            st.rerun()
        if c3.button("🗑", key=f"d_{idx}_{k}"):
            ws_inv.delete_rows(idx)
            ws_log.append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state.user, "ELIMINADO", nombre, "0"])
            st.rerun()

# --- 6. CUERPO PRINCIPAL ---
st.title("💊 Inventario Médico")

busqueda_input = st_keyup("🔍 BUSCAR MEDICAMENTO:", key="buscador_inst")
busqueda = busqueda_input.upper().strip() if busqueda_input else ""

if busqueda:
    resultados = df_visible[df_visible["Nombre_Clean"].str.contains(busqueda, na=False)]
    if not resultados.empty:
        for _, fila in resultados.iterrows():
            pintar_tarjeta(fila, "busq")
        st.divider()
    else:
        st.warning(f"No hay coincidencias para '{busqueda}'.")

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

# --- 7. SIDEBAR (ADMINISTRACIÓN Y LOGS) ---
with st.sidebar:
    st.subheader(f"👤 {st.session_state.user.capitalize()}")
    if st.button("Cerrar Sesión"):
        st.session_state.clear()
        st.rerun()
    
    if st.session_state.role == "admin":
        st.divider()
        st.subheader("➕ Añadir Stock")
        with st.form("nuevo_med", clear_on_submit=True):
            nombre_n = st.text_input("Nombre").upper()
            stock_n = st.number_input("Cantidad", min_value=1, value=1)
            col_m, col_y = st.columns(2)
            mes_n = col_m.selectbox("Mes", list(range(1, 13)), index=datetime.now().month - 1)
            anio_n = col_y.selectbox("Año", list(range(datetime.now().year, datetime.now().year + 10)))
            ubi_n = st.selectbox("Ubicación", ["Medicación de vitrina", "Medicación de armario"])
            if st.form_submit_button("Guardar"):
                if nombre_n:
                    ultimo_dia = calendar.monthrange(anio_n, mes_n)[1]
                    fecha_interna = f"{anio_n}-{mes_n:02d}-{ultimo_dia:02d}"
                    ws_inv.append_row([nombre_n.strip(), int(stock_n), fecha_interna, ubi_n])
                    ws_log.append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state.user, "ALTA", nombre_n.strip(), str(stock_n)])
                    st.success("Guardado")
                    time.sleep(1)
                    st.rerun()

        # --- SECCIÓN EXCLUSIVA ADMIN: REGISTRO DE ACTIVIDAD ---
        st.divider()
        st.subheader("📜 Historial de Uso")
        try:
            log_data = ws_log.get_all_values()
            if len(log_data) > 1:
                df_logs = pd.DataFrame(log_data[1:], columns=log_data[0])
                # Mostrar los últimos 20 movimientos, los más recientes primero
                st.dataframe(df_logs.iloc[::-1].head(20), hide_index=True)
            else:
                st.info("No hay registros aún.")
        except:
            st.error("No se pudo cargar el historial.")