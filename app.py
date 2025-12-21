import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import time

# ==========================================
# 1. CONFIGURACIÓN Y TIEMPO (5 MINUTOS)
# ==========================================
st.set_page_config(page_title="Gestión Médica Pro", layout="wide", page_icon="💊")

TIEMPO_INACTIVIDAD = 300 # 5 minutos en segundos

def logout():
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# Si el usuario ya entró, vigilamos el reloj
if "user" in st.session_state:
    ahora = time.time()
    if ahora - st.session_state.get("last_activity", ahora) > TIEMPO_INACTIVIDAD:
        logout()
    st.session_state["last_activity"] = ahora

# Estilos CSS (Texto siempre negro y parpadeo)
st.markdown("""
    <style>
    @keyframes blink { 0% { opacity: 1; } 50% { opacity: 0.1; } 100% { opacity: 1; } }
    .blink-icon { animation: blink 1s infinite; font-size: 1.2rem; margin-right: 5px; }
    .tarjeta-med { color: black !important; border: 1px solid rgba(0,0,0,0.1); }
    .tarjeta-med * { color: black !important; }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. LOGIN Y PERMISOS (ADMIN/USER)
# ==========================================
if "user" not in st.session_state:
    st.title("🔐 Acceso")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if u in st.secrets["users"] and p == st.secrets["users"][u]:
                st.session_state["user"] = u
                # Aquí sacamos el rol de los secretos (admin o user)
                st.session_state["role"] = st.secrets["roles"].get(u, "user")
                st.session_state["last_activity"] = time.time()
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

# ==========================================
# 3. CONEXIÓN AL EXCEL Y REGISTRO
# ==========================================
@st.cache_resource
def conectar():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    sh = client.open_by_url(st.secrets["url_excel"])
    ws_inv = sh.get_worksheet(0)
    # Si no existe la pestaña "Registro", la creamos
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

# Función para anotar quién coge qué
def registrar_log(accion, med, stock):
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    ws_log.append_row([fecha, st.session_state.user, accion, med, str(stock)])

# ==========================================
# 4. LAS TARJETAS (SEMÁFORO DE COLORES)
# ==========================================
def pintar_tarjeta(fila, idx_excel, key_suffix):
    nombre = fila["Nombre"]
    stock = int(fila["Stock"])
    caducidad = fila["Caducidad"]
    ubi = fila["Ubicacion"]
    
    # Lógica de colores
    hoy = datetime.now()
    limite_2meses = hoy + timedelta(days=60)
    bg, icono, nota = "#d4edda", "", "" # Verde

    try:
        dt = datetime.strptime(caducidad, "%Y-%m-%d")
        if dt < hoy:
            bg, icono, nota = "#f8d7da", '<span class="blink-icon">⚠</span>', "<b>¡CADUCADO!</b>"
        elif dt <= limite_2meses:
            bg, nota = "#fff3cd", "<b>Caduca pronto</b>"
    except: pass

    with st.container():
        c1, c2, c3, c4 = st.columns([5, 1, 1, 1])
        c1.markdown(f"""
            <div class="tarjeta-med" style="background:{bg}; padding:10px; border-radius:8px; margin-bottom:10px;">
                {icono} 📍 <b>{ubi}</b><br>
                <b>{nombre}</b> | Stock: {stock}<br>
                <small>Vence: {caducidad} {nota}</small>
            </div>
        """, unsafe_allow_html=True)
        
        # BOTÓN COGER (Para todos)
        if c2.button("💊", key=f"get_{idx_excel}_{key_suffix}"):
            n_stock = max(0, stock - 1)
            ws_inv.update_cell(idx_excel, headers.index("Stock")+1, n_stock)
            registrar_log("RETIRAR", nombre, n_stock)
            st.toast(f"Registrado: {st.session_state.user} cogió {nombre}")
            time.sleep(0.5)
            st.rerun()

        # BOTONES SOLO ADMIN
        if st.session_state.role == "admin":
            if c3.button("➕", key=f"add_{idx_excel}_{key_suffix}"):
                ws_inv.update_cell(idx_excel, headers.index("Stock")+1, stock + 1)
                st.rerun()
            if c4.button("🗑", key=f"del_{idx_excel}_{key_suffix}"):
                ws_inv.delete_rows(idx_excel)
                st.rerun()

# ==========================================
# 5. EL BUSCADOR Y LAS PESTAÑAS (REGISTRO SOLO ADMIN)
# ==========================================
st.title("💊 Inventario Médico")

opcion = st.selectbox("🔍 Buscar medicamento...", [""] + sorted(df["Nombre"].unique().tolist()))
if opcion:
    for i, f in df[df["Nombre"] == opcion].iterrows():
        pintar_tarjeta(f, i+2, "busc")
    st.divider()

# Lista de pestañas: El Registro solo se añade si eres ADMIN
lista_tabs = ["⚠ Alertas (1 mes)", "📋 Todo", "📁 Vitrina", "📁 Armario"]
if st.session_state.role == "admin":
    lista_tabs.append("📜 Registro")

tabs = st.tabs(lista_tabs)

with tabs[0]: # Alertas
    limite_1mes = datetime.now() + timedelta(days=30)
    for i, f in df.iterrows():
        try:
            if datetime.strptime(f["Caducidad"], "%Y-%m-%d") <= limite_1mes:
                pintar_tarjeta(f, i+2, "alt")
        except: pass

with tabs[1]: # Todo
    for i, f in df.iterrows(): pintar_tarjeta(f, i+2, "all")

with tabs[2]: # Vitrina
    for i, f in df[df["Ubicacion"] == "Medicación de vitrina"].iterrows(): pintar_tarjeta(f, i+2, "vit")

with tabs[3]: # Armario
    for i, f in df[df["Ubicacion"] == "Medicación de armario"].iterrows(): pintar_tarjeta(f, i+2, "arm")

# SOLO ADMIN: Ver la tabla de quién cogió qué
if st.session_state.role == "admin":
    with tabs[4]:
        st.subheader("🕵 Historial de movimientos")
        log_records = ws_log.get_all_records()
        if log_records:
            st.table(pd.DataFrame(log_records).iloc[::-1])
        else:
            st.write("Aún no hay registros.")

with st.sidebar:
    st.write(f"Usuario: *{st.session_state.user}* ({st.session_state.role})")
    if st.button("Cerrar Sesión"): logout()