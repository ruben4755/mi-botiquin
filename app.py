import streamlit as st
import pandas as pd
from datetime import date

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Mi Botiquín Seguro", layout="wide")

# 2. FUNCIÓN DE SEGURIDAD
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False

    if st.session_state["password_correct"]:
        return True

    # Pantalla de bloqueo
    st.title("🔒 Acceso Restringido")
    password_input = st.text_input("Introduce la contraseña del botiquín:", type="password")
    
    if st.button("Entrar"):
        # Compara con lo que pusiste en el panel 'Secrets' de Streamlit
        if password_input == st.secrets["password"]:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("❌ Contraseña incorrecta")
    return False

# Si no pasa la contraseña, la app se para aquí
if not check_password():
    st.stop()

# --- 3. CÓDIGO DE LA APLICACIÓN (Solo se ve si la clave es correcta) ---

def cargar_datos():
    try:
        df = pd.read_csv("inventario.csv")
        df['Caducidad'] = pd.to_datetime(df['Caducidad']).dt.date
        return df
    except:
        return pd.DataFrame(columns=["Nombre", "Stock", "Caducidad", "Notas"])

def guardar_datos(df):
    df.to_csv("inventario.csv", index=False)

if 'df' not in st.session_state:
    st.session_state.df = cargar_datos()

st.title("💊 Mi Botiquín Familiar")

# --- BARRA LATERAL ---
with st.sidebar:
    st.header("➕ Añadir Medicamento")
    with st.form("nuevo_form", clear_on_submit=True):
        n = st.text_input("Nombre del medicamento")
        s = st.number_input("Cantidad (unidades)", min_value=1, value=1)
        notas = st.text_area("Notas / Síntomas", placeholder="Ej: Para la fiebre")
        vence = st.date_input("Fecha de caducidad", value=date.today())
        
        if st.form_submit_button("Guardar en inventario"):
            if n:
                nueva_fila = pd.DataFrame([{"Nombre": n, "Stock": s, "Caducidad": vence, "Notas": notas}])
                st.session_state.df = pd.concat([st.session_state.df, nueva_fila], ignore_index=True)
                guardar_datos(st.session_state.df)
                st.success("¡Guardado!")
                st.rerun()

    st.divider()
    if st.button("🧹 Borrar todos los caducados"):
        hoy = date.today()
        antes = len(st.session_state.df)
        st.session_state.df = st.session_state.df[st.session_state.df['Caducidad'] >= hoy]
        guardar_datos(st.session_state.df)
        st.success(f"Limpieza hecha. Se borraron {antes - len(st.session_state.df)} items.")
        st.rerun()

# --- BUSCADOR Y LISTADO ---
busqueda = st.text_input("🔍 Buscar medicina o síntoma...", placeholder="Ej: Ibuprofeno o Dolor").lower()

# Filtrar datos
res = st.session_state.df.copy()
if busqueda:
    res = res[
        res['Nombre'].str.lower().str.contains(busqueda) | 
        res['Notas'].str.lower().str.contains(busqueda)
    ]

# Mostrar resultados con diseño de tarjetas
hoy = date.today()
if not res.empty:
    for i, fila in res.iterrows():
        # Color según caducidad
        dias = (fila['Caducidad'] - hoy).days
        if dias < 0:
            color = "#FFDADA"  # Rojo (Caducado)
        elif dias < 30:
            color = "#FFF4D1"  # Amarillo (Próximo)
        else:
            color = "#D4EDDA"  # Verde (Bien)

        st.markdown(f"""
            <div style="background-color:{color}; padding:15px; border-radius:10px; border:1px solid #ccc; margin-bottom:10px; color:black;">
                <h3 style="margin:0;">{fila['Nombre']}</h3>
                <p style="margin:5px 0;"><b>Stock:</b> {fila['Stock']} unidades | <b>Vence:</b> {fila['Caducidad']}</p>
                <p style="margin:0;"><i>{fila['Notas']}</i></p>
            </div>
        """, unsafe_allow_html=True)
        
        # Botones de acción
        c1, c2, _ = st.columns([1, 1, 8])
        if c1.button("🗑", key=f"del{i}"):
            st.session_state.df = st.session_state.df.drop(i).reset_index(drop=True)
            guardar_datos(st.session_state.df)
            st.rerun()
else:
    st.info("No hay medicamentos registrados o no coinciden con la búsqueda.")