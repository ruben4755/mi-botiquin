import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Inventario Seguro", layout="wide")

@st.cache_resource
def obtener_cliente():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds)

@st.cache_data(ttl=5)
def cargar_datos_seguro():
    try:
        client = obtener_cliente()
        sh = client.open_by_url(st.secrets["url_excel"])
        worksheet = sh.get_worksheet(0)
        rows = worksheet.get_all_values()
        
        if len(rows) <= 1: # Solo hay encabezados o está vacío
            return pd.DataFrame(columns=["Nombre", "Stock", "Caducidad", "Ubicacion"]), worksheet
        
        # Crear DataFrame asegurando que los nombres de columnas son limpios
        df_temp = pd.DataFrame(rows[1:], columns=rows[0])
        df_temp.columns = [c.strip() for c in df_temp.columns]
        return df_temp, worksheet
    except Exception as e:
        st.error(f"Error al cargar datos: {e}")
        return pd.DataFrame(), None

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

df, worksheet = cargar_datos_seguro()

# --- 3. BARRA LATERAL ---
with st.sidebar:
    st.header("➕ Registro")
    with st.form("registro", clear_on_submit=True):
        nom = st.text_input("Nombre")
        cant = st.number_input("Cantidad", min_value=0, step=1)
        fec = st.date_input("Caducidad")
        ubi = st.selectbox("Ubicación", ["Medicación de vitrina", "Medicación de armario"])
        if st.form_submit_button("Guardar"):
            if nom and worksheet:
                worksheet.append_row([nom, int(cant), str(fec), ubi, st.session_state["user"]])
                st.cache_data.clear()
                st.rerun()

# --- 4. LISTADO ---
st.title("💊 Inventario de Medicación")
tab1, tab2 = st.tabs(["📁 Vitrina", "📁 Armario"])

def pintar_seccion(ubi_filtro):
    # Verificación de seguridad para evitar AttributeError
    if df is None or df.empty or "Ubicacion" not in df.columns:
        st.info("No hay datos registrados en esta sección.")
        return

    items = df[df["Ubicacion"] == ubi_filtro]
    hoy = datetime.now()
    proximo = hoy + timedelta(days=30)

    for i, fila in items.iterrows():
        # Calculamos la fila real del Excel (i es el índice del DataFrame original)
        idx_excel = i + 2
        
        # Extraer datos con seguridad
        nombre_med = fila.get('Nombre', 'Sin nombre')
        stock_med = fila.get('Stock', '0')
        f_cad = str(fila.get('Caducidad', ''))
        
        bg = "#f0f2f6"
        txt_aviso = ""
        
        if f_cad:
            try:
                dt = datetime.strptime(f_cad, "%Y-%m-%d")
                if dt <= hoy: bg, txt_aviso = "#ffcccc", "🚨 CADUCADO"
                elif dt <= proximo: bg, txt_aviso = "#ffe5b4", "⏳ CADUCA PRONTO"
            except: pass

        with st.container():
            c_info, c_plus, c_min, c_del = st.columns([6, 1, 1, 1])
            with c_info:
                st.markdown(f"""<div style='background:{bg}; padding:8px; border-radius:5px; color:black; margin-bottom:5px; border: 1px solid #ddd;'>
                <b>{nombre_med}</b> (Stock: {stock_med}) {txt_aviso}<br>
                <small>Vence: {f_cad}</small></div>""", unsafe_allow_html=True)

            with c_plus:
                if st.button("＋", key=f"p{idx_excel}"):
                    worksheet.update_cell(idx_excel, 2, int(stock_med) + 1)
                    st.cache_data.clear()
                    st.rerun()
            with c_min:
                if st.button("－", key=f"m{idx_excel}"):
                    val = max(0, int(stock_med) - 1)
                    worksheet.update_cell(idx_excel, 2, val)
                    st.cache_data.clear()
                    st.rerun()
            with c_del:
                if st.button("🗑", key=f"d{idx_excel}"):
                    worksheet.delete_rows(idx_excel)
                    st.cache_data.clear()
                    st.rerun()

with tab1: pintar_seccion("Medicación de vitrina")
with tab2: pintar_seccion("Medicación de armario")