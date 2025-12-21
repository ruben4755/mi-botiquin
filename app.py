import streamlit as st
import pandas as pd
import gspread
import requests
import time
import unicodedata
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from st_keyup import st_keyup

# --- 1. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="Gestión Médica Pro", layout="wide", page_icon="💊")

# --- CONTROL DE INACTIVIDAD (3 MINUTOS) ---
if "last_activity" not in st.session_state:
    st.session_state.last_activity = time.time()

if "logueado" in st.session_state and st.session_state.logueado:
    if time.time() - st.session_state.last_activity > 180:
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.warning("Sesión cerrada por seguridad (Inactividad).")
        st.stop()

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .tarjeta-med { 
        color: #ffffff !important; background: #1e2128; padding: 18px; 
        border-radius: 12px; margin-bottom: 12px; border-left: 10px solid #28a745;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
    }
    .caja-info {
        background: #262730; border-radius: 10px; padding: 15px;
        color: #eeeeee !important; border: 1px solid #444; margin: 10px 0;
    }
    [data-testid="stSidebar"] { background-color: #1a1c23 !important; min-width: 350px !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR DE TRADUCCIÓN COLOQUIAL ---
def traducir_a_coloquial(nombre_tecnico):
    nombre_tecnico = (nombre_tecnico or "").lower()
    mapeo = {
        "analgésicos": "Para quitar dolores (cabeza, cuerpo, espalda).",
        "antipiréticos": "Para bajar la fiebre.",
        "antiinflamatorios": "Para bajar la hinchazón y el dolor.",
        "protones": "Protector de estómago. Para que no siente mal la medicación.",
        "antibacterianos": "Antibiótico para infecciones.",
        "antihistamínicos": "Para alergias, estornudos y picores.",
        "antitusígenos": "Para calmar la tos seca.",
        "ansiolíticos": "Para los nervios o ayudarte a dormir.",
        "antihipertensivos": "Para la tensión alta.",
        "antidiabéticos": "Para el azúcar en sangre."
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
            p_activo = m.get('principiosActivos', [{'nombre': 'Desconocido'}])[0]['nombre'].capitalize()
            det = requests.get(f"https://cima.aemps.es/cima/rest/medicamento?nregistro={m['nregistro']}").json()
            uso_tecnico = det.get('atcs', [{'nombre': 'Uso general'}])[0]['nombre']
            return {"p": p_activo, "e": traducir_a_coloquial(uso_tecnico)}
    except: return None
    return None

# --- 3. CONEXIÓN ---
@st.cache_resource
def conectar_gsheets():
    try:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets"])
        sh = gspread.authorize(creds).open_by_url(st.secrets["url_excel"])
        ws_inv = sh.get_worksheet(0)
        titles = [w.title for w in sh.worksheets()]
        ws_not = sh.worksheet("Notas") if "Notas" in titles else sh.add_worksheet("Notas", 500, 3)
        ws_his = sh.worksheet("Historial") if "Historial" in titles else sh.add_worksheet("Historial", 2000, 4)
        return ws_inv, ws_not, ws_his
    except: return None, None, None

ws_inv, ws_not, ws_his = conectar_gsheets()

# --- 4. LOGIN ---
if "logueado" not in st.session_state: st.session_state.logueado = False

if not st.session_state.logueado:
    st.title("🔐 Acceso")
    with st.form("login"):
        u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if u in st.secrets["users"] and str(p) == str(st.secrets["users"][u]):
                st.session_state.update({"logueado": True, "user": u, "role": st.secrets["roles"].get(u, "user"), "last_activity": time.time()})
                st.rerun()
    st.stop()

# --- 5. CARGA DE DATOS ---
def cargar_inventario():
    try:
        data = ws_inv.get_all_values()
        if len(data) < 2: return pd.DataFrame()
        df = pd.DataFrame(data[1:], columns=[h.strip() for h in data[0]])
        df["Stock"] = pd.to_numeric(df["Stock"], errors='coerce').fillna(0).astype(int)
        df["Nombre"] = df["Nombre"].astype(str).str.strip()
        return df
    except: return pd.DataFrame()

df_master = cargar_inventario()

# --- 6. SIDEBAR (FORMULARIO E HISTORIAL) ---
with st.sidebar:
    st.header(f"👤 {st.session_state.user.capitalize()}")
    if st.button("🚪 Salir"): 
        st.session_state.clear()
        st.rerun()
    
    if st.session_state.role == "admin":
        st.divider()
        st.subheader("➕ Añadir Medicación")
        with st.form("alta", clear_on_submit=True):
            n = st.text_input("Nombre").upper()
            s = st.number_input("Cantidad", 1)
            f = st.date_input("Vencimiento")
            u = st.selectbox("Lugar", ["Medicación de vitrina", "Medicación de armario"])
            if st.form_submit_button("Registrar"):
                if n:
                    ws_inv.append_row([n, s, str(f), u])
                    ws_his.append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state.user, "ALTA", n])
                    st.session_state.last_activity = time.time()
                    st.success(f"{n} registrado.")
                    time.sleep(1)
                    st.rerun()

        st.divider()
        st.subheader("📜 Historial de Movimientos")
        try:
            h_data = ws_his.get_all_values()
            if len(h_data) > 1:
                df_h = pd.DataFrame(h_data[1:], columns=h_data[0]).tail(10)
                st.dataframe(df_h.iloc[::-1], use_container_width=True, hide_index=True)
            else:
                st.caption("No hay registros.")
        except:
            st.error("Error al cargar historial.")

# --- 7. BÚSQUEDA ---
def normalize(t):
    return ''.join(c for c in unicodedata.normalize('NFD', t) if unicodedata.category(c) != 'Mn').lower()

st.title("💊 Inventario Médico")
raw_query = st_keyup("🔍 Busca por nombre o lugar...", key="search_main").strip()

if raw_query:
    st.session_state.last_activity = time.time()

df_vis = df_master[df_master["Stock"] > 0].copy() if not df_master.empty else pd.DataFrame()

if raw_query and not df_vis.empty:
    q = normalize(raw_query)
    df_vis = df_vis[df_vis.apply(lambda r: q in normalize(r["Nombre"]) or q in normalize(r["Ubicacion"]), axis=1)]

tabs = st.tabs(["📋 Todo", "💊 Vitrina", "📦 Armario"])

# --- 8. FUNCIÓN TARJETA ---
def dibujar_tarjeta(fila, key_tab):
    try:
        nombre = fila["Nombre"]
        stock = int(fila["Stock"])
        cad = fila["Caducidad"]
        
        f_vence = datetime.strptime(cad, "%Y-%m-%d")
        col = "#28a745" if f_vence > datetime.now() + timedelta(days=30) else "#ffa500" if f_vence > datetime.now() else "#ff4b4b"

        st.markdown(f'<div class="tarjeta-med" style="border-left-color: {col}"><b>{nombre}</b><br><small>{stock} uds | {fila["Ubicacion"]} | Vence: {cad}</small></div>', unsafe_allow_html=True)
        
        with st.expander("🤔 ¿Para qué sirve?"):
            notas_data = ws_not.get_all_values()
            nota_m = next((r for r in notas_data if r[0] == nombre), None)
            
            if nota_m: p_act, d_uso = nota_m[1], nota_m[2]
            else:
                info = buscar_info_web(nombre)
                p_act, d_uso = (info['p'], info['e']) if info else ("No disponible", "Sin datos.")
            
            st.markdown(f'<div class="caja-info"><b>Principio Activo:</b> {p_act}<br><br><b>Descripción:</b> {d_uso}</div>', unsafe_allow_html=True)
            
            # NUEVO: Edición de descripción solo para ADMIN
            if st.session_state.role == "admin":
                with st.form(f"edit_info_{nombre}_{key_tab}"):
                    nuevo_p = st.text_input("Editar Principio Activo", p_act)
                    nueva_d = st.text_area("Editar Descripción Coloquial", d_uso)
                    if st.form_submit_button("Guardar cambios en descripción"):
                        celda = ws_not.find(nombre)
                        if celda:
                            ws_not.update_row(celda.row, [nombre, nuevo_p, nueva_d])
                        else:
                            ws_not.append_row([nombre, nuevo_p, nueva_d])
                        st.success("Información actualizada.")
                        time.sleep(1)
                        st.rerun()

        c1, c2 = st.columns([4, 1])
        if c1.button(f"💊 RETIRAR 1 UNIDAD", key=f"ret_{nombre}_{key_tab}"):
            st.session_state.last_activity = time.time()
            celda = ws_inv.find(nombre)
            if celda:
                ws_inv.update_cell(celda.row, 2, max(0, stock - 1))
                ws_his.append_row([datetime.now().strftime("%d/%m/%Y %H:%M"), st.session_state.user, "RETIRADA", nombre])
                st.toast(f"✅ {st.session_state.user} retiró {nombre}")
                time.sleep(1)
                st.rerun()

        if st.session_state.role == "admin" and c2.button("🗑", key=f"del_{nombre}_{key_tab}"):
            celda = ws_inv.find(nombre)
            if celda:
                ws_inv.delete_rows(celda.row)
                st.rerun()
    except: pass

# --- 9. RENDER ---
for i, filtro in enumerate(["", "vitrina", "armario"]):
    with tabs[i]:
        if df_vis.empty: st.caption("No hay resultados.")
        else:
            df_f = df_vis if not filtro else df_vis[df_vis["Ubicacion"].str.contains(filtro, case=False)]
            for _, fila in df_f.iterrows(): dibujar_tarjeta(fila, i)