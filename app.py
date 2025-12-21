import streamlit as st
import pandas as pd
import gspread
import requests
import time
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from st_keyup import st_keyup
from streamlit_autorefresh import st_autorefresh

# --- 1. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="Gestión Médica Pro", layout="wide", page_icon="💊")

# Script para auto-cierre por inactividad (3 minutos = 180 segundos)
if "last_activity" not in st.session_state:
    st.session_state.last_activity = time.time()

# Detectar inactividad
if st.session_state.get("logueado"):
    tiempo_transcurrido = time.time() - st.session_state.last_activity
    if tiempo_transcurrido > 180:
        st.session_state.clear()
        st.rerun()
    # Refresco silencioso para chequear el cronómetro
    st_autorefresh(interval=30000, key="timeoutcheck") 

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
        "antidiabéticos": "Para el azúcar en la sangre.",
        "hipolipemiantes": "Para bajar el colesterol."
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

# --- 4. SEGURIDAD Y ACCESO ---
if "logueado" not in st.session_state: st.session_state["logueado"] = False
if not st.session_state["logueado"]:
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

# --- 6. SIDEBAR ---
with st.sidebar:
    st.header(f"👤 {st.session_state.user.capitalize()}")
    if st.button("🚪 Salir"): st.session_state.clear(); st.rerun()
    
    if st.session_state.role == "admin":
        with st.form("alta", clear_on_submit=True):
            n = st.text_input("Nombre").upper()
            s = st.number_input("Cantidad", 1)
            f = st.date_input("Vencimiento")
            u = st.selectbox("Lugar", ["Medicación de vitrina", "Medicación de armario"])
            if st.form_submit_button("Registrar"):
                if n:
                    ws_inv.append_row([n, s, str(f), u])
                    st.rerun()

# --- 7. PANEL PRINCIPAL Y BUSCADOR ---
st.title("💊 Inventario Médico")
query = st_keyup("🔍 Busca un medicamento...", key="search_main").strip().upper()
if query: st.session_state.last_activity = time.time() # Reiniciar timer al buscar

df_vis = df_master[df_master["Stock"] > 0].copy() if not df_master.empty else pd.DataFrame()
if query and not df_vis.empty:
    df_vis = df_vis[df_vis["Nombre"].str.contains(query, na=False)]

tabs = st.tabs(["📋 Todo", "💊 Vitrina", "📦 Armario"])

# --- 8. FUNCIÓN TARJETA (DISEÑO ACTUALIZADO) ---
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
            
            # DISEÑO SOLICITADO: Principio activo primero, descripción después
            st.markdown(f'<div class="caja-info"><b>Principio Activo:</b> {p_act}<br><br><b>Descripción:</b> {d_uso}</div>', unsafe_allow_html=True)
            
            if st.session_state.role == "admin":
                with st.form(f"f_n_{nombre}_{key_tab}"):
                    n_p = st.text_input("Editar Principio", p_act)
                    n_d = st.text_area("Editar Descripción", d_uso)
                    if st.form_submit_button("Guardar"):
                        m = ws_not.find(nombre)
                        if m: ws_not.update_row(m.row, [nombre, n_p, n_d])
                        else: ws_not.append_row([nombre, n_p, n_d])
                        st.rerun()

        c1, c2 = st.columns([4, 1])
        if c1.button(f"💊 RETIRAR 1 UNIDAD", key=f"ret_{nombre}_{key_tab}"):
            st.session_state.last_activity = time.time()
            encontrado = ws_inv.find(nombre)
            if encontrado:
                ws_inv.update_cell(encontrado.row, 2, max(0, stock - 1))
                ws_his.append_row([datetime.now().strftime("%d/%m %H:%M"), st.session_state.user, "RETIRADA", nombre])
                st.rerun()

        if st.session_state.role == "admin":
            if c2.button("🗑", key=f"del_{nombre}_{key_tab}"):
                st.session_state.last_activity = time.time()
                encontrado = ws_inv.find(nombre)
                if encontrado:
                    ws_inv.delete_rows(encontrado.row)
                    st.rerun()
    except: pass

# --- 9. RENDER ---
for i, filtro in enumerate(["", "vitrina", "armario"]):
    with tabs[i]:
        df_f = df_vis if not filtro else df_vis[df_vis["Ubicacion"].str.contains(filtro, case=False)]
        for _, fila in df_f.iterrows(): dibujar_tarjeta(fila, i)