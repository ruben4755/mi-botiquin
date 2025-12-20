import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Inventario Inteligente", layout="wide")

@st.cache_resource
def obtener_cliente():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Error en credenciales: {e}")
        return None

def cargar_datos_vivos():
    try:
        client = obtener_cliente()
        sh = client.open_by_url(st.secrets["url_excel"])
        worksheet = sh.get_worksheet(0)
        rows = worksheet.get_all_values()
        return rows, worksheet
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None, None

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

# --- 3. PROCESAMIENTO ---
rows, worksheet = cargar_datos_vivos()

if rows:
    headers = [str(h).strip() for h in rows[0]]
    df = pd.DataFrame(rows[1:], columns=headers)
    col_nom = next((c for c in df.columns if "Nom" in c), "Nombre")
    col_stock = next((c for c in df.columns if "Sto" in c or "Cant" in c), "Stock")
    col_cad = next((c for c in df.columns if "Cad" in c or "Fec" in c), "Caducidad")
    col_ubi = next((c for c in df.columns if "Ubi" in c), "Ubicacion")
else:
    st.warning("El Excel está vacío.")
    st.stop()

# --- 4. FUNCIÓN PARA PINTAR TARJETAS (REUTILIZABLE) ---
def pintar_tarjeta(fila, idx_excel, modo_busqueda=False):
    nombre = fila[col_nom]
    stock = fila[col_stock]
    fecha_s = fila[col_cad]
    ubicacion = fila[col_ubi]
    
    hoy = datetime.now()
    alerta = hoy + timedelta(days=30)
    bg = "#f0f2f6"
    txt = ""
    
    try:
        dt = datetime.strptime(fecha_s, "%Y-%m-%d")
        if dt <= hoy: bg, txt = "#ffcccc", "🚨 CADUCADO"
        elif dt <= alerta: bg, txt = "#ffe5b4", "⏳ CADUCA PRONTO"
    except: pass

    with st.container():
        c1, c2, c3, c4 = st.columns([5, 1, 1, 1])
        
        # Si es modo búsqueda, añadimos la ubicación en grande
        info_html = f"<b>{nombre}</b> (Stock: {stock}) {txt}<br><small>Vence: {fecha_s}</small>"
        if modo_busqueda:
            info_html = f"📍 <b>{ubicacion}</b><br>" + info_html
            
        c1.markdown(f"<div style='background:{bg}; padding:10px; border-radius:5px; color:black; margin-bottom:5px; border-left: 5px solid #007bff;'>{info_html}</div>", unsafe_allow_html=True)
        
        # Botones de acción
        suffix = "srch" if modo_busqueda else "tab"
        if c2.button("＋", key=f"p{idx_excel}_{suffix}"):
            col_idx = headers.index(col_stock) + 1
            worksheet.update_cell(idx_excel, col_idx, int(stock) + 1)
            st.cache_data.clear()
            st.rerun()
        if c3.button("－", key=f"m{idx_excel}_{suffix}"):
            col_idx = headers.index(col_stock) + 1
            worksheet.update_cell(idx_excel, col_idx, max(0, int(stock) - 1))
            st.cache_data.clear()
            st.rerun()
        if c4.button("🗑", key=f"d{idx_excel}_{suffix}"):
            worksheet.delete_rows(idx_excel)
            st.cache_data.clear()
            st.rerun()

# --- 5. INTERFAZ ---
st.title("💊 Inventario de Medicación")

# BUSCADOR EN TIEMPO REAL
st.subheader("🔍 Buscador Inteligente")
busqueda = st.text_input("Empieza a escribir el nombre...", key="main_search").strip().lower()

if busqueda:
    # Filtro letra a letra
    mask = df[col_nom].str.lower().str.contains(busqueda)
    resultados = df[mask]
    
    if not resultados.empty:
        for i, fila in resultados.iterrows():
            pintar_tarjeta(fila, i + 2, modo_busqueda=True)
    else:
        st.write("No hay coincidencias.")
    st.divider()

# PESTAÑAS PARA NAVEGACIÓN NORMAL
t1, t2 = st.tabs(["📁 Vitrina", "📁 Armario"])

with t1:
    items = df[df[col_ubi] == "Medicación de vitrina"]
    for i, fila in items.iterrows():
        pintar_tarjeta(fila, i + 2)

with t2:
    items = df[df[col_ubi] == "Medicación de armario"]
    for i, fila in items.iterrows():
        pintar_tarjeta(fila, i + 2)

# BARRA LATERAL PARA AÑADIR
with st.sidebar:
    st.header("➕ Nuevo Registro")
    with st.form("add"):
        n = st.text_input("Nombre")
        s = st.number_input("Stock", min_value=0, step=1)
        c = st.date_input("Caducidad")
        u = st.selectbox("Ubicación", ["Medicación de vitrina", "Medicación de armario"])
        if st.form_submit_button("Guardar"):
            worksheet.append_row([n, int(s), str(c), u, st.session_state["user"]])
            st.cache_data.clear()
            st.rerun()