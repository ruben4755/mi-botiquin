import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import time

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión Médica Pro", layout="wide", page_icon="💊")

# CSS para rapidez y visibilidad en móvil
st.markdown("""
    <style>
    .stTextInput>div>div>input { font-size: 18px !important; padding: 10px !important; }
    .tarjeta-med { color: black !important; border-left: 5px solid #28a745; background: #f8f9fa; padding:15px; border-radius:8px; margin-bottom:10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; }
    </style>
""", unsafe_allow_html=True)

# --- 2. LOGIN ---
if "user" not in st.session_state:
    st.title("🔐 Acceso")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if u in st.secrets["users"] and str(p) == str(st.secrets["users"][u]):
                st.session_state["user"] = u
                st.session_state["role"] = st.secrets.get("roles", {}).get(u, "user")
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    st.stop()

# --- 3. CONEXIÓN ---
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
    return ws_inv, ws_log

ws_inv, ws_log = conectar()
data = ws_inv.get_all_values()
headers = [h.strip() for h in data[0]]
df_master = pd.DataFrame(data[1:], columns=headers)
df_master["Stock"] = pd.to_numeric(df_master["Stock"], errors='coerce').fillna(0).astype(int)
df_master["idx_excel"] = range(2, len(df_master) + 2)

# --- 4. LÓGICA DE REGISTRO ---
def registrar_log(accion, med, stock):
    fecha = datetime.now().strftime("%H:%M:%S") # Más corto para rapidez
    ws_log.append_row([fecha, st.session_state.user, accion, med, str(stock)])

# --- 5. FUNCIÓN TARJETAS (DISEÑO MÓVIL) ---
def pintar_tarjeta(fila, k):
    nombre, stock, cad, ubi, idx = fila["Nombre"], fila["Stock"], fila["Caducidad"], fila["Ubicacion"], fila["idx_excel"]
    
    with st.container():
        # Diseño en dos filas para móvil: Info arriba, botones abajo
        st.markdown(f"""
            <div class="tarjeta-med">
                <b style="font-size:18px;">{nombre}</b><br>
                <span>📦 Stock: <b>{stock}</b></span> | 📍 {ubi}<br>
                <small>📅 Vence: {cad}</small>
            </div>
        """, unsafe_allow_html=True)
        
        c1, c2, c3 = st.columns([2, 1, 1])
        if c1.button(f"💊 RETIRAR {nombre}", key=f"ret_{idx}_{k}"):
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

# --- 6. CUERPO PRINCIPAL (BUSCADOR PRIORITARIO) ---
st.title("💊 Inventario Rápido")

# BUSCADOR: Ahora fuera del lateral para evitar bloqueos de teclado en móvil
busqueda = st.text_input("🔍 BUSCAR MEDICAMENTO:", placeholder="Escribe el nombre...", help="Filtra según escribes").upper()

df_visible = df_master[df_master["Stock"] > 0].copy()

if busqueda:
    # Filtrado ultra-rápido por coincidencia de texto
    df_filtrado = df_visible[df_visible["Nombre"].str.upper().str.contains(busqueda)]
    
    if not df_filtrado.empty:
        for _, f in df_filtrado.iterrows():
            pintar_tarjeta(f, "search")
    else:
        st.error("No se encuentra el medicamento.")
    st.divider()

# Solo mostramos pestañas si no hay búsqueda activa (para no saturar la pantalla del móvil)
if not busqueda:
    tabs = st.tabs(["📋 Todo", "⚠ Alertas", "📁 Vitrina", "📁 Armario"])
    
    with tabs[0]:
        for _, f in df_visible.iterrows(): pintar_tarjeta(f, "all")
    with tabs[1]:
        limite = datetime.now() + timedelta(days=45)
        for _, f in df_visible.iterrows():
            try:
                dt_cad = datetime.strptime(f["Caducidad"], "%Y-%m-%d")
                if dt_cad <= limite: pintar_tarjeta(f, "warn")
            except: pass
    with tabs[2]:
        for _, f in df_visible[df_visible["Ubicacion"] == "Medicación de vitrina"].iterrows(): pintar_tarjeta(f, "vit")
    with tabs[3]:
        for _, f in df_visible[df_visible["Ubicacion"] == "Medicación de armario"].iterrows(): pintar_tarjeta(f, "arm")

# --- 7. SIDEBAR (Solo para gestión Admin) ---
with st.sidebar:
    st.write(f"Conectado como: *{st.session_state.user}*")
    if st.button("🚪 Cerrar Sesión"):
        st.session_state.clear()
        st.rerun()
    
    if st.session_state.role == "admin":
        st.divider()
        st.subheader("⚙ Gestión Admin")
        with st.expander("➕ Añadir Medicamento"):
            with st.form("nuevo"):
                n = st.text_input("Nombre")
                s = st.number_input("Stock", 1)
                c = st.date_input("Caducidad")
                u = st.selectbox("Ubi", ["Medicación de vitrina", "Medicación de armario"])
                if st.form_submit_button("Guardar"):
                    ws_inv.append_row([n.upper(), int(s), str(c), u])
                    st.rerun()