import streamlit as st

# 1. Esto DEBE ser lo primero que aparezca en el código
st.set_page_config(page_title="Botiquín Protegido")

def check_password():
    """Retorna True si el usuario introdujo la contraseña correcta."""

    def password_entered():
        # Comprueba si la contraseña escrita coincide con la de "Secrets"
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Borra la clave de la memoria por seguridad
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        # PANTALLA DE LOGIN (Si no ha entrado antes)
        st.title("🔒 Acceso Restringido")
        st.text_input(
            "Introduce la contraseña del botiquín:", 
            type="password", 
            on_change=password_entered, 
            key="password"
        )
        if "password_correct" in st.session_state:
            st.error("😕 Contraseña incorrecta")
        return False
    return True

# 2. SOLO SI PASA EL CHECK, SE EJECUTA LO DEMÁS
if check_password():
    # AQUÍ VA TODO TU CÓDIGO ANTERIOR
    st.success("✅ Acceso concedido")
    st.title("💊 Mi Inventario de Medicinas")
    
    # ... (Aquí sigue el resto de tu código: cargar_datos, etc.) ...
    # Asegúrate de que TODO lo que sigue esté movido un espacio (tabulación) a la derecha 
    # para que esté dentro del "if check_password():"
    
    st.write("Si ves esto, es que la contraseña es correcta o el sistema ha fallado.")