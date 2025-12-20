import streamlit as st
import pandas as pd
from datetime import date

# 1. CONFIGURACIÓN E IDIOMAS
st.set_page_config(page_title="Inventario Cloud Pro", layout="wide")

idiomas = {
    "Español": {
        "titulo": "🚀 Panel Compartido (Google Cloud)",
        "usuario": "Usuario",
        "pass": "Contraseña",
        "btn_entrar": "Acceder",
        "sidebar_add": "➕ Añadir Elemento",
        "nombre": "Nombre",
        "cantidad": "Cantidad",
        "fecha": "Fecha",
        "ubicacion": "Ubicación",
        "opcion1": "Medicación de vitrina",
        "opcion2": "Medicación de armario",
        "btn_guardar": "Guardar en la Nube",
        "buscar": "🔍 Buscar...",
        "vence": "Vence",
        "modificado": "Por",
        "vacío": "Sin datos.",
        "cerrar": "Cerrar"
    },
    "English": {
        "titulo": "🚀 Cloud Team Panel",
        "usuario": "Username",
        "pass": "Password",
        "btn_entrar": "Login",
        "sidebar_add": "➕ Add Item",
        "nombre": "Name",
        "cantidad": "Stock",
        "fecha": "Date",
        "ubicacion": "Location",
        "opcion1": "Display Case",
        "opcion2": "Cabinet",
        "btn_guardar": "Save to Cloud",
        "buscar": "🔍 Search...",
        "vence": "Expires",
        "modificado": "By",
        "vacío": "No data.",
        "cerrar": "Logout"
    }
}

if "lang" not in st.session_state:
    st.session_state.lang = "Español"

# 2. LOGIN (Igual que antes)
def check_password():
    if "user" not in st.session_state:
        st.title("🔒 Acceso Seguro")
        u_input = st.text_input("Usuario")
        p_input = st.text_input("Contraseña", type="password")
        if st.button("Entrar"):
            user_secrets = st.secrets.get("users", {})
            if u_input in user_secrets and p_input == user_secrets[u_input]:
                st.session_state["user"] = u_input
                st.rerun()
            else:
                st.error("❌ Datos incorrectos")
        return False
    return True

if not check_password():
    st.stop()

t = idiomas[st.session_state.lang]

# 3. CONEXIÓN CON GOOGLE SHEETS
# Transformamos el enlace normal de Google en un enlace de descarga directa
raw_url = st.secrets["url_excel"]
csv_url = raw_url.replace("/edit?usp=sharing", "/export?format=csv")
csv_url = csv_url.replace("/edit#gid=0", "/export?format=csv") # Por si el enlace es distinto

@st.cache_data(ttl=10) # Refresca los datos cada 10 segundos
def cargar_datos_google():
    try:
        return pd.read_csv(csv_url)
    except:
        return pd.DataFrame(columns=["Nombre", "Stock", "Caducidad", "Ubicacion", "Ultimo_Cambio"])

# IMPORTANTE: Para escribir en Google Sheets desde Streamlit se necesita una configuración avanzada. 
# Por ahora, esta versión LEE de Google. 
# Si quieres que también ESCRIBA (Guardar), necesitamos un paso extra con una "Service Account".

st.warning("⚠ Esta versión lee directamente de tu Google Sheets. Para añadir datos, edita el Excel y refresca la app.")

df = cargar_datos_google()
st.title(t["titulo"])
st.session_state.lang = st.radio("Idioma:", ["Español", "English"], horizontal=True)

# 4. MOSTRAR INVENTARIO (Pestañas)
tab1, tab2 = st.tabs([f"📁 {t['opcion1']}", f"📁 {t['opcion2']}"])

def mostrar_seccion(nombre_ubi):
    # Filtrar por ubicación (Vitrina o Armario)
    filtro = df[df["Ubicacion"] == nombre_ubi]
    
    if not filtro.empty:
        for _, fila in filtro.iterrows():
            st.markdown(f"""
                <div style="background-color:#f8f9fa; padding:12px; border-radius:8px; border-left: 5px solid #1c3d5a; margin-bottom:8px; color:black;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size:18px;"><b>{fila['Nombre']}</b> (x{fila['Stock']})</span>
                        <span style="font-size:14px; color:#555;">📅 {t['vence']}: <b>{fila['Caducidad']}</b></span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.write(t["vacío"])

with tab1:
    mostrar_seccion("Medicación de vitrina")

with tab2:
    mostrar_seccion("Medicación de armario")