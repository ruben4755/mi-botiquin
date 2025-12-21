import streamlit as st
import pandas as pd
import gspread
import requests
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from st_keyup import st_keyup

# --- 1. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="Sistema Médico Consolidado", layout="wide", page_icon="💊")

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
    [data-testid="stSidebar"] * { color: white !important; }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { 
        background-color: #1e2128; border-radius: 5px; padding: 10px 20px; color: white;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. MOTOR DE INFORMACIÓN (API CIMA) ---
def traducir_a_coloquial(atc_nombre):
    atc_nombre = (atc_nombre or "").lower()
    mapeo = {
        "analgésicos": "Para dolores (cabeza, cuerpo, articulaciones).",
        "antipiréticos": "Para bajar la fiebre.",
        "antiinflamatorios": "Para reducir hinchazón y dolor.",
        "protones": "Protector de estómago. Evita ardores.",
        "antibacterianos": "Antibiótico para infecciones.",
        "antihistamínicos": "Para alergias y picores.",
        "antitusígenos": "Para calmar la tos seca.",
        "ansiolíticos": "Para calmar nervios o dormir.",
        "antihipertensivos": "Para la tensión arterial.",
        "antidiabéticos": "Para el azúcar en sangre."
    }
    for clave, explicacion in mapeo.items():
        if clave in atc_nombre: return explicacion
    return f"Uso: {atc_nombre}."

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

# --- 3. CONEXIÓN Y LOGS ---
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

def registrar(accion, med):
    try:
        ws_his.append_row([datetime.now().strftime("%d/%m %H:%M"), st.session_state.user, accion, med])
    except: pass

# --- 4. SEGURIDAD ---
if "logueado" not in st.session_state: st.session_state["logueado"] = False
if not st.session_state["logueado"]:
    st.title("🔐 Acceso")
    with st.form("login"):
        u, p = st.text_input("Usuario"), st.text_input("Contraseña", type="password")
        if st.form_submit_button("Entrar"):
            if u in st.secrets["users"] and str(p) == str(st.secrets["users"][u]):
                st.session_state.update({"logueado": True, "user": u, "role": st.secrets["roles"].get(u, "user")})
                st.rerun()
            else: st.error("Error de acceso.")
    st.stop()

# --- 5. CARGA DE DATOS ROBUSTA ---
def cargar_inventario():
    try:
        data = ws_inv.get_all_values()
        if len(data) < 2: return pd.DataFrame()
        header = [h.strip() for h in data[0]]
        df = pd.DataFrame(data[1:], columns=header)
        df["Stock"] = pd.to_numeric(df["Stock"], errors='coerce').fillna(0).astype(int)
        df["Nombre"] = df["Nombre"].astype(str).str.strip()
        return df
    except: return pd.DataFrame()

df_master = cargar_inventario()

# --- 6. SIDEBAR ADMINISTRATIVA ---
with st.sidebar:
    st.header(f"👤 {st.session_state.user.capitalize()}")
    if st.button("🚪 Salir"): st.session_state.clear(); st.rerun()
    
    if st.session_state.role == "admin":
        st.divider()
        st.subheader("➕ Nuevo Medicamento")
        with st.form("alta", clear_on_submit=True):
            n = st.text_input("Nombre").upper()
            s = st.number_input("Stock Inicial", 1)
            f = st.date_input("Vencimiento")
            u = st.selectbox("Ubicación", ["Medicación de vitrina", "Medicación de armario"])
            if st.form_submit_button("Registrar"):
                if n:
                    ws_inv.append_row([n, s, str(f), u])
                    registrar("ALTA", n)
                    st.rerun()

        st.divider()
        st.subheader("🕒 Logs Recientes")
        try:
            h_raw = ws_his.get_all_values()
            if len(h_raw) > 1:
                df_h = pd.DataFrame(h_raw[1:]).iloc[::-1].head(10)
                df_h.columns = ["Fecha", "User", "Accion", "Med"]
                st.dataframe(df_h, hide_index=True)
        except: pass

# --- 7. PANEL PRINCIPAL Y BUSCADOR ---
st.title("💊 Gestión de Medicación Consolidada")
query = st_keyup("🔍 Escribe para buscar...", key="search_main").strip().upper()

df_vis = df_master[df_master["Stock"] > 0].copy() if not df_master.empty else pd.DataFrame()

if query and not df_vis.empty:
    df_vis = df_vis[df_vis["Nombre"].str.contains(query, na=False)]

tabs = st.tabs(["📋 Todos", "💊 Vitrina", "📦 Armario"])

# --- 8. FUNCIÓN DE RENDERIZADO PROTEGIDO ---
def dibujar_medicamento(fila, key_tab):
    try:
        nombre = fila["Nombre"]
        stock = int(fila["Stock"])
        ubi = fila["Ubicacion"]
        cad = fila["Caducidad"]
        
        # Lógica de Semáforo
        f_vence = datetime.strptime(cad, "%Y-%m-%d")
        hoy = datetime.now()
        if f_vence < hoy: status, col = "🔴 CADUCADO", "#ff4b4b"
        elif f_vence < hoy + timedelta(days=30): status, col = "🟠 PRÓXIMO", "#ffa500"
        else: status, col = "🟢 OK", "#28a745"

        st.markdown(f'''
            <div class="tarjeta-med" style="border-left-color: {col}">
                <span style="float:right; font-size:0.8em; color:{col}; font-weight:bold;">{status}</span>
                <b style="font-size:1.2em;">{nombre}</b><br>
                <small>{stock} unidades | {ubi} | Vence: {cad}</small>
            </div>
        ''', unsafe_allow_html=True)
        
        with st.expander("📚 Información y Notas"):
            # Buscar nota guardada
            notas_all = ws_not.get_all_values()
            nota_actual = next((r for r in notas_all if r[0] == nombre), None)
            
            if nota_actual:
                p_act, d_uso = nota_actual[1], nota_actual[2]
            else:
                info = buscar_info_web(nombre)
                p_act, d_uso = (info['p'], info['e']) if info else ("No disponible", "Sin datos técnicos.")
            
            st.markdown(f'<div class="caja-info"><b>Principio Activo:</b> {p_act}<br><b>💡 Uso:</b> {d_uso}</div>', unsafe_allow_html=True)
            
            if st.session_state.role == "admin":
                with st.form(f"f_nota_{nombre}_{key_tab}"):
                    edit_p = st.text_input("Editar Principio", p_act)
                    edit_d = st.text_area("Editar descripción", d_uso)
                    if st.form_submit_button("Guardar Nota"):
                        match = ws_not.find(nombre)
                        if match: ws_not.update_row(match.row, [nombre, edit_p, edit_d])
                        else: ws_not.append_row([nombre, edit_p, edit_d])
                        st.rerun()

        c1, c2 = st.columns([4, 1])
        if c1.button(f"💊 RETIRAR 1 UNIDAD", key=f"btn_ret_{nombre}_{key_tab}"):
            # BUSQUEDA DINÁMICA: Evita el error de índice
            match = ws_inv.find(nombre)
            if match:
                nuevo_stock = max(0, stock - 1)
                ws_inv.update_cell(match.row, 2, nuevo_stock)
                registrar("RETIRADA", nombre)
                st.rerun()

        if st.session_state.role == "admin":
            if c2.button("🗑", key=f"btn_del_{nombre}_{key_tab}"):
                match = ws_inv.find(nombre)
                if match:
                    ws_inv.delete_rows(match.row)
                    registrar("ELIMINADO", nombre)
                    st.rerun()
    except Exception as e:
        pass

# --- 9. DISTRIBUCIÓN ---
for i, filtro in enumerate(["", "vitrina", "armario"]):
    with tabs[i]:
        if df_vis.empty:
            st.info("Inventario vacío.")
        else:
            df_filtro = df_vis if not filtro else df_vis[df_vis["Ubicacion"].str.contains(filtro, case=False)]
            if df_filtro.empty:
                st.caption("No se han encontrado resultados.")
            for _, fila in df_filtro.iterrows():
                dibujar_medicamento(fila, i)