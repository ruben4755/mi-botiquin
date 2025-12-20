import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONEXIÓN CON GOOGLE SHEETS ---
def conectar_google():
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    # Usamos la llave que pegaste en Secrets
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    # Abrimos el Excel por la URL que también está en Secrets
    sh = client.open_by_url(st.secrets["url_excel"])
    return sh.get_worksheet(0)

# Intentar conectar
try:
    worksheet = conectar_google()
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- 2. LOGIN ---
if "user" not in st.session_state:
    st.title("🔒 Acceso Inventario")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u in st.secrets["users"] and p == st.secrets["users"][u]:
            st.session_state["user"] = u
            st.rerun()
        else:
            st.error("Credenciales incorrectas")
    st.stop()

# --- 3. FUNCIONES DE GESTIÓN ---
def cargar_datos():
    # Lee todo el Excel y lo convierte en una tabla de Python
    lista_datos = worksheet.get_all_records()
    return pd.DataFrame(lista_datos)

# --- 4. INTERFAZ PRINCIPAL ---
st.title("💊 Gestión de Medicación")

# BARRA LATERAL PARA AÑADIR NUEVOS
with st.sidebar:
    st.header("➕ Nuevo Medicamento")
    with st.form("form_add", clear_on_submit=True):
        nombre = st.text_input("Nombre del fármaco")
        stock = st.number_input("Cantidad inicial", min_value=0, step=1)
        fecha = st.text_input("Fecha de caducidad (Ej: 2026-05-20)")
        ubi = st.selectbox("¿Dónde se guarda?", ["Medicación de vitrina", "Medicación de armario"])
        
        if st.form_submit_button("Registrar Medicamento"):
            if nombre and fecha:
                # Añade una fila al final del Excel de Google
                worksheet.append_row([nombre, stock, fecha, ubi, st.session_state["user"]])
                st.success("✅ ¡Guardado en Google Sheets!")
                st.rerun()
            else:
                st.warning("Por favor, rellena nombre y fecha.")

# --- 5. VISUALIZACIÓN POR PESTAÑAS ---
df = cargar_datos()
tab1, tab2 = st.tabs(["📁 Medicación de Vitrina", "📁 Medicación de Armario"])

def renderizar_lista(nombre_ubicacion):
    # Filtrar solo lo que pertenece a esta pestaña
    if not df.empty and "Ubicacion" in df.columns:
        items = df[df["Ubicacion"] == nombre_ubicacion]
        
        if not items.empty:
            for i, fila in items.iterrows():
                # DISEÑO: Nombre a la izquierda, Fecha a la derecha
                st.markdown(f"""
                    <div style="background-color:#f0f2f6; padding:15px; border-radius:10px; border-left: 6px solid #007bff; margin-bottom:10px; color: black;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size:18px;"><b>{fila['Nombre']}</b> (x{fila['Stock']})</span>
                            <span style="font-size:14px; color:#666;">📅 Vence: <b>{fila['Caducidad']}</b></span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                # Botón pequeño para borrar justo debajo de cada uno
                if st.button(f"Eliminar {fila['Nombre']}", key=f"btn_{i}"):
                    # gspread borra filas empezando por 1 y contando encabezado (i+2)
                    worksheet.delete_rows(i + 2)
                    st.rerun()
        else:
            st.write("No hay nada aquí todavía.")
    else:
        st.write("El Excel está vacío.")

with tab1:
    renderizar_lista("Medicación de vitrina")

with tab2:
    renderizar_lista("Medicación de armario")
