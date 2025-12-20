import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Inventario Rápido", layout="wide")

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

# --- 3. FUNCIÓN TARJETAS ---
def pintar_tarjeta(fila, idx_excel, key_suffix):
    nombre = fila[col_nom]
    stock = fila[col_stock]
    fecha_s = fila[col_cad]
    ubicacion = fila[col_ubi]
    
    hoy = datetime.now()
    alerta = hoy + timedelta(days=30)
    bg, txt = "#f0f2f6", ""
    try:
        dt = datetime.strptime(fecha_s, "%Y-%m-%d")
        if dt <= hoy: bg, txt = "#ffcccc", "🚨 CADUCADO"
        elif dt <= alerta: bg, txt = "#ffe5b4", "⏳ PRÓXIMO"
    except: pass

    with st.container():
        c1, c2, c3, c4 = st.columns([5, 1, 1, 1])
        info = f"📍 <b>{ubicacion}</b><br><b>{nombre}</b> (Stock: {stock}) {txt}<br><small>Vence: {fecha_s}</small>"
        c1.markdown(f"<div style='background:{bg}; padding:10px; border-radius:5px; color:black; margin-bottom:5px; border-left: 5px solid #007bff;'>{info}</div>", unsafe_allow_html=True)
        
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
st.subheader("🔍 Buscador Instantáneo")
opciones = [""] + sorted(df[col_nom].unique().tolist())
seleccion = st.selectbox("Escribe el nombre del medicamento...", opciones, index=0)

if seleccion:
    resultados = df[df[col_nom] == seleccion]
    for i, fila in resultados.iterrows():
        pintar_tarjeta(fila, i + 2, "search")
    st.divider()

# PESTAÑAS
t1, t2 = st.tabs(["📁 Vitrina", "📁 Armario"])

with t1:
    items = df[df[col_ubi] == "Medicación de vitrina"]
    for i, fila in items.iterrows():
        pintar_tarjeta(fila, i + 2, "tab1")

with t2:
    items = df[df[col_ubi] == "Medicación de armario"]
    for i, fila in items.iterrows():
        pintar_tarjeta(fila, i + 2, "tab2")

# --- 5. BARRA LATERAL (CON LIMPIEZA AUTOMÁTICA) ---
with st.sidebar:
    st.header("➕ Nuevo Registro")
    # El parámetro clear_on_submit=True es el que limpia el formulario al guardar
    with st.form("add_form", clear_on_submit=True):
        n = st.text_input("Nombre")
        s = st.number_input("Stock", min_value=0, step=1)
        c = st.date_input("Caducidad")
        u = st.selectbox("Ubicación", ["Medicación de vitrina", "Medicación de armario"])
        
        enviar = st.form_submit_button("Guardar Medicamento")
        
        if enviar:
            if n:
                with st.spinner("Guardando..."):
                    worksheet.append_row([n, int(s), str(c), u, st.session_state["user"]])
                    st.success(f"✅ {n} guardado correctamente")
                    st.rerun()
            else:
                st.error("El nombre es obligatorio")