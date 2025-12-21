import streamlit as st
import pandas as pd
import gspread
import requests
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from st_keyup import st_keyup

# --- 1. CONFIGURACIÓN Y ESTÉTICA ---
st.set_page_config(page_title="Gestión Médica Pro", layout="wide", page_icon="💊")

st.markdown("""
    <style>
    .stApp { background-color: #0e1117; }
    .tarjeta-med { 
        color: #ffffff !important; background: #1e2128; padding: 18px; 
        border-radius: 12px; margin-bottom: 12px; border-left: 8px solid #28a745;
        box-shadow: 0 4px 10px rgba(0,0,0,0.4);
    }
    .caja-info {
        background: #262730; border-radius: 10px; padding: 15px;
        color: #eeeeee !important; border: 1px solid #444; margin: 10px 0;
    }
    [data-testid="stSidebar"] { 
        background-color: #1a1c23 !important; 
        min-width: 350px !important; 
    }
    [data-testid="stSidebar"] * { color: white !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR DE INFORMACIÓN ---
def traducir_a_coloquial(atc_nombre):
    atc_nombre = (atc_nombre or "").lower()
    mapeo = {
        "analgésicos": "Para aliviar dolores (cabeza, cuerpo, articulaciones).",
        "antipiréticos": "Para ayudar a bajar la fiebre.",
        "antiinflamatorios": "Para reducir la hinchazón y el dolor.",
        "inhibidores de la bomba de protones": "Protector de estómago. Evita ardores.",
        "antibacterianos": "Antibiótico para combatir infecciones.",
        "antihistamínicos": "Para alergias, estornudos y picores.",
        "antitusígenos": "Para calmar la tos seca.",
        "ansiolíticos": "Para calmar los nervios o dormir.",
        "antihipertensivos": "Para la tensión arterial.",
        "antidiabéticos": "Para el azúcar en sangre."
    }
    for clave, explicacion in mapeo.items():
        if clave in atc_nombre: return explicacion
    return f"Uso: {atc_nombre}."

@st.cache_data(ttl=604800)
def buscar_info_web(nombre):
    try:
        # Limpiamos el nombre para la búsqueda en API
        busqueda = nombre.split()[0].strip()
        res = requests.get(f"https://cima.aemps.es/cima/rest/medicamentos?nombre={busqueda}", timeout=5).json()
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
def iniciar_conexion():
    try:
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=["https://www.googleapis.com/auth/spreadsheets"])
        sh = gspread.authorize(creds).open_by_url(st.secrets["url_excel"])
        ws_inv = sh.get_worksheet(0)
        worksheets = [w.title for w in sh.worksheets()]
        ws_notas = sh.worksheet("Notas") if "Notas" in worksheets else sh.add_worksheet("Notas", 500, 3)
        ws_hist = sh.worksheet("Historial") if "Historial" in worksheets else sh.add_worksheet("Historial", 5000, 5)
        return ws_inv, ws_notas, ws_hist
    except: return None, None, None

ws_inv, ws_notas, ws_hist = iniciar_conexion()

def registrar_evento(accion, med):
    try:
        ws_hist.append_row([datetime.now().strftime("%d/%m %H:%M"), st.session_state.user, accion, med])
    except: pass

# --- 4. LOGIN ---
if "logueado" not in st.session_state: st.session_state["logueado"] = False
if not st.session_state["logueado"]:
    st.title("🔐 Acceso")
    with st.form("login"):
        u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if "users" in st.secrets and u in st.secrets["users"] and str(p) == str(st.secrets["users"][u]):
                st.session_state.update({"logueado": True, "user": u, "role": st.secrets["roles"].get(u, "user")})
                st.rerun()
    st.stop()

# --- 5. SIDEBAR ---
with st.sidebar:
    st.header(f"👤 {st.session_state.user.capitalize()}")
    if st.button("🚪 Cerrar Sesión"): st.session_state.clear(); st.rerun()
    
    if st.session_state.role == "admin":
        st.divider()
        st.subheader("➕ Nuevo Medicamento")
        with st.form("nuevo_med", clear_on_submit=True):
            n = st.text_input("Nombre")
            s = st.number_input("Cantidad", 1)
            f = st.date_input("Caducidad")
            u = st.selectbox("Lugar", ["Medicación de vitrina", "Medicación de armario"])
            if st.form_submit_button("Añadir"):
                if n:
                    ws_inv.append_row([n.upper().strip(), int(s), f.strftime("%Y-%m-%d"), u])
                    registrar_evento("ALTA", n.upper())
                    st.rerun()

        st.divider()
        st.subheader("🕒 Historial")
        try:
            h_raw = ws_hist.get_all_values()
            if len(h_raw) > 1:
                df_h = pd.DataFrame([fil for fil in h_raw[1:] if len(fil) >= 4])
                if not df_h.empty:
                    df_h = df_h.iloc[:, :4]
                    df_h.columns = ['Fecha', 'Usuario', 'Acción', 'Medicina']
                    st.dataframe(df_h.iloc[::-1].head(10), hide_index=True, use_container_width=True)
        except: st.caption("Historial no disponible.")

# --- 6. DATOS Y BUSCADOR (FILTRADO BLINDADO) ---
try:
    # Obtenemos todos los datos y limpiamos de golpe
    data_inv = ws_inv.get_all_values()
    if len(data_inv) > 1:
        headers = [str(h).strip() for h in data_inv[0]]
        df_master = pd.DataFrame(data_inv[1:], columns=headers)
        
        # Normalización total de columnas críticas
        df_master["Stock"] = pd.to_numeric(df_master["Stock"], errors='coerce').fillna(0).astype(int)
        df_master["Nombre"] = df_master["Nombre"].astype(str).str.strip()
        df_master["Ubicacion"] = df_master["Ubicacion"].astype(str).str.strip()
        df_master["idx"] = range(2, len(df_master) + 2)
    else:
        st.info("Inventario vacío.")
        st.stop()
except:
    st.error("Error de base de datos.")
    st.stop()

st.title("💊 Inventario Médico")

# BUSCADOR ESTABLE: key estática y limpieza de caracteres
bus = st_keyup("🔍 Escribir para buscar...", key="main_search_input")

# Filtro base por stock
df_vis = df_master[df_master["Stock"] > 0].copy()

# APLICACIÓN DE BÚSQUEDA (Solo si hay texto real escrito)
if bus and bus.strip():
    txt = bus.strip().upper()
    df_vis = df_vis[df_vis["Nombre"].str.upper().str.contains(txt, na=False)]

tabs = st.tabs(["📋 Todos", "💊 Vitrina", "📦 Armario"])

# --- 7. FUNCIÓN DE RENDERIZADO ---
def pintar_tarjeta(fila, k):
    n, stock, ubi, idx, cad = fila["Nombre"], fila["Stock"], fila["Ubicacion"], fila["idx"], fila["Caducidad"]
    
    try:
        f_c = datetime.strptime(cad, "%Y-%m-%d")
        hoy = datetime.now()
        if f_c < hoy: status, color = "🔴 CADUCADO", "#ff4b4b"
        elif f_c < hoy + timedelta(days=30): status, color = "🟠 PRÓXIMO", "#ffa500"
        else: status, color = "🟢 OK", "#28a745"
    except: status, color = "⚪ S/F", "#444"

    st.markdown(f'<div class="tarjeta-med" style="border-left: 8px solid {color};"><b>{n}</b> <span style="float:right; font-size:0.7em;">{status}</span><br><small>{stock} uds. | {ubi} | Vence: {cad}</small></div>', unsafe_allow_html=True)
    
    with st.expander("🤔 Info"):
        try:
            notas_all = ws_notas.get_all_values()
            nota_m = next((r for r in notas_all if r[0] == n), None)
            p_f, d_f = (nota_m[1], nota_m[2]) if nota_m else ("?", "?")
            
            if p_f == "?":
                info = buscar_info_web(n)
                if info: p_f, d_f = info['p'], info['e']
                
            st.markdown(f'<b>P. Activo:</b> {p_f}<br><b>💡 Uso:</b> {d_f}', unsafe_allow_html=True)
            
            if st.session_state.role == "admin":
                with st.form(f"ed_{idx}"):
                    np, nd = st.text_input("P. Activo", p_f), st.text_area("Uso", d_f)
                    if st.form_submit_button("Guardar"):
                        celda = ws_notas.find(n)
                        if celda: ws_notas.update_row(celda.row, [n, np, nd])
                        else: ws_notas.append_row([n, np, nd])
                        st.rerun()
        except: st.caption("No se pudo cargar la información.")

    c1, c2 = st.columns([3, 1])
    if c1.button(f"💊 RETIRAR", key=f"r_{idx}_{k}"):
        ws_inv.update_cell(idx, headers.index("Stock") + 1, max(0, int(stock) - 1))
        registrar_evento("RETIRADA", n)
        st.rerun()
        
    if st.session_state.role == "admin":
        if c2.button("🗑", key=f"d_{idx}_{k}"):
            ws_inv.delete_rows(idx)
            registrar_evento("ELIMINADO", n)
            st.rerun()

# --- 8. RENDERIZADO POR PESTAÑAS ---
for i, ubi_f in enumerate(["", "vitrina", "armario"]):
    with tabs[i]:
        # Filtrado por ubicación sobre los resultados de la búsqueda
        if ubi_f == "":
            df_final = df_vis
        else:
            df_final = df_vis[df_vis["Ubicacion"].str.contains(ubi_f, case=False, na=False)]
        
        if not df_final.empty:
            for _, f in df_final.iterrows():
                pintar_tarjeta(f, f"tab{i}")
        else:
            st.caption("Sin resultados para esta búsqueda o ubicación.")