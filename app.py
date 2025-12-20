import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta

# --- 1. CONEXIÓN ---
def conectar_google():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(st.secrets["url_excel"])
        return sh.get_worksheet(0)
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

# --- 2. LOGIN ---
if "user" not in st.session_state:
    st.title("🔒 Acceso Inventario")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u in st.secrets["users"] and p == st.secrets["users"][u]:
            st.session_state["user"] = u
            st.rerun()
    st.stop()

worksheet = conectar_google()

# --- 3. CARGA DE DATOS LIMPIA ---
# Obtenemos todos los datos y eliminamos filas que no tengan nombre (las que dan error)
try:
    data = worksheet.get_all_records()
    df_sucio = pd.DataFrame(data)
    df_sucio.columns = df_sucio.columns.str.strip()
    # Filtramos para que solo aparezcan filas donde la columna "Nombre" no esté vacía
    df = df_sucio[df_sucio['Nombre'] != ""].copy()
except Exception as e:
    st.error(f"Error al leer datos: {e}")
    df = pd.DataFrame()

# --- 4. BARRA LATERAL (AÑADIR) ---
with st.sidebar:
    st.header("➕ Nuevo Registro")
    with st.form("registro", clear_on_submit=True):
        nom = st.text_input("Nombre")
        cant = st.number_input("Cantidad", min_value=0, step=1)
        fec = st.date_input("Fecha de caducidad")
        ubi = st.selectbox("Ubicación", ["Medicación de vitrina", "Medicación de armario"])
        if st.form_submit_button("Guardar"):
            if nom:
                worksheet.append_row([nom, int(cant), str(fec), ubi, st.session_state["user"]])
                st.success("Guardado")
                st.rerun()

# --- 5. LISTADO Y ALERTAS ---
st.title("💊 Gestión de Medicación")
tab1, tab2 = st.tabs(["📁 Vitrina", "📁 Armario"])

def pintar_inventario(nombre_filtro):
    col_ubi = [c for c in df.columns if "Ubicacion" in c or "Ubicación" in c]
    if not df.empty and col_ubi:
        # Importante: filtramos los items pero guardamos su índice original para borrar
        items = df[df[col_ubi[0]] == nombre_filtro]
        hoy = datetime.now()
        un_mes_despues = hoy + timedelta(days=30)

        for i, fila in items.iterrows():
            # Lógica de colores por caducidad
            color_fondo = "#f0f2f6"
            aviso_texto = ""
            try:
                dt_cad = datetime.strptime(str(fila['Caducidad']), "%Y-%m-%d")
                if dt_cad <= hoy:
                    color_fondo = "#ffcccc"
                    aviso_texto = "⚠ CADUCADO"
                elif dt_cad <= un_mes_despues:
                    color_fondo = "#ffe5b4"
                    aviso_texto = "⏳ Caduca pronto"
            except: pass

            with st.container():
                st.markdown(f"""
                    <div style="background-color:{color_fondo}; padding:10px; border-radius:10px; margin-bottom:5px; color: black;">
                        <b>{fila['Nombre']}</b> | Stock: {fila['Stock']} {aviso_texto}<br>
                        <small>Vence: {fila['Caducidad']}</small>
                    </div>
                """, unsafe_allow_html=True)
                
                c1, c2, c3 = st.columns([1, 1, 2])
                # El +2 es porque Excel empieza en 1 y tiene cabecera
                fila_excel = i + 2 
                
                with c1:
                    if st.button("➕", key=f"add_{i}"):
                        worksheet.update_cell(fila_excel, 2, int(fila['Stock']) + 1)
                        st.rerun()
                with c2:
                    if st.button("➖", key=f"min_{i}"):
                        worksheet.update_cell(fila_excel, 2, max(0, int(fila['Stock']) - 1))
                        st.rerun()
                with c3:
                    if st.button("🗑 Borrar", key=f"del_{i}"):
                        worksheet.delete_rows(fila_excel)
                        st.rerun()
                st.write("---")
    else:
        st.write("Sección vacía.")

with tab1: pintar_inventario("Medicación de vitrina")
with tab2: pintar_inventario("Medicación de armario")