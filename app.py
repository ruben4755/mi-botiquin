import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Inventario Color-Coded", layout="wide", page_icon="💊")

# Estilo para el parpadeo del símbolo de alerta
st.markdown("""
    <style>
    @keyframes blink {
        0% { opacity: 1; }
        50% { opacity: 0.1; }
        100% { opacity: 1; }
    }
    .blink-icon {
        animation: blink 1s infinite;
        font-size: 1.2rem;
        margin-right: 5px;
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_resource
def obtener_cliente():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except: return None

def cargar_datos_vivos():
    try:
        client = obtener_cliente()
        sh = client.open_by_url(st.secrets["url_excel"])
        worksheet = sh.get_worksheet(0)
        rows = worksheet.get_all_values()
        return rows, worksheet
    except: return None, None

# --- 2. LOGIN ---
if "user" not in st.session_state:
    st.title("🔒 Acceso")
    with st.form("login"):
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if u in st.secrets["users"] and p == st.secrets["users"][u]:
                st.session_state["user"] = u
                st.rerun()
    st.stop()

rows, worksheet = cargar_datos_vivos()

if rows:
    headers = [str(h).strip() for h in rows[0]]
    df = pd.DataFrame(rows[1:], columns=headers)
    col_nom = next((c for c in df.columns if "Nom" in c), "Nombre")
    col_stock = next((c for c in df.columns if "Sto" in c or "Cant" in c), "Stock")
    col_cad = next((c for c in df.columns if "Cad" in c or "Fec" in c), "Caducidad")
    col_ubi = next((c for c in df.columns if "Ubi" in c), "Ubicacion")
else:
    st.stop()

# --- 3. FUNCIÓN TARJETAS CON COLORES SEMÁFORO ---
def pintar_tarjeta(fila, idx_excel, key_suffix):
    nombre = fila[col_nom]
    stock = fila[col_stock]
    fecha_s = fila[col_cad]
    ubicacion = fila[col_ubi]
    
    hoy = datetime.now()
    alerta_2meses = hoy + timedelta(days=60)
    
    # Valores por defecto (Verde)
    bg_color = "#d4edda"  # Verde claro
    texto_aviso = ""
    icono_alerta = ""

    try:
        dt = datetime.strptime(fecha_s, "%Y-%m-%d")
        if dt < hoy:
            # ROJO y parpadeo
            bg_color = "#f8d7da"
            icono_alerta = '<span class="blink-icon">⚠</span>'
            texto_aviso = "<b>¡CADUCADO!</b>"
        elif dt <= alerta_2meses:
            # AMARILLO
            bg_color = "#fff3cd"
            texto_aviso = "<b>Próximo a caducar (2 meses)</b>"
    except:
        pass

    with st.container():
        c1, c2, c3, c4 = st.columns([5, 1, 1, 1])
        info = f"""
        <div style="background-color:{bg_color}; padding:12px; border-radius:8px; color:#155724; border: 1px solid rgba(0,0,0,0.1); margin-bottom:10px;">
            <div style="display:flex; align-items:center;">
                {icono_alerta} 📍 <b>{ubicacion}</b>
            </div>
            <div style="margin-top:5px;">
                <span style="font-size:1.1rem;"><b>{nombre}</b></span> | Stock: {stock} <br>
                <small>Vence: {fecha_s} {texto_aviso}</small>
            </div>
        </div>
        """
        c1.markdown(info, unsafe_allow_html=True)
        
        # Botones
        if c2.button("＋", key=f"p_{idx_excel}_{key_suffix}"):
            worksheet.update_cell(idx_excel, headers.index(col_stock)+1, int(stock)+1)
            st.rerun()
        if c3.button("－", key=f"m_{idx_excel}_{key_suffix}"):
            worksheet.update_cell(idx_excel, headers.index(col_stock)+1, max(0, int(stock)-1))
            st.rerun()
        if c4.button("🗑", key=f"d_{idx_excel}_{key_suffix}"):
            worksheet.delete_rows(idx_excel)
            st.rerun()

# --- 4. INTERFAZ ---
st.title("💊 Inventario de Medicación")

# BUSCADOR
opciones = [""] + sorted(df[col_nom].unique().tolist())
seleccion = st.selectbox("🔍 Buscar medicamento...", opciones, index=0)
if seleccion:
    for i, fila in df[df[col_nom] == seleccion].iterrows():
        pintar_tarjeta(fila, i + 2, "search")
    st.divider()

# PESTAÑAS
t_alerta, t_todos, t_vitrina, t_armario = st.tabs([
    "⚠ Alertas", 
    "📋 Todo", 
    "📁 Vitrina", 
    "📁 Armario"
])

with t_alerta:
    hoy = datetime.now()
    limite = hoy + timedelta(days=60)
    encontrados = 0
    for i, fila in df.iterrows():
        try:
            dt = datetime.strptime(fila[col_cad], "%Y-%m-%d")
            if dt <= limite:
                pintar_tarjeta(fila, i + 2, "alerta")
                encontrados += 1
        except: pass
    if encontrados == 0: st.success("No hay alertas de caducidad.")

with t_todos:
    for i, fila in df.iterrows():
        pintar_tarjeta(fila, i + 2, "todos")

with t_vitrina:
    for i, fila in df[df[col_ubi] == "Medicación de vitrina"].iterrows():
        pintar_tarjeta(fila, i + 2, "vit")

with t_armario:
    for i, fila in df[df[col_ubi] == "Medicación de armario"].iterrows():
        pintar_tarjeta(fila, i + 2, "arm")

# SIDEBAR
with st.sidebar:
    st.header("➕ Nuevo Registro")
    with st.form("add_form", clear_on_submit=True):
        n = st.text_input("Nombre")
        s = st.number_input("Stock", min_value=0, step=1)
        c = st.date_input("Caducidad")
        u = st.selectbox("Ubicación", ["Medicación de vitrina", "Medicación de armario"])
        if st.form_submit_button("Guardar"):
            if n:
                worksheet.append_row([n.capitalize(), int(s), str(c), u, st.session_state["user"]])
                st.rerun()