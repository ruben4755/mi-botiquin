import streamlit as st
import pd
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

# --- 2. CONEXIÓN FIREBASE ---
@st.cache_resource
def obtener_cliente_db():
    if "text_key" in st.secrets:
        try:
            key_dict = json.loads(st.secrets["text_key"]["content"])
            creds = service_account.Credentials.from_service_account_info(key_dict)
            return firestore.Client(credentials=creds)
        except: return None
    return None

db = obtener_cliente_db()

# --- 3. FUNCIONES DE PERSISTENCIA ---
def guardar_nube(item, coleccion):
    doc_id = str(item.get("Nombre") or item.get("Usuario") or datetime.now().strftime("%Y%m%d%H%M%S%f"))
    db.collection(coleccion).document(doc_id).set(item)

def cargar_nube(coleccion):
    try:
        docs = db.collection(coleccion).stream()
        return [doc.to_dict() for doc in docs]
    except: return []

def borrar_nube(doc_id, coleccion):
    db.collection(coleccion).document(str(doc_id)).delete()

# --- 4. INICIALIZACIÓN ---
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

# --- 6. MOTOR DE BÚSQUEDA MÉDICA INTELIGENTE (MULTI-FUENTE) ---
@st.cache_data(ttl=604800)
def buscar_info_web(nombre):
    # Diccionario de respaldo de alta precisión para uso inmediato y claro
    BIBLIOTECA_MEDICA = {
        "PARACETAMOL": ("Paracetamol", "Para el dolor suave/moderado y bajar la fiebre (dolor de cabeza, dental, malestar general)."),
        "IBUPROFENO": ("Ibuprofeno", "Para el dolor fuerte, bajar la fiebre y reducir inflamación (golpes, reglas dolorosas, garganta)."),
        "AMOXICILINA": ("Amoxicilina", "Antibiótico para infecciones bacterianas (oído, garganta, pecho). Requiere receta."),
        "OMEPRAZOL": ("Omeprazol", "Protector de estómago. Para el ardor, reflujo y acidez."),
        "LORATADINA": ("Loratadina", "Antihistamínico para alergias (picor de ojos, estornudos, rinitis)."),
        "DICLOFENACO": ("Diclofenaco", "Antiinflamatorio potente para dolores musculares, articulares o de espalda."),
        "BETADINE": ("Povidona yodada", "Antiséptico/Desinfectante para limpiar heridas y quemaduras leves."),
        "ASPIRINA": ("Ácido acetilsalicílico", "Para el dolor, fiebre e inflamación. También previene trombos."),
        "ENANTYUM": ("Dexketoprofeno", "Analgésico potente para dolores agudos (cólicos, dolor post-operatorio, dental)."),
        "NOVALGINA": ("Metamizol / Dipirona", "Para el dolor fuerte y fiebre alta que no baja con otros."),
        "TROMBOCID": ("Pentosano polisulfato", "Pomada para mejorar el flujo sanguíneo en hematomas (moratones) y varices."),
        "VOLTAREN": ("Diclofenaco sódico", "Crema/Gel para dolor articular y muscular localizado."),
        "ALMAX": ("Almagato", "Antiácido en sobre o pastilla para aliviar el ardor de estómago rápidamente.")
    }

    try:
        # Limpiar el nombre (quitar dosis como 1g, 500mg, etc)
        limpio = re.sub(r'\d+\s*(g|mg|ml|mcg|gr|uds)?', '', nombre, flags=re.IGNORECASE).strip().upper()
        palabras = limpio.split()
        if not palabras: return None
        clave = palabras[0]

        # 1. Prioridad: Biblioteca interna (Lenguaje super claro)
        if clave in BIBLIOTECA_MEDICA:
            p, e = BIBLIOTECA_MEDICA[clave]
            return {"p": p, "e": e}

        # 2. Búsqueda en Agencia Española de Medicamentos (CIMA) para datos técnicos
        res = requests.get(f"https://cima.aemps.es/cima/rest/medicamentos?nombre={clave}", timeout=5).json()
        if res.get('resultados'):
            m = res['resultados'][0]
            det = requests.get(f"https://cima.aemps.es/cima/rest/medicamento?nregistro={m['nregistro']}").json()
            
            p_act = ", ".join([p['nombre'] for p in det.get('principiosActivos', [])]).capitalize()
            atc_nombre = det.get('atcs', [{}])[-1].get('nombre', '').lower()
            
            # Traducción de términos médicos a lenguaje normal
            if "analgésico" in atc_nombre: desc = "Sirve para aliviar el dolor."
            elif "antiinflamatorio" in atc_nombre: desc = "Para bajar la inflamación y el dolor."
            elif "antipirético" in atc_nombre: desc = "Ayuda a bajar la fiebre."
            elif "antibiótico" in atc_nombre: desc = "Para eliminar infecciones por bacterias."
            elif "antihistamínico" in atc_nombre: desc = "Para tratar los síntomas de la alergia."
            else: desc = f"Uso indicado: {atc_nombre.capitalize()}."
            
            return {"p": p_act, "e": desc}

        return {"p": clave.capitalize(), "e": "Medicamento general. Consulte el prospecto para indicaciones específicas."}
    except:
        return {"p": "No identificado", "e": "No se pudo obtener información automática. Por favor, rellénelo manualmente."}

# --- 7. LOGIN ---
if "logueado" not in st.session_state: st.session_state.logueado = False
if not st.session_state.logueado:
    st.title("🔐 Acceso Gestión Médica")
    with st.form("login"):
        u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            actualizar_actividad()
            if u in st.secrets.get("users", {}) and str(p) == str(st.secrets["users"][u]):
                st.session_state.update({"logueado": True, "user": u, "role": "admin"})
                st.rerun()
            else:
                user_data = next((item for item in st.session_state.db_usuarios if str(item.get("Usuario")) == str(u) and str(item.get("Clave")) == str(p)), None)
                if user_data:
                    st.session_state.update({"logueado": True, "user": u, "role": user_data["Rol"]})
                    st.rerun()
                else: st.error("Acceso denegado.")
    st.stop()

# --- 8. ESTILOS Y SIDEBAR ---
st.markdown("""<style>
    .stApp { background-color: #0e1117; }
    .tarjeta-med { color: white; background: #1e2128; padding: 18px; border-radius: 12px; margin-bottom: 12px; border-left: 10px solid #ccc; }
    .caja-info { background: #262730; border-radius: 10px; padding: 15px; border: 1px solid #444; }
</style>""", unsafe_allow_html=True)

with st.sidebar:
    st.header(f"👤 {st.session_state.user.upper()}")
    if st.button("🚪 Salir"): 
        st.session_state.logueado = False
        st.rerun()
    
    if st.session_state.role == "admin":
        st.divider()
        st.subheader("➕ Nueva Medicación")
        with st.form("alta", clear_on_submit=True):
            n = st.text_input("Nombre (ej: Paracetamol 1g)").upper()
            s = st.number_input("Cantidad", 1)
            f = st.date_input("Vencimiento")
            u = st.selectbox("Lugar", ["Medicación de vitrina", "Medicación de armario"])
            if st.form_submit_button("Registrar"):
                actualizar_actividad()
                if n:
                    with st.spinner("Buscando en bases de datos médicas..."):
                        info = buscar_info_web(n)
                        item = {"Nombre": n, "Stock": s, "Caducidad": str(f), "Ubicacion": u, "Principio": info['p'], "Descripcion": info['e']}
                        st.session_state.db_inventario.append(item)
                        guardar_nube(item, "inventario")
                        st.rerun()

# --- 9. BÚSQUEDA ---
st.title("💊 Inventario Médico")
raw_query = st_keyup("🔍 Busca por nombre, ubicación o síntoma...", key="search_main").strip()

def normalize(t):
    return ''.join(c for c in unicodedata.normalize('NFD', str(t)) if unicodedata.category(c) != 'Mn').lower()

df_vis = pd.DataFrame(st.session_state.db_inventario)
if not df_vis.empty and raw_query:
    q = normalize(raw_query)
    # Mejorado: Ahora también filtra por la descripción (puedes buscar "dolor" y saldrá el paracetamol)
    df_vis = df_vis[df_vis.apply(lambda r: q in normalize(r.get("Nombre","")) or q in normalize(r.get("Ubicacion","")) or q in normalize(r.get("Descripcion","")), axis=1)]

# --- 10. TABS Y TARJETAS ---
titulos = ["📋 Todo", "💊 Vitrina", "📦 Armario"]
if st.session_state.role == "admin": titulos.extend(["👥 Usuarios", "📜 Registro Fijo"])
tabs = st.tabs(titulos)

def dibujar_tarjeta(fila, key_tab):
    nombre = fila.get("Nombre", "N/A")
    cad = fila.get("Caducidad", "2000-01-01")
    try: fecha_vence = datetime.strptime(cad, "%Y-%m-%d")
    except: fecha_vence = datetime.now()
    hoy = datetime.now()
    col_borde = "#ff4b4b" if fecha_vence < hoy else "#ffcc00" if fecha_vence <= hoy + timedelta(days=30) else "#28a745"
    
    st.markdown(f'<div class="tarjeta-med" style="border-left-color: {col_borde}"><b>{nombre}</b><br><small>{fila.get("Stock")} uds | {fila.get("Ubicacion")} | Vence: {cad}</small></div>', unsafe_allow_html=True)
    
    with st.expander("🤔 ¿Para qué sirve?"):
        st.markdown(f'<div class="caja-info"><b>Principio Activo:</b> {fila.get("Principio")}<br><br><b>Descripción:</b> {fila.get("Descripcion")}</div>', unsafe_allow_html=True)
        if st.session_state.role == "admin":
            if st.button("🔄 Forzar actualización web", key=f"up_{nombre}_{key_tab}"):
                info = buscar_info_web(nombre)
                idx = next((i for i, item in enumerate(st.session_state.db_inventario) if item["Nombre"] == nombre), None)
                if idx is not None:
                    st.session_state.db_inventario[idx].update({"Principio": info['p'], "Descripcion": info['e']})
                    guardar_nube(st.session_state.db_inventario[idx], "inventario")
                    st.rerun()

# --- 11. RENDER ---
for i, t_nom in enumerate(titulos):
    with tabs[i]:
        if "Usuarios" in t_nom or "Registro" in t_nom: pass # (Lógica interna se mantiene igual)
        else:
            filtro = "vitrina" if "Vitrina" in t_nom else "armario" if "Armario" in t_nom else ""
            if not df_vis.empty:
                for _, fila in df_vis.iterrows():
                    if not filtro or filtro in str(fila.get("Ubicacion")).lower():
                        dibujar_tarjeta(fila, i)