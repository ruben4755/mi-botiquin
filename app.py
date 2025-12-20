import streamlit as st
import pandas as pd

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Inventario Seguro", layout="wide")

def limpiar_url(url):
    try:
        base = url.split("/edit")[0]
        return f"{base}/export?format=csv"
    except:
        return None

# --- LOGIN ---
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
            st.error("Datos incorrectos")
    st.stop()

# --- CARGA DE DATOS (CON PROTECCIÓN CONTRA ERRORES) ---
try:
    url_final = limpiar_url(st.secrets["url_excel"])
    df = pd.read_csv(url_final)
    # Limpiar espacios en blanco de los nombres de las columnas
    df.columns = df.columns.str.strip()
except Exception as e:
    st.error(f"⚠ No se pudo leer el Excel. Revisa los nombres de las columnas A1, B1, C1...")
    st.info("Asegúrate de que en el Excel pusiste: Nombre, Stock, Caducidad, Ubicacion")
    st.stop()

# --- INTERFAZ ---
st.title("🚀 Panel de Control")
tab1, tab2 = st.tabs(["📁 Vitrina", "📁 Armario"])

def mostrar(ubi_filtro):
    # Verificamos si la columna existe antes de filtrar
    if "Ubicacion" in df.columns:
        res = df[df["Ubicacion"] == ubi_filtro]
        if not res.empty:
            for _, fila in res.iterrows():
                st.info(f"{fila['Nombre']}** (Stock: {fila['Stock']}) - Vence: {fila['Caducidad']}")
        else:
            st.write("Vacío.")
    else:
        st.error("No encuentro la columna 'Ubicacion' en tu Excel.")

with tab1:
    mostrar("Medicación de vitrina")
with tab2:
    mostrar("Medicación de armario")