import streamlit as st
import pandas as pd
import requests
import time
import unicodedata
import os
import json
from datetime import datetime, timedelta
from st_keyup import st_keyup
from google.cloud import firestore
from google.oauth2 import service_account

# --- 1. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="Gestión Médica Pro", layout="wide", page_icon="💊")

# --- 2. CONEXIÓN FIREBASE (NUBE) ---
if "text_key" in st.secrets:
    try:
        key_dict = json.loads(st.secrets["text_key"]["content"])
        creds = service_account.Credentials.from_service_account_info(key_dict)
        db = firestore.Client(credentials=creds)
    except Exception as e:
        st.error(f"Error en el formato de la llave JSON en Secrets: {e}")
        st.stop()
else:
    st.error("⚠️ Falta la configuración 'text_key' en los Secrets de Streamlit.")
    st.stop()

# --- 3. FUNCIONES DE PERSISTENCIA EN NUBE ---
def guardar_nube(item, coleccion):
    doc_id = str(item.get("Nombre") or item.get("Usuario") or datetime.now().strftime("%Y%m%d%H%M%S%f"))
    db.collection(coleccion).document(doc_id).set(item)

def cargar_nube(coleccion):
    docs = db.collection(coleccion).stream()
    return [doc.to_dict() for doc in docs]

def borrar_nube(doc_id, coleccion):
    db.collection(coleccion).document(str(doc_id)).delete()

# --- 4. INICIALIZACIÓN DE DATOS (CORREGIDO LÍNEA 32) ---
if "db_inventario" not in st.session_state:
    st.session_state.db_inventario = cargar_nube("inventario")
if "db_usuarios" not in st.session_state:
    st.session_state.db_usuarios = cargar_nube("usuarios")
if "db_registro_fijo" not in st.session_state:
    st.session_state.db_registro_fijo = cargar_nube("registros")

# --- 5. LÓGICA DE ACTIVIDAD ---
if "last_activity" not in st.session_state:
    st.session_state.last_activity = time.time()

def actualizar_actividad():
    st.session_state.last_activity = time.time()

if "logueado" in st.session_state and st.session_state.logueado:
    if time.time() - st.session_state.last_activity > 180:
        for key in ["logueado", "user", "role"]:
            if key in st.session_state: del st.session_state[key]
        st.warning("Sesión cerrada por inactividad.")
        st.stop()

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
    [data-testid="stSidebar"] { background-color: #1a1c23 !important; min-width: 350px !important; }
    </style>
""", unsafe_allow_html=True)

# --- 6. MOTOR MÉDICO (AEMPS) ---
def traducir_a_coloquial(nombre_tecnico):
    nombre_tecnico = (nombre_tecnico or "").lower()
    mapeo = {
        "analgésicos": "Para quitar dolores (cabeza, cuerpo, espalda).",
        "antipiréticos": "Para bajar la fiebre.",
        "antiinflamatorios": "Para bajar la hinchazón y el dolor.",
        "protones": "Protector de estómago."
    }
    for clave, explicacion in mapeo.items():
        if clave in nombre_tecnico: return explicacion
    return f"Uso: {nombre_tecnico.capitalize()}."

@st.cache_data(ttl=604800)
def buscar_info_web(nombre):
    try:
        n_bus = nombre.split()[0].strip()
        res = requests.get(f"https://cima.aemps.es/cima/rest/medicamentos?nombre={n_bus}", timeout=5).json()
        if res.get('resultados'):
            m = res['resultados'][0]
            det = requests.get(f"https://cima.aemps.es/cima/rest/medicamento?nregistro={m['nregistro']}").json()
            return {
                "p": m.get('principiosActivos', [{'nombre': 'Desconocido'}])[0]['nombre'].capitalize(), 
                "e": traducir_a_coloquial(det.get('atcs', [{'nombre': 'Uso general'}])[0]['nombre'])
            }
    except: return None
    return None

# --- 7. LOGIN (CORREGIDO LÍNEA 64 Y 72) ---
if "logueado" not in st.session_state: st.session_state.logueado = False

if not st.session_state.logueado:
    st.title("🔐 Acceso Gestión Médica")
    with st.form("login"):
        u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            actualizar_actividad()
            # Corrección línea 64: Verificación segura de secrets
            users_dict = st.secrets.get("users", {})
            if u in users_dict and str(p) == str(users_dict[u]):
                st.session_state.update({"logueado": True, "user": u, "role": "admin"})
                st.rerun()
            else:
                # Corrección línea 72: Verificación de lista de usuarios
                user_data = next((item for item in st.session_state.db_usuarios if str(item.get("Usuario")) == str(u) and str(item.get("Clave")) == str(p)), None)
                if user_data:
                    st.session_state.update({"logueado": True, "user": u, "role": user_data["Rol"]})
                    st.rerun()
                else: st.error("Acceso denegado.")
    st.stop()

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
            n = st.text_input("Nombre").upper()
            s = st.number_input("Cantidad", 1)
            f = st.date_input("Vencimiento")
            u = st.selectbox("Lugar", ["Medicación de vitrina", "Medicación de armario"])
            if st.form_submit_button("Registrar"):
                actualizar_actividad()
                if n:
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
                    st.success(f"{n} añadido."); time.sleep(0.5); st.rerun()

# --- 9. BÚSQUEDA ---
st.title("💊 Inventario Médico")
raw_query = st_keyup("🔍 Busca por nombre o ubicación...", key="search_main", on_change=actualizar_actividad).strip()

def normalize(t):
    return ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn').lower()

df_master = pd.DataFrame(st.session_state.db_inventario)
df_vis = df_master.copy()
if raw_query and not df_vis.empty:
    q = normalize(raw_query)
    df_vis = df_vis[df_vis.apply(lambda r: q in normalize(str(r["Nombre"])) or q in normalize(str(r["Ubicacion"])), axis=1)]

# TABS
titulos = ["📋 Todo", "💊 Vitrina", "📦 Armario"]
if st.session_state.role == "admin": titulos.extend(["👥 Usuarios", "📜 Registro Fijo"])
tabs = st.tabs(titulos)

# --- 10. FUNCIÓN TARJETA (CORREGIDO LÍNEA 151, 153, 157) ---
def dibujar_tarjeta(fila, key_tab):
    nombre, stock, cad = fila["Nombre"], int(fila["Stock"]), fila["Caducidad"]
    # Corrección línea 151 y 153: Manejo de formato de fecha
    try:
        fecha_vence = datetime.strptime(cad, "%Y-%m-%d")
    except:
        fecha_vence = datetime.now()
        
    hoy = datetime.now()
    # Corrección línea 157: Comparación de fechas
    col_borde = "#ff4b4b" if fecha_vence.date() < hoy.date() else "#ffcc00" if fecha_vence.date() <= (hoy + timedelta(days=30)).date() else "#28a745"
    
    st.markdown(f'<div class="tarjeta-med" style="border-left-color: {col_borde}"><b>{nombre}</b><br><small>{stock} uds | {fila["Ubicacion"]} | Vence: {cad}</small></div>', unsafe_allow_html=True)
    
    # Obtener info guardada o buscar si no existe
    p_act = fila.get("Principio", "No disponible")
    d_uso = fila.get("Descripcion", "Sin datos.")

    with st.expander("🤔 ¿Para qué sirve?"):
        actualizar_actividad()
        if st.session_state.role == "admin":
            with st.form(f"edit_info_{nombre}_{key_tab}"):
                nuevo_p = st.text_input("Principio Activo", p_act)
                nueva_d = st.text_area("Descripción/Uso", d_uso)
                if st.form_submit_button("💾 Guardar Cambios"):
                    idx_real = next((i for i, item in enumerate(st.session_state.db_inventario) if item["Nombre"] == nombre), None)
                    if idx_real is not None:
                        st.session_state.db_inventario[idx_real]["Principio"] = nuevo_p
                        st.session_state.db_inventario[idx_real]["Descripcion"] = nueva_d
                        guardar_nube(st.session_state.db_inventario[idx_real], "inventario")
                        st.success("Info actualizada"); time.sleep(0.5); st.rerun()
        else:
            st.markdown(f'<div class="caja-info"><b>Principio Activo:</b> {p_act}<br><br><b>Descripción:</b> {d_uso}</div>', unsafe_allow_html=True)

    idx_real = next((i for i, item in enumerate(st.session_state.db_inventario) if item["Nombre"] == nombre), None)

    if idx_real is not None:
        if st.session_state.role == "admin":
            c1, c2, c3 = st.columns([2, 2, 1])
            if c1.button(f"💊 QUITAR 1", key=f"q_{nombre}_{key_tab}"):
                st.session_state.db_inventario[idx_real]["Stock"] = max(0, stock - 1)
                guardar_nube(st.session_state.db_inventario[idx_real], "inventario")
                reg = {"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Persona": st.session_state.user, "Medicamento": nombre, "Movimiento": "RETIRADA (-1)"}
                st.session_state.db_registro_fijo.append(reg)
                guardar_nube(reg, "registros")
                st.rerun()
            if c2.button(f"➕ AÑADIR 1", key=f"a_{nombre}_{key_tab}"):
                st.session_state.db_inventario[idx_real]["Stock"] = stock + 1
                guardar_nube(st.session_state.db_inventario[idx_real], "inventario")
                reg = {"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Persona": st.session_state.user, "Medicamento": nombre, "Movimiento": "ADICIÓN (+1)"}
                st.session_state.db_registro_fijo.append(reg)
                guardar_nube(reg, "registros")
                st.rerun()
            if c3.button("🗑", key=f"d_{nombre}_{key_tab}"):
                reg_del = {"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Persona": st.session_state.user, "Medicamento": nombre, "Movimiento": "ELIMINACIÓN TOTAL"}
                st.session_state.db_registro_fijo.append(reg_del)
                guardar_nube(reg_del, "registros")
                borrar_nube(nombre, "inventario")
                st.session_state.db_inventario.pop(idx_real)
                st.rerun()
        else:
            if st.button(f"💊 QUITAR 1", key=f"q_{nombre}_{key_tab}"):
                st.session_state.db_inventario[idx_real]["Stock"] = max(0, stock - 1)
                guardar_nube(st.session_state.db_inventario[idx_real], "inventario")
                reg = {"Fecha": datetime.now().strftime("%d/%m/%Y %H:%M"), "Persona": st.session_state.user, "Medicamento": nombre, "Movimiento": "RETIRADA (-1)"}
                st.session_state.db_registro_fijo.append(reg)
                guardar_nube(reg, "registros")
                st.rerun()

# --- 11. RENDER (CORREGIDO LÍNEA 199) ---
for i, t_nom in enumerate(titulos):
    with tabs[i]:
        if t_nom == "👥 Usuarios":
            with st.form("nu"):
                nu, np, nr = st.columns(3)
                u_in, p_in, r_in = nu.text_input("Usuario"), np.text_input("Clave"), nr.selectbox("Rol", ["user", "admin"])
                if st.form_submit_button("Crear"):
                    nuevo_u = {"Usuario": u_in, "Clave": p_in, "Rol": r_in}
                    st.session_state.db_usuarios.append(nuevo_u)
                    guardar_nube(nuevo_u, "usuarios"); st.rerun()
            # Corrección línea 199: Uso de list() para evitar errores al modificar la lista mientras se itera
            for idx, user in enumerate(list(st.session_state.db_usuarios)):
                col1, col2 = st.columns([4, 1])
                col1.write(f"👤 {user['Usuario']} ({user['Rol']})")
                if col2.button("Borrar", key=f"u_{idx}"):
                    borrar_nube(user['Usuario'], "usuarios")
                    st.session_state.db_usuarios.pop(idx); st.rerun()
        
        elif t_nom == "📜 Registro Fijo":
            st.subheader("📋 Registro Histórico (Firestore)")
            if st.session_state.db_registro_fijo:
                df_reg = pd.DataFrame(st.session_state.db_registro_fijo)
                st.dataframe(df_reg.iloc[::-1], use_container_width=True, hide_index=True)
            else: st.info("No hay registros aún.")
            
        else:
            filtro = "vitrina" if "Vitrina" in t_nom else "armario" if "Armario" in t_nom else ""
            if not df_vis.empty:
                for _, fila in df_vis.iterrows():
                    if not filtro or filtro in fila["Ubicacion"].lower():
                        dibujar_tarjeta(fila, i)
            else:
                st.info("No hay medicación disponible.")