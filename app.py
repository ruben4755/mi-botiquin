import streamlit as st
import pandas as pd
from datetime import date
import os

st.set_page_config(page_title="Inventario Compartido Pro", layout="wide")

# --- SISTEMA DE ACCESO ---
def check_password():
    if "user" not in st.session_state:
        st.title("🔒 Acceso Compartido - Rendimiento")
        u_input = st.text_input("Tu Nombre")
        p_input = st.text_input("Contraseña", type="password")
        
        if st.button("Acceder al Panel"):
            user_secrets = st.secrets.get("users", {})
            if u_input in user_secrets and p_input == user_secrets[u_input]:
                st.session_state["user"] = u_input
                st.rerun()
            else:
                st.error("❌ Usuario o contraseña no válidos")
        return False
    return True

if not check_password():
    st.stop()

# --- GESTIÓN DE DATOS ÚNICA PARA TODOS ---
def cargar_datos():
    if os.path.exists("inventario.csv"):
        try:
            df = pd.read_csv("inventario.csv")
            df['Caducidad'] = pd.to_datetime(df['Caducidad']).dt.date
            return df
        except:
            return pd.DataFrame(columns=["Nombre", "Stock", "Caducidad", "Ultimo_Cambio"])
    return pd.DataFrame(columns=["Nombre", "Stock", "Caducidad", "Ultimo_Cambio"])

def guardar_datos(df):
    df.to_csv("inventario.csv", index=False)

if 'df' not in st.session_state:
    st.session_state.df = cargar_datos()

# --- INTERFAZ ---
st.title("🚀 Panel de Control de Equipo")
st.info(f"Sesión iniciada por: *{st.session_state['user']}*. Todos los cambios son visibles para el equipo.")

# BARRA LATERAL
with st.sidebar:
    st.header("➕ Añadir Recurso")
    with st.form("add_form", clear_on_submit=True):
        n = st.text_input("Nombre del recurso")
        s = st.number_input("Cantidad inicial", min_value=1)
        v = st.date_input("Fecha límite/reposición", value=date.today())
        
        if st.form_submit_button("Añadir al grupo"):
            if n:
                nueva = pd.DataFrame([{"Nombre": n, "Stock": s, "Caducidad": v, "Ultimo_Cambio": st.session_state['user']}])
                st.session_state.df = pd.concat([st.session_state.df, nueva], ignore_index=True)
                guardar_datos(st.session_state.df)
                st.rerun()
    
    if st.button("Cerrar Sesión"):
        del st.session_state["user"]
        st.rerun()

# LISTADO COMPARTIDO
st.subheader("📦 Inventario Global")
busqueda = st.text_input("🔍 Buscar recurso compartido...", placeholder="Ej: Cafeína").lower()

res = st.session_state.df.copy()
if busqueda:
    res = res[res['Nombre'].str.lower().str.contains(busqueda)]

if not res.empty:
    res = res.sort_values("Caducidad")
    for i, fila in res.iterrows():
        # Estética de tarjeta profesional
        st.markdown(f"""
            <div style="background-color:#f0f2f6; padding:15px; border-radius:10px; border-left: 5px solid #007bff; margin-bottom:10px; color: black;">
                <div style="display: flex; justify-content: space-between;">
                    <b style="font-size:18px;">{fila['Nombre']}</b>
                    <span>Stock: <b style="font-size:18px;">{fila['Stock']}</b></span>
                </div>
                <div style="font-size:12px; color:gray; margin-top:5px;">
                    📅 Vence: {fila['Caducidad']} | 👤 Modificado por última vez por: {fila['Ultimo_Cambio']}
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        c1, c2, c3, _ = st.columns([0.6, 0.6, 0.6, 7])
        if c1.button("➕", key=f"u{i}"):
            st.session_state.df.at[i, 'Stock'] += 1
            st.session_state.df.at[i, 'Ultimo_Cambio'] = st.session_state['user']
            guardar_datos(st.session_state.df)
            st.rerun()
        if c2.button("➖", key=f"d{i}"):
            if st.session_state.df.at[i, 'Stock'] > 0:
                st.session_state.df.at[i, 'Stock'] -= 1
                st.session_state.df.at[i, 'Ultimo_Cambio'] = st.session_state['user']
                guardar_datos(st.session_state.df)
                st.rerun()
        if c3.button("🗑", key=f"r{i}"):
            st.session_state.df = st.session_state.df.drop(i).reset_index(drop=True)
            guardar_datos(st.session_state.df)
            st.rerun()
else:
    st.write("No hay recursos en la lista común.")