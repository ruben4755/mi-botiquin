import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Inventario Seguro", layout="wide")

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
        # Leemos todo como una lista de listas
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

# --- 3. PROCESAMIENTO DE DATOS ---
rows, worksheet = cargar_datos_vivos()

if rows:
    # Creamos el DataFrame
    headers = [str(h).strip() for h in rows[0]]
    df = pd.DataFrame(rows[1:], columns=headers)
    
    # Buscamos los nombres de las columnas reales (por si tienen tildes o espacios)
    col_nom = next((c for c in df.columns if "Nom" in c), None)
    col_stock = next((c for c in df.columns if "Sto" in c or "Cant" in c), None)
    col_cad = next((c for c in df.columns if "Cad" in c or "Fec" in c), None)
    col_ubi = next((c for c in df.columns if "Ubi" in c), None)
else:
    st.warning("El Excel parece vacío.")
    st.stop()

# --- 4. BARRA LATERAL ---
with st.sidebar:
    st.header("➕ Registro")
    with st.form("add"):
        n = st.text_input("Nombre")
        s = st.number_input("Stock", min_value=0, step=1)
        c = st.date_input("Caducidad")
        u = st.selectbox("Ubicación", ["Medicación de vitrina", "Medicación de armario"])
        if st.form_submit_button("Guardar"):
            worksheet.append_row([n, int(s), str(c), u, st.session_state["user"]])
            st.cache_data.clear()
            st.rerun()

# --- 5. LISTADO ---
st.title("💊 Inventario de Medicación")
t1, t2 = st.tabs(["📁 Vitrina", "📁 Armario"])

def mostrar(filtro, pestaña):
    # Si no encontramos la columna de ubicación, no podemos filtrar
    if not col_ubi:
        pestaña.error("No encuentro la columna 'Ubicacion' en tu Excel.")
        return

    items = df[df[col_ubi] == filtro]
    hoy = datetime.now()
    alerta = hoy + timedelta(days=30)

    if items.empty:
        pestaña.write("No hay nada aquí.")
        return

    for i, fila in items.iterrows():
        idx_excel = i + 2
        nombre = fila[col_nom] if col_nom else "Desconocido"
        stock = fila[col_stock] if col_stock else "0"
        fecha_s = fila[col_cad] if col_cad else ""
        
        bg = "#f0f2f6"
        txt = ""
        try:
            dt = datetime.strptime(fecha_s, "%Y-%m-%d")
            if dt <= hoy: bg, txt = "#ffcccc", "🚨 CADUCADO"
            elif dt <= alerta: bg, txt = "#ffe5b4", "⏳ CADUCA PRONTO"
        except: pass

        with pestaña.container():
            c1, c2, c3, c4 = st.columns([5, 1, 1, 1])
            c1.markdown(f"<div style='background:{bg}; padding:10px; border-radius:5px; color:black;'><b>{nombre}</b> (Stock: {stock}) {txt}<br><small>Vence: {fecha_s}</small></div>", unsafe_allow_html=True)
            
            # Botones
            if c2.button("＋", key=f"p{idx_excel}"):
                # Buscamos el número de la columna de Stock (A=1, B=2...)
                col_idx_stock = headers.index(col_stock) + 1
                worksheet.update_cell(idx_excel, col_idx_stock, int(stock) + 1)
                st.rerun()
            if c3.button("－", key=f"m{idx_excel}"):
                col_idx_stock = headers.index(col_stock) + 1
                worksheet.update_cell(idx_excel, col_idx_stock, max(0, int(stock) - 1))
                st.rerun()
            if c4.button("🗑", key=f"d{idx_excel}"):
                worksheet.delete_rows(idx_excel)
                st.rerun()

mostrar("Medicación de vitrina", t1)
mostrar("Medicación de armario", t2)