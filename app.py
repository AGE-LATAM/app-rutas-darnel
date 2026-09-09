import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import datetime
import pytz
import requests
import base64

# --- CONFIGURACIÓN DE LA APP ---
st.set_page_config(page_title="Rutas Darnel", layout="centered", page_icon="🏍️")

# 3. Identidad Visual: Banner Superior
try:
    st.image("banner.png", use_container_width=True)
except Exception as e:
    st.error(f"Error cargando banner: {e}")

st.markdown("### Gestión de Rutas - Motorizado")

# ID del archivo de Google Sheets
SHEET_ID = "1tABY8D8rpQUP2qorNz1KCxea92WjG2PdIA3e-1CcqFU"

@st.cache_resource
def conectar_servicios():
    """Conecta con Google Sheets usando las credenciales secretas"""
    cred_dict = dict(st.secrets["gcp_service_account"])
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets', 
        'https://www.googleapis.com/auth/drive'
    ]
    creds = Credentials.from_service_account_info(cred_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc

try:
    gc = conectar_servicios()
except Exception as e:
    st.warning("⚠️ Faltan credenciales de Google.")
    st.stop()

# --- SELECTOR DINÁMICO DE CIUDADES ---
# Excluimos las hojas administrativas
hojas_excluidas = ["Visitas_Realizadas", "Metodología", "Resumen_Rutas"]
todas_las_hojas = [hoja.title for hoja in gc.open_by_key(SHEET_ID).worksheets()]
ciudades_disponibles = [hoja for hoja in todas_las_hojas if hoja not in hojas_excluidas]

if not ciudades_disponibles:
    st.error("No se encontraron hojas de ciudades válidas en el Excel.")
    st.stop()

# Selector de ciudad
ciudad_seleccionada = st.selectbox("🏙️ Selecciona tu Ciudad", ciudades_disponibles)

# --- LECTURA DE DATOS ---
@st.cache_data(ttl=600)
def obtener_datos(ciudad):
    hoja = gc.open_by_key(SHEET_ID).worksheet(ciudad)
    datos = hoja.get_all_records()
    df = pd.DataFrame(datos)
    return df

try:
    df_rutas = obtener_datos(ciudad_seleccionada)
except Exception as e:
    st.error(f"Error al leer la ciudad. Detalle: {e}")
    st.stop()

# --- INTERFAZ DEL MOTORIZADO ---
# 1. Configurar zona horaria de Bogotá
zona_colombia = pytz.timezone('America/Bogota')
fecha_hoy = datetime.datetime.now(zona_colombia).strftime("%d-%m-%Y")
fecha_seleccionada = st.text_input("📅 Fecha de Ruta (DD-MM-AAAA)", value=fecha_hoy)

# 2. Limpiar espacios invisibles y filtrar
if "Fecha_Motorizado" in df_rutas.columns:
    # Convertimos la columna a texto y borramos espacios fantasma
    df_rutas["Fecha_Motorizado"] = df_rutas["Fecha_Motorizado"].astype(str).str.strip()
    fecha_limpia = fecha_seleccionada.strip()
    
    df_dia = df_rutas[df_rutas["Fecha_Motorizado"] == fecha_limpia]
else:
    st.error("No se encontró la columna 'Fecha_Motorizado' en el Excel.")
    st.stop()
if df_dia.empty:
    st.info(f"No hay rutas programadas para {ciudad_seleccionada} el {fecha_seleccionada}")
else:
    st.success(f"Tienes {len(df_dia)} clientes para visitar hoy.")
    
    for index, cliente in df_dia.iterrows():
        nombre = cliente.get("Nombre_Cliente", "Cliente sin nombre")
        
        # 1. Dirección Principal (Columna H)
        direccion = cliente.get("Direccion_Principal", "")
        id_cliente = cliente.get("Código_Cliente", str(index))
        
        if direccion and direccion != "":
            direccion_url = str(direccion).replace(" ", "+")
            # Google maps ahora busca la dirección + la ciudad seleccionada
            link_maps = f"https://www.google.com/maps/search/?api=1&query={direccion_url},+{ciudad_seleccionada}"
        else:
            link_maps = ""
            direccion = "Sin dirección"
        
        with st.expander(f"📍 {nombre} - {direccion}"):
            st.write(f"**Dirección:** {direccion}")
            
            if link_maps:
                st.markdown(f"[🗺️ Abrir en Google Maps y Navegar]({link_maps})", unsafe_allow_html=True)
            else:
                st.warning("Este cliente no tiene una dirección válida para buscar.")
            
            st.markdown("---")
            st.write("📸 **Constancia de Visita**")
            
            foto = st.camera_input("Tomar foto del punto", key=f"cam_{index}")
            
            if st.button("✅ Guardar Visita", key=f"btn_{index}"):
                if foto is not None:
                    with st.spinner("Subiendo foto y guardando registro..."):
                        try:
                            # Subir Foto vía Puente Apps Script
                            foto_b64 = base64.b64encode(foto.getvalue()).decode('utf-8')
                            
                            script_url = "https://script.google.com/macros/s/AKfycbz2alLhhxHqHQFN9oF7Ik10ze1jLqTA7iqSFe5irMiD68P2npBKXlZXwSMDLLTmWewP/exec"
                            payload = {
                                "folder": "1my9s9jGKOkUjfSS85YvpaiXpIcPLhCmU",
                                "name": f"{id_cliente}_{fecha_hoy}.jpg",
                                "data": foto_b64
                            }
                            
                            respuesta = requests.post(script_url, data=payload)
                            link_foto = respuesta.text
                            
                            # Guardar en Excel
                            hora_actual = datetime.datetime.now().strftime("%H:%M:%S")
                            hoja_visitas = gc.open_by_key(SHEET_ID).worksheet("Visitas_Realizadas")
                            
                            # Agregamos la ciudad al registro de visitas
                            hoja_visitas.append_row([
                                nombre, 
                                f"{fecha_seleccionada} {hora_actual}", 
                                ciudad_seleccionada, 
                                str(direccion), 
                                link_foto
                            ])
                            st.success("¡Visita guardada exitosamente!")
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")
                else:
                    st.warning("⚠️ Debes tomar una foto antes de guardar la visita.")

# 4. Sello de la Agencia
st.markdown("<br><br><br>", unsafe_allow_html=True)
col1, col2, col3 = st.columns([1, 1, 1])
with col2:
    st.markdown("<p style='text-align: center; color: gray; font-size: 12px; margin-bottom: 0px;'>Powered by</p>", unsafe_allow_html=True)
    try:
        st.image("tremendo.png", use_container_width=True)
    except:
        pass
