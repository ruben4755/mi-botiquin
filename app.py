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
data = worksheet.get_all_records()
df = pd.DataFrame(data)
df.columns = df.columns.str.strip()

# --- 3. BARRA LATERAL ---
with st.sidebar:
    st.header("➕ Nuevo Registro")
    with st.form("registro", clear_on_submit=True):
        nom = st.text_input("Nombre")
        cant = st.number_input("Cantidad", min_value=0, step=1)
        fec = st.date_input("Fecha de caducidad", min_value=datetime.now())
        ubi = st.selectbox("Ubicación", ["Medicación de vitrina", "Medicación de armario"])
        if st.form_submit_button("Guardar"):
            worksheet.append_row([nom, int(cant), str(fec), ubi, st.session_state["user"]])
            st.success("Guardado")
            st.rerun()

# --- 4. LÓGICA DE ALERTAS Y LISTADO ---
st.title("💊 Gestión Inteligente de Stock")

tab1, tab2 = st.tabs(["📁 Vitrina", "📁 Armario"])

def pintar_inventario(nombre_filtro):
    col_ubi = [c for c in df.columns if "Ubicacion" in c or "Ubicación" in c]
    if not df.empty and col_ubi:
        items = df[df[col_ubi[0]] == nombre_filtro]
        hoy = datetime.now()
        un_mes_despues = hoy + timedelta(days=30)

        for i, fila in items.iterrows():
            # Lógica de fecha para avisos
            fecha_cad = str(fila.get('Caducidad', ''))
            color_fondo = "#f0f2f6"
            aviso_texto = ""
            
            try:
                dt_cad = datetime.strptime(fecha_cad, "%Y-%m-%d")
                if dt_cad <= hoy:
                    color_fondo = "#ffcccc" # Rojo si ya caducó
                    aviso_texto = "⚠ ¡CADUCADO!"
                elif dt_cad <= un_mes_despues:
                    color_fondo = "#ffe5b4" # Naranja si caduca pronto
                    aviso_texto = "⏳ Caduca en menos de 1 mes"
            except:
                pass

            # Diseño del Medicamento
            with st.container():
                st.markdown(f"""
                    <div style="background-color:{color_fondo}; padding:15px; border-radius:10px; border-left: 6px solid #007bff; margin-bottom:5px; color: black;">
                        <div style="display: flex; justify-content: space-between;">
                            <span><b>{fila['Nombre']}</b></span>
                            <span style="color:red; font-weight:bold;">{aviso_texto}</span>
                        </div>
                        <div style="font-size:13px;">Stock actual: {fila['Stock']} | Vence: {fila['Caducidad']}</div>
                    </div>
                """, unsafe_allow_html=True)
                
                # Botones de gestión rápida (+1, -1, Eliminar)
                c1, c2, c3, c4 = st.columns([1, 1, 3, 2])
                with c1:
                    if st.button("➕", key=f"add_{i}"):
                        worksheet.update_cell(i + 2, 2, int(fila['Stock']) + 1)
                        st.rerun()
                with c2:
                    if st.button("➖", key=f"min_{i}"):
                        nuevo_valor = max(0, int(fila['Stock']) - 1)
                        worksheet.update_cell(i + 2, 2, nuevo_valor)
                        st.rerun()
                with c4:
                    if st.button("🗑 Borrar", key=f"del_{i}"):
                        worksheet.delete_rows(i + 2)
                        st.rerun()
                st.write("---")
    else:
        st.write("Sin datos.")

with tab1:
    pintar_inventario("Medicación de vitrina")
with tab2:
    pintar_inventario("Medicación de armario")