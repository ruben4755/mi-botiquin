import streamlit as st
import pandas as pd

# --- 1. CONFIGURACIÓN Y LIMPIEZA DE URL ---
st.set_page_config(page_title="Inventario Cloud", layout="wide")

def limpiar_url(url):
    # Esta función transforma el enlace de Google para que la app pueda leerlo
    try:
        base = url.split("/edit")[0]
        return f"{base}/export?format=csv"
    except:
        return None

# --- 2. IDIOMAS ---
idiomas = {
    "Español": {
        "titulo": "🚀 Panel de Control",
        "vence": "Vence",
        "vacío": "No hay datos en esta sección.",
        "vitrina": "Medicación de vitrina",
        "armario": "Medicación de armario",
        "buscar": "Buscar..."
    },
    "English": {
        "titulo": "🚀 Control Panel",
        "vence": "Expires",
        "vacío": "No data in this section.",
        "vitrina": "Display Case Meds",
        "armario": "Cabinet Meds",
        "buscar": "Search..."
    }
}

# --- 3. SEGURIDAD (LOGIN) ---
def check_password():
    if "user" not in st.session_state:
        st.title("🔒 Acceso")
        u = st.text_input("Usuario")
        p = st.text_input("Contraseña", type="password")
        if st.button("Entrar"):
            user_secrets = st.secrets.get("users", {})
            if u in user_secrets and p == user_secrets[u]:
                st.session_state["user"] = u
                st.rerun()
            else:
                st.error("❌ Error")
        return False
    return True

if not check_password():
    st.stop()

# --- 4. CARGA DE DATOS DESDE GOOGLE SHEETS ---
if "url_excel" in st.secrets:
    url_final = limpiar_url(st.secrets["url_excel"])
    try:
        # Leemos el Excel de Google
        df = pd.read_csv(url_final)
    except:
        st.error("Error al conectar con Google Sheets. Revisa el enlace en Secrets.")
        st.stop()
else:
    st.error("Falta la URL del Excel en Secrets.")
    st.stop()

# --- 5. INTERFAZ ---
lang = st.radio("Idioma / Language", ["Español", "English"], horizontal=True)
t = idiomas[lang]

st.title(t["titulo"])

# Pestañas para separar Vitrina y Armario
tab1, tab2 = st.tabs([f"📁 {t['vitrina']}", f"📁 {t['armario']}"])

def mostrar_inventario(ubicacion_nombre):
    # Filtramos los datos del Excel por la ubicación
    filtro = df[df["Ubicacion"] == ubicacion_nombre]
    
    if not filtro.empty:
        for _, fila in filtro.iterrows():
            # DISEÑO: Nombre (izquierda) y Fecha (derecha)
            st.markdown(f"""
                <div style="background-color:#f8f9fa; padding:15px; border-radius:10px; border-left: 5px solid #1c3d5a; margin-bottom:10px; color:black;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size:18px;"><b>{fila['Nombre']}</b> (x{fila['Stock']})</span>
                        <span style="font-size:14px; color:#555;">📅 {t['vence']}: <b>{fila['Caducidad']}</b></span>
                    </div>
                </div>
            """, unsafe_allow_html=True)
    else:
        st.write(t["vacío"])

with tab1:
    mostrar_inventario("Medicación de vitrina")

with tab2:
    mostrar_inventario("Medicación de armario")
