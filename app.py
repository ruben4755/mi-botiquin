import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Inventario Rápido", layout="wide")

# --- 2. CONEXIÓN OPTIMIZADA (USA CACHÉ) ---
@st.cache_resource
def obtener_cliente():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

# Esta función guarda los datos en memoria por 10 segundos para máxima velocidad
@st.cache_data(ttl=10)
def cargar_datos_rapido():
    client = obtener_cliente()
    sh = client.open_by_url(st.secrets["url_excel"])
    worksheet = sh.get_worksheet(0)
    data = worksheet.get_all_records()
    df_temp = pd.DataFrame(data)
    df_temp.columns = df_temp.columns.str.strip()
    return df_temp, worksheet

# --- 3. LOGIN (INSTANTÁNEO) ---
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

# Carga de datos inicial
df, worksheet = cargar_datos_rapido()

# --- 4. BARRA LATERAL ---
with st.sidebar:
    st.header("➕ Registro")
    with st.form("registro", clear_on_submit=True):
        nom = st.text_input("Nombre")
        cant = st.number_input("Cantidad", min_value=0, step=1)
        fec = st.date_input("Caducidad")
        ubi = st.selectbox("Ubicación", ["Medicación de vitrina", "Medicación de armario"])
        if st.form_submit_button("Guardar"):
            with st.spinner("Guardando..."):
                worksheet.append_row([nom, int(cant), str(fec), ubi, st.session_state["user"]])
                st.cache_data.clear() # Limpia la memoria para forzar lectura
                st.rerun()
    
    if st.button("🔄 Forzar Refresco"):
        st.cache_data.clear()
        st.rerun()

# --- 5. INTERFAZ Y LISTADO ---
st.title("💊 Inventario Inteligente")
tab1, tab2 = st.tabs(["📁 Vitrina", "📁 Armario"])

def pintar_seccion(ubi_filtro):
    if df.empty:
        st.info("Cargando o sin datos...")
        return

    items = df[df["Ubicacion"] == ubi_filtro]
    hoy = datetime.now()
    proximo = hoy + timedelta(days=30)

    for i, fila in items.iterrows():
        # Lógica de colores simplificada
        f_cad = str(fila['Caducidad'])
        bg = "#f0f2f6"
        txt_aviso = ""
        try:
            dt = datetime.strptime(f_cad, "%Y-%m-%d")
            if dt <= hoy: bg, txt_aviso = "#ffcccc", "🚨 CADUCADO"
            elif dt <= proximo: bg, txt_aviso = "#ffe5b4", "⏳ 1 MES"
        except: pass

        with st.container():
            # Usamos columnas para que los botones de + y - ocupen menos espacio
            c_info, c_plus, c_min, c_del = st.columns([6, 1, 1, 1])
            
            with c_info:
                st.markdown(f"""<div style='background:{bg}; padding:8px; border-radius:5px; color:black;'>
                <b>{fila['Nombre']}</b> (Stock: {fila['Stock']}) {txt_aviso}</div>""", unsafe_allow_html=True)
            
            # Buscamos la fila real en el Excel basándonos en el índice
            idx_excel = i + 2

            with c_plus:
                if st.button("＋", key=f"p{i}"):
                    worksheet.update_cell(idx_excel, 2, int(fila['Stock']) + 1)
                    st.cache_data.clear()
                    st.rerun()
            with c_min:
                if st.button("－", key=f"m{i}"):
                    val = max(0, int(fila['Stock']) - 1)
                    worksheet.update_cell(idx_excel, 2, val)
                    st.cache_data.clear()
                    st.rerun()
            with c_del:
                if st.button("🗑", key=f"d{i}"):
                    worksheet.delete_rows(idx_excel)
                    st.cache_data.clear()
                    st.rerun()

with tab1: pintar_seccion("Medicación de vitrina")
with tab2: pintar_seccion("Medicación de armario")