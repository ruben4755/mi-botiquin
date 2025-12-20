import streamlit as st
import pandas as pd
from datetime import date
import os

# 1. CONFIGURACIÓN Y MULTI-IDIOMA
st.set_page_config(page_title="Gestión de Inventario Pro", layout="wide")

idiomas = {
    "Español": {
        "titulo": "🚀 Panel de Control de Equipo",
        "usuario": "Usuario",
        "pass": "Contraseña",
        "btn_entrar": "Acceder",
        "sidebar_add": "➕ Añadir Elemento",
        "nombre": "Nombre del elemento",
        "cantidad": "Cantidad",
        "fecha": "Fecha",
        "ubicacion": "Ubicación",
        "opcion1": "Medicación de vitrina",
        "opcion2": "Medicación de armario",
        "btn_guardar": "Guardar en inventario",
        "buscar": "🔍 Buscar elemento...",
        "vence": "Vence",
        "modificado": "Modificado por",
        "vacío": "No hay elementos aquí.",
        "cerrar": "Cerrar Sesión"
    },
    "English": {
        "titulo": "🚀 Team Control Panel",
        "usuario": "Username",
        "pass": "Password",
        "btn_entrar": "Login",
        "sidebar_add": "➕ Add Item",
        "nombre": "Item Name",
        "cantidad": "Stock",
        "fecha": "Date",
        "ubicacion": "Location",
        "opcion1": "Display Case Meds",
        "opcion2": "Cabinet Meds",
        "btn_guardar": "Save to inventory",
        "buscar": "🔍 Search item...",
        "vence": "Expires",
        "modificado": "Last changed by",
        "vacío": "No items here.",
        "cerrar": "Logout"
    }
}

# Selector de idioma en la parte superior
if "lang" not in st.session_state:
    st.session_state.lang = "Español"

# 2. SISTEMA DE ACCESO
def check_password():
    if "user" not in st.session_state:
        st.title("🔒 Acceso al Sistema")
        u_input = st.text_input("Usuario / Username")
        p_input = st.text_input("Contraseña / Password", type="password")
        if st.button("Entrar"):
            user_secrets = st.secrets.get("users", {})
            if u_input in user_secrets and p_input == user_secrets[u_input]:
                st.session_state["user"] = u_input
                st.rerun()
            else:
                st.error("❌ Error de acceso")
        return False
    return True

if not check_password():
    st.stop()

# Diccionario de textos actual
t = idiomas[st.session_state.lang]

# 3. LÓGICA DE DATOS
def cargar_datos():
    if os.path.exists("inventario.csv"):
        try:
            df = pd.read_csv("inventario.csv")
            df['Caducidad'] = pd.to_datetime(df['Caducidad']).dt.date
            return df
        except:
            return pd.DataFrame(columns=["Nombre", "Stock", "Caducidad", "Ubicación", "Ultimo_Cambio"])
    return pd.DataFrame(columns=["Nombre", "Stock", "Caducidad", "Ubicación", "Ultimo_Cambio"])

def guardar_datos(df):
    df.to_csv("inventario.csv", index=False)

if 'df' not in st.session_state:
    st.session_state.df = cargar_datos()

# 4. INTERFAZ PRINCIPAL
st.title(t["titulo"])
st.session_state.lang = st.radio("Idioma / Language:", ["Español", "English"], horizontal=True)

# BARRA LATERAL
with st.sidebar:
    st.header(t["sidebar_add"])
    with st.form("add_form", clear_on_submit=True):
        n = st.text_input(t["nombre"])
        s = st.number_input(t["cantidad"], min_value=0, value=1)
        v = st.date_input(t["fecha"], value=date.today())
        u = st.selectbox(t["ubicacion"], [t["opcion1"], t["opcion2"]])
        
        if st.form_submit_button(t["btn_guardar"]):
            if n:
                nueva = pd.DataFrame([{"Nombre": n, "Stock": s, "Caducidad": v, "Ubicación": u, "Ultimo_Cambio": st.session_state['user']}])
                st.session_state.df = pd.concat([st.session_state.df, nueva], ignore_index=True)
                guardar_datos(st.session_state.df)
                st.rerun()
    
    st.divider()
    if st.button(t["cerrar"]):
        del st.session_state["user"]
        st.rerun()

# 5. PESTAÑAS PARA LOS DOS INVENTARIOS
tab1, tab2 = st.tabs([f"📁 {t['opcion1']}", f"📁 {t['opcion2']}"])

def mostrar_lista(ubicacion_filtro):
    busqueda = st.text_input(f"{t['buscar']} ({ubicacion_filtro})", key=f"search_{ubicacion_filtro}").lower()
    
    # Filtrar datos por ubicación y búsqueda
    res = st.session_state.df[st.session_state.df["Ubicación"] == ubicacion_filtro].copy()
    if busqueda:
        res = res[res['Nombre'].str.lower().str.contains(busqueda)]
    
    if not res.empty:
        for i, fila in res.iterrows():
            # DISEÑO: Nombre a la izquierda, Fecha a la derecha
            st.markdown(f"""
                <div style="background-color:#f8f9fa; padding:12px; border-radius:8px; border-left: 5px solid #1c3d5a; margin-bottom:8px; color:black;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <span style="font-size:18px;"><b>{fila['Nombre']}</b> (x{fila['Stock']})</span>
                        <span style="font-size:14px; color:#555;">📅 {t['vence']}: <b>{fila['Caducidad']}</b></span>
                    </div>
                    <div style="font-size:11px; color:gray; margin-top:5px;">{t['modificado']}: {fila['Ultimo_Cambio']}</div>
                </div>
            """, unsafe_allow_html=True)
            
            c1, c2, c3, _ = st.columns([0.5, 0.5, 0.5, 8])
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
        st.write(t["vacío"])

with tab1:
    mostrar_lista(t["opcion1"])

with tab2:
    mostrar_lista(t["opcion2"])