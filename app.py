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

@st.cache_data(ttl=10)
def cargar_datos_seguro():
    client = obtener_cliente()
    sh = client.open_by_url(st.secrets["url_excel"])
    worksheet = sh.get_worksheet(0)
    
    # CAMBIO CLAVE: Leemos los valores directos, no los registros por nombre
    # Esto evita el error de nombres duplicados
    rows = worksheet.get_all_values()
    if not rows:
        return pd.DataFrame(), worksheet
    
    # La primera fila son los encabezados, el resto son los datos
    df_temp = pd.DataFrame(rows[1:], columns=rows[0])
    df_temp.columns = df_temp.columns.str.strip()
    return df_temp, worksheet

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
            if nom:
                with st.spinner("Guardando..."):
                    worksheet.append_row([nom, int(cant), str(fec), ubi, st.session_state["user"]])
                    st.cache_data.clear()
                    st.rerun()

# --- 4. LISTADO ---
st.title("💊 Inventario de Medicación")
tab1, tab2 = st.tabs(["📁 Vitrina", "📁 Armario"])

def pintar_seccion(ubi_filtro):
    if df.empty:
        st.info("No hay datos todavía.")
        return

    # Filtramos por la columna Ubicacion
    items = df[df["Ubicacion"] == ubi_filtro]
    hoy = datetime.now()
    proximo = hoy + timedelta(days=30)

    for i, fila in items.iterrows():
        # i es el índice del DataFrame, que coincide con la fila del Excel - 2
        idx_excel = i + 2
        
        f_cad = str(fila['Caducidad'])
        bg = "#f0f2f6"
        txt_aviso = ""
        try:
            dt = datetime.strptime(f_cad, "%Y-%m-%d")
            if dt <= hoy: bg, txt_aviso = "#ffcccc", "🚨 CADUCADO"
            elif dt <= proximo: bg, txt_aviso = "#ffe5b4", "⏳ 1 MES"
        except: pass

        with st.container():
            c_info, c_plus, c_min, c_del = st.columns([6, 1, 1, 1])
            
            with c_info:
                st.markdown(f"""<div style='background:{bg}; padding:8px; border-radius:5px; color:black; margin-bottom:5px;'>
                <b>{fila['Nombre']}</b> (Stock: {fila['Stock']}) {txt_aviso}<br>
                <small>Vence: {f_cad}</small></div>""", unsafe_allow_html=True)

            with c_plus:
                if st.button("＋", key=f"p{idx_excel}"):
                    # Columna 2 es el Stock
                    nuevo_val = int(fila['Stock']) + 1
                    worksheet.update_cell(idx_excel, 2, nuevo_val)
                    st.cache_data.clear()
                    st.rerun()
            with c_min:
                if st.button("－", key=f"m{idx_excel}"):
                    nuevo_val = max(0, int(fila['Stock']) - 1)
                    worksheet.update_cell(idx_excel, 2, nuevo_val)
                    st.cache_data.clear()
                    st.rerun()
            with c_del:
                if st.button("🗑", key=f"d{idx_excel}"):
                    worksheet.delete_rows(idx_excel)
                    st.cache_data.clear()
                    st.rerun()

with tab1: pintar_seccion("Medicación de vitrina")
with tab2: pintar_seccion("Medicación de armario")