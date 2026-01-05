import streamlit as st
import pandas as pd
import requests
import time
import unicodedata
import os
import json
import re
from datetime import datetime, timedelta
from st_keyup import st_keyup
from google.cloud import firestore
from google.oauth2 import service_account

# --- 1. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="Gestión Médica Pro", layout="wide", page_icon="💊")

# --- 2. CONEXIÓN FIREBASE (NUBE) ---
# Se mantiene la conexión pero se asegura que sea persistente
@st.cache_resource
def get_db_client():
    if "text_key" in st.secrets:
        key_dict = json.loads(st.secrets["text_key"]["content"])
        creds = service_account.Credentials.from_service_account_info(key_dict)
        return firestore.Client(credentials=creds)
    return None

db = get_db_client()

if not db:
    st.error("⚠️ Error de configuración en Secrets.")
    st.stop()

# --- 3. FUNCIONES DE PERSISTENCIA ---
def guardar_nube(item, coleccion):
    doc_id = str(item.get("Nombre") or item.get("Usuario") or datetime.now().strftime("%Y%m%d%H%M%S%f"))
    db.collection(coleccion).document(doc_id).set(item)

def cargar_nube(coleccion):
    try:
        docs = db.collection(coleccion).stream()
        return [doc.to_dict() for doc in docs]
    except:
        return []

def borrar_nube(doc_id, coleccion):
    db.collection(coleccion).document(str(doc_id)).delete()

# --- 4. INICIALIZACIÓN DE DATOS (RE-CARGA AUTOMÁTICA) ---
# Esto evita que la app aparezca vacía tras días de inactividad
if "db_inventario" not in st.session_state or not st.session_state.db_inventario:
    st.session_state.db_inventario = cargar_nube("inventario")
if "db_usuarios" not in st.session_state or not st.session_state.db_usuarios:
    st.session_state.db_usuarios = cargar_nube("usuarios")
if "db_registro_fijo" not in st.session_state or not st.session_state.db_registro_fijo:
    st.session_state.db_registro_fijo = cargar_nube("registros")

# --- 5. LÓGICA DE ACTIVIDAD ---
if "last_activity" not in st.session_state:
    st.session_state.last_activity = time.time()

def actualizar_actividad():
    st.session_state.last_activity = time.time()

# --- 6. MOTOR MÉDICO PROFESIONAL (CORREGIDO PARA BUSQUEDAS ESPECÍFICAS) ---
@st.cache_data(ttl=604800)
def buscar_info_web(nombre):
    try:
        # Limpiamos el nombre: quitamos gramos (1g, 500mg), números y símbolos
        n_limpio = re.sub(r'\d+(g|mg|ml|mcg)?', '', nombre, flags=re.IGNORECASE)
        n_bus = n_limpio.strip().split()[0] # Tomamos la primera palabra clave
        
        res = requests.get(f"https://cima.aemps.es/cima/rest/medicamentos?nombre={n_bus}", timeout=10).json()
        
        if res.get('resultados'):
            # Buscamos el mejor match que contenga la palabra clave
            m = res['resultados'][0]
            det = requests.get(f"https://cima.aemps.es/cima/rest/medicamento?nregistro={m['nregistro']}").json()
            
            pas = [p['nombre'] for p in det.get('principiosActivos', [])]
            p_final = ", ".join(pas).capitalize()
            
            # Buscamos el uso clínico en la sección ATC
            atcs = det.get('atcs', [])
            uso = "Uso clínico general"
            if atcs:
                # El último nivel del ATC suele ser el más específico
                uso = atcs[-1]['nombre'].capitalize()
            
            return {"p": p_final, "e": f"Indicado para: {uso}"}
    except Exception as e:
        return {"p": "No encontrado", "e": "Detalles no disponibles en AEMPS."}
    return None

# --- 7. LOGIN ---
if "logueado" not in st.session_state: st.session_state.logueado = False

if not st.session_state.logueado:
    st.title("🔐 Acceso Gestión Médica")
    with st.form("login"):
        u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            actualizar_actividad()
            users_dict = st.secrets.get("users", {})
            if u in users_dict and str(p) == str(users_dict[u]):
                st.session_state.update({"logueado": True, "user": u, "role": "admin"})
                st.rerun()
            else:
                user_data = next((item for item in st.session_state.db_usuarios if str(item.get("Usuario")) == str(u) and str(item.get("Clave")) == str(p)), None)
                if user_data:
                    st.session_state.update({"logueado": True, "user": u, "role": user_data["Rol"]})
                    st.rerun()
                else: st.error("Acceso denegado.")
    st.stop()

# --- Estilos ---
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .tarjeta-med { 
        color: #ffffff !important; background: #1e2128; padding: 18px; 
        border-radius: 12px; margin-bottom: 12px; border-left: 10px solid #ccc;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
    .caja-info {
        background: #262730; border-radius: 10px; padding: 15px;
        color: #eeeeee !important; border: 1px solid #444; margin: 10px 0;
    }
    </style>
""", unsafe_allow_html=True)

# --- 8. SIDEBAR ---
with st.sidebar:
    st.header(f"👤 {st.session_state.user.upper()}")
    if st.button("🚪 Salir"): 
        st.session_state.logueado = False
        st.rerun()
    
    if st.session_state.role == "admin":
        st.divider()
        st.subheader("➕ Nueva Medicación")
        with st.form("alta", clear_on_submit=True):
            n = st.text_input("Nombre (ej. Paracetamol)").upper()
            s = st.number_input("Cantidad", 1)
            f = st.date_input("Vencimiento")
            u = st.selectbox("Lugar", ["Medicación de vitrina", "Medicación de armario"])
            if st.form_submit_button("Registrar"):
                actualizar_actividad()
                if n:
                    with st.spinner("Buscando información profesional..."):
                        info_web = buscar_info_web(n)
                        p_act = info_web['p'] if info_web else "No disponible"
                        desc = info_web['e'] if info_web else "Sin datos."
                    
                    item_nuevo = {
                        "Nombre": n, "Stock": s, "Caducidad": str(f), 
                        "Ubicacion": u, "Principio": p_act, "Descripcion": desc
                    }
                    st.session_state.db_inventario.append(item_nuevo)
                    guardar_nube(item_nuevo, "inventario")
                    
                    reg_alta = {"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Persona": st.session_state.user, "Medicamento": n, "Movimiento": f"ALTA NUEVA ({s} uds)"}
                    st.session_state.db_registro_fijo.append(reg_alta)
                    guardar_nube(reg_alta, "registros")
                    st.rerun()

# --- 9. BÚSQUEDA ---
st.title("💊 Inventario Médico")
raw_query = st_keyup("🔍 Busca por nombre o ubicación...", key="search_main").strip()

def normalize(t):
    return ''.join(c for c in unicodedata.normalize('NFD', str(t)) if unicodedata.category(c) != 'Mn').lower()

df_vis = pd.DataFrame(st.session_state.db_inventario)
if not df_vis.empty and raw_query:
    q = normalize(raw_query)
    df_vis = df_vis[df_vis.apply(lambda r: q in normalize(r.get("Nombre","")) or q in normalize(r.get("Ubicacion","")), axis=1)]

# TABS
titulos = ["📋 Todo", "💊 Vitrina", "📦 Armario"]
if st.session_state.role == "admin": titulos.extend(["👥 Usuarios", "📜 Registro Fijo"])
tabs = st.tabs(titulos)

# --- 10. FUNCIÓN TARJETA ---
def dibujar_tarjeta(fila, key_tab):
    nombre = fila.get("Nombre", "N/A")
    stock = fila.get("Stock", 0)
    cad = fila.get("Caducidad", "2000-01-01")
    
    try: fecha_vence = datetime.strptime(cad, "%Y-%m-%d")
    except: fecha_vence = datetime.now()
        
    hoy = datetime.now()
    col_borde = "#ff4b4b" if fecha_vence < hoy else "#ffcc00" if fecha_vence <= hoy + timedelta(days=30) else "#28a745"
    
    st.markdown(f'<div class="tarjeta-med" style="border-left-color: {col_borde}"><b>{nombre}</b><br><small>{stock} uds | {fila.get("Ubicacion")} | Vence: {cad}</small></div>', unsafe_allow_html=True)
    
    p_act = fila.get("Principio", "Consultar prospecto")
    d_uso = fila.get("Descripcion", "Uso general")

    with st.expander("🤔 ¿Para qué sirve?"):
        if st.session_state.role == "admin":
            with st.form(f"edit_{nombre}_{key_tab}"):
                nuevo_p = st.text_input("Principio Activo", p_act)
                nueva_d = st.text_area("Descripción", d_uso)
                if st.form_submit_button("💾 Actualizar"):
                    idx = next((i for i, item in enumerate(st.session_state.db_inventario) if item["Nombre"] == nombre), None)
                    if idx is not None:
                        st.session_state.db_inventario[idx].update({"Principio": nuevo_p, "Descripcion": nueva_d})
                        guardar_nube(st.session_state.db_inventario[idx], "inventario")
                        st.rerun()
        else:
            st.markdown(f'<div class="caja-info"><b>Principio Activo:</b> {p_act}<br><br><b>Descripción:</b> {d_uso}</div>', unsafe_allow_html=True)

# --- 11. RENDER ---
for i, t_nom in enumerate(titulos):
    with tabs[i]:
        if "Usuarios" in t_nom:
            # Lógica de usuarios (se mantiene igual)
            for idx, user in enumerate(list(st.session_state.db_usuarios)):
                st.write(f"👤 {user['Usuario']}")
        elif "Registro" in t_nom:
            if st.session_state.db_registro_fijo:
                st.table(pd.DataFrame(st.session_state.db_registro_fijo).iloc[::-1])
        else:
            filtro = "vitrina" if "Vitrina" in t_nom else "armario" if "Armario" in t_nom else ""
            if not df_vis.empty:
                for _, fila in df_vis.iterrows():
                    if not filtro or filtro in str(fila.get("Ubicacion")).lower():
                        dibujar_tarjeta(fila, i)