import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- 1. CONEXIÓN (SIN MEMORIA CACHÉ PARA QUE SEA EN VIVO) ---
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
    st.title("🔒 Acceso")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u in st.secrets["users"] and p == st.secrets["users"][u]:
            st.session_state["user"] = u
            st.rerun()
    st.stop()

# Conectamos
worksheet = conectar_google()

# --- 3. CARGA DE DATOS REAL ---
# Hemos quitado el @st.cache para que no se "olvide" de actualizar
data = worksheet.get_all_records()
df = pd.DataFrame(data)
df.columns = df.columns.str.strip()

# --- 4. FORMULARIO EN LA BARRA LATERAL ---
with st.sidebar:
    st.header("➕ Añadir Medicamento")
    with st.form("registro", clear_on_submit=True):
        nom = st.text_input("Nombre")
        cant = st.number_input("Cantidad", min_value=0, step=1)
        fec = st.text_input("Fecha (AAAA-MM-DD)")
        ubi = st.selectbox("Ubicación", ["Medicación de vitrina", "Medicación de armario"])
        
        if st.form_submit_button("Registrar"):
            if nom and fec:
                # Escribimos en Google Sheets
                worksheet.append_row([nom, cant, fec, ubi, st.session_state["user"]])
                st.success("✅ Guardado en Google. Actualizando...")
                # Forzamos el reinicio para leer los nuevos datos inmediatamente
                st.rerun()
            else:
                st.warning("Rellena todos los campos.")
    
    st.divider()
    if st.button("🔄 Actualizar lista ahora"):
        st.rerun()

# --- 5. PESTAÑAS Y LISTADO ---
st.title("💊 Inventario de Medicación")
tab1, tab2 = st.tabs(["📁 Vitrina", "📁 Armario"])

def pintar_lista(nombre_filtro):
    # Buscamos la columna de ubicación (sin importar tildes)
    col_ubi = [c for c in df.columns if "Ubicacion" in c or "Ubicación" in c]
    
    if not df.empty and col_ubi:
        nombre_col = col_ubi[0]
        items = df[df[nombre_col] == nombre_filtro]
        
        if not items.empty:
            for i, fila in items.iterrows():
                st.markdown(f"""
                    <div style="background-color:#f0f2f6; padding:15px; border-radius:10px; border-left: 6px solid #007bff; margin-bottom:10px; color: black;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <span style="font-size:18px;"><b>{fila.get('Nombre', 'Error')}</b> (x{fila.get('Stock', 0)})</span>
                            <span style="font-size:14px; color:#666;">📅 Vence: <b>{fila.get('Caducidad', 'S/F')}</b></span>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                # Botón para borrar
                if st.button(f"Borrar {fila.get('Nombre', i)}", key=f"del_{i}"):
                    worksheet.delete_rows(i + 2)
                    st.rerun()
        else:
            st.write("No hay nada en esta sección.")
    else:
        st.info("No se encuentran datos. Revisa los nombres de las columnas en tu Excel.")

with tab1:
    pintar_lista("Medicación de vitrina")
with tab2:
    pintar_lista("Medicación de armario")