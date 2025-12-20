import streamlit as st
import pandas as pd
from datetime import date

st.set_page_config(page_title="Botiquín Pro v4", layout="wide")

# --- FUNCIONES DE DATOS ---
def cargar_datos():
    try:
        df = pd.read_csv("inventario.csv")
        df['Caducidad'] = pd.to_datetime(df['Caducidad'], errors='coerce').dt.date
        return df.dropna(subset=['Caducidad']).sort_values(by='Caducidad')
    except:
        return pd.DataFrame(columns=["Nombre", "Stock", "Caducidad"])

def guardar_datos(df):
    df.to_csv("inventario.csv", index=False)

if 'df' not in st.session_state:
    st.session_state.df = cargar_datos()

# --- BARRA LATERAL: AÑADIR CON SELECTORES DE MES/AÑO ---
with st.sidebar:
    st.header("➕ Nuevo Registro")
    with st.form("nuevo_form", clear_on_submit=True):
        n = st.text_input("Nombre del medicamento")
        s = st.number_input("Cantidad de cajas", min_value=1, value=1)
        
        st.write("📅 Fecha de Vencimiento")
        col_mes, col_anio = st.columns(2)
        
        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", 
                 "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        
        mes_sel = col_mes.selectbox("Mes", meses, index=date.today().month - 1)
        # Generamos años desde el actual hasta 10 años en el futuro
        anio_actual = date.today().year
        anio_sel = col_anio.selectbox("Año", list(range(anio_actual, anio_actual + 11)))
        
        if st.form_submit_button("Añadir al Inventario"):
            if n:
                # Convertir mes seleccionado a número
                mes_num = meses.index(mes_sel) + 1
                # Creamos la fecha (usamos el día 1 por defecto para el registro interno)
                fecha_vence = date(anio_sel, mes_num, 1)
                
                nueva = pd.DataFrame([{"Nombre": n, "Stock": s, "Caducidad": fecha_vence}])
                st.session_state.df = pd.concat([st.session_state.df, nueva], ignore_index=True)
                guardar_datos(st.session_state.df)
                st.rerun()

# --- INTERFAZ PRINCIPAL ---
st.title("💊 Mi Inventario de Medicinas")

# 1. BUSCADOR EN TIEMPO REAL
busqueda = st.text_input("🔍 Escribe para buscar...", placeholder="Ej: Ibuprofeno").lower()

# 2. FILTRO DE VISTA
opciones = ["Todos", "Próximos a caducar (30 días)", "Caducados"]
filtro_vista = st.selectbox("📂 Ver categoría:", opciones)

# --- PROCESAMIENTO DE FILTROS ---
hoy = date.today()
df_display = st.session_state.df.copy()

# Primero filtramos por búsqueda de texto
if busqueda:
    df_display = df_display[df_display['Nombre'].str.lower().str.contains(busqueda)]

# Luego filtramos por categoría de fecha
if filtro_vista == "Próximos a caducar (30 días)":
    df_display = df_display[df_display['Caducidad'].apply(lambda x: 0 <= (x - hoy).days <= 30)]
elif filtro_vista == "Caducados":
    df_display = df_display[df_display['Caducidad'].apply(lambda x: x < hoy)]

# Ordenar siempre por fecha
df_display = df_display.sort_values(by='Caducidad')

# --- LISTADO VISUAL ---
if not df_display.empty:
    for i, fila in df_display.iterrows():
        dias_faltan = (fila['Caducidad'] - hoy).days
        
        # Lógica de colores
        if dias_faltan < 0: color = "#FFDADA" # Rojo
        elif dias_faltan <= 30: color = "#FFF4D1" # Amarillo
        else: color = "#D4EDDA" # Verde

        # Mostramos la fecha en formato Mes / Año
        mes_anio_texto = fila['Caducidad'].strftime('%m / %Y')

        st.markdown(f"""
            <div style="background-color:{color}; padding:15px; border-radius:10px; border:1px solid #ccc; margin-bottom:10px; color:black;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <span style="font-size:20px; font-weight:bold;">{fila['Nombre']}</span>
                    <span style="font-size:18px;">Vence: <b>{mes_anio_texto}</b></span>
                </div>
                <div style="font-size:16px;">Stock: <b>{fila['Stock']}</b> unidades</div>
            </div>
        """, unsafe_allow_html=True)
        
        # Botones de gestión
        c1, c2, c3, _ = st.columns([1,1,1,6])
        if c1.button("➕", key=f"add_{i}"):
            st.session_state.df.loc[i, 'Stock'] += 1
            guardar_datos(st.session_state.df)
            st.rerun()
        if c2.button("➖", key=f"sub_{i}"):
            if st.session_state.df.loc[i, 'Stock'] > 1:
                st.session_state.df.loc[i, 'Stock'] -= 1
                guardar_datos(st.session_state.df)
                st.rerun()
        if c3.button("🗑", key=f"del_{i}"):
            st.session_state.df = st.session_state.df.drop(i).reset_index(drop=True)
            guardar_datos(st.session_state.df)
            st.rerun()
else:
    st.info("No se encontraron medicamentos.")