import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import datetime
import io

# --- CONFIGURACIÓN DE LA APP ---
st.set_page_config(page_title="Rutas Darnel", layout="centered", page_icon="🏍️")
st.title("🏍️ Vitrina Móvil Darnel")
st.markdown("### Gestión de Rutas - Motorizado")

# ID del archivo de Google Sheets (El nuevo archivo sin .xlsx)
SHEET_ID = "1tABY8D8rpQUP2qorNz1KCxea92WjG2PdIA3e-1CcqFU"

@st.cache_resource
def conectar_servicios():
    """Conecta con Google Sheets y Drive usando las credenciales secretas"""
    cred_dict = dict(st.secrets["gcp_service_account"])
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets', 
        'https://www.googleapis.com/auth/drive'
    ]
    creds = Credentials.from_service_account_info(cred_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    drive_service = build('drive', 'v3', credentials=creds)
    return gc, drive_service

# Intentar conectar
try:
    gc, drive_service = conectar_servicios()
except Exception as e:
    st.warning("⚠️ La app está lista. Falta vincular las credenciales en Streamlit (Siguiente paso).")
    st.stop()

# --- LECTURA DE DATOS ---
@st.cache_data(ttl=600) # Recarga los datos cada 10 minutos
def obtener_datos():
    hoja = gc.open_by_key(SHEET_ID).worksheet("Bogotá")
    datos = hoja.get_all_records()
    df = pd.DataFrame(datos)
    return df

try:
    df_rutas = obtener_datos()
except Exception as e:
    st.error(f"Hubo un error al leer el Excel. Detalle técnico: {repr(e)}")
    st.stop()

# --- INTERFAZ DEL MOTORIZADO ---
# 1. Selector de Fecha con guiones
fecha_hoy = datetime.datetime.now().strftime("%d-%m-%Y")
fecha_seleccionada = st.text_input("📅 Fecha de Ruta (DD-MM-AAAA)", value=fecha_hoy)

# Filtrar clientes por la fecha seleccionada
if "Fecha_Motorizado" in df_rutas.columns:
    df_dia = df_rutas[df_rutas["Fecha_Motorizado"] == fecha_seleccionada]
else:
    st.error("No se encontró la columna 'Fecha_Motorizado' en el Excel.")
    st.stop()

if df_dia.empty:
    st.info(f"No hay rutas programadas para la fecha: {fecha_seleccionada}")
else:
    st.success(f"Tienes {len(df_dia)} clientes para visitar hoy.")
    
    # 2. Mostrar la lista de clientes
    for index, cliente in df_dia.iterrows():
        nombre = cliente.get("Nombre_Cliente", "Cliente sin nombre")
        direccion = cliente.get("Direccion_Centro_5km_Aprox", cliente.get("Direccion_Principal", "Sin dirección"))
        id_cliente = cliente.get("Código_Cliente", str(index))
        
        # Construir link exacto con GPS de latitud y longitud
        lat = str(cliente.get("Latitud centro", "")).strip().replace(",", ".")
        lon = str(cliente.get("Longitud centro", "")).strip().replace(",", ".")
        
        if lat and lon and lat.lower() != "nan":
            link_maps = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}"
        else:
            link_maps = ""
        
        with st.expander(f"📍 {nombre} - {direccion}"):
            st.write(f"**Dirección:** {direccion}")
            
            # Botón de Navegación
            if link_maps:
                st.markdown(f"[🗺️ Abrir en Google Maps y Navegar]({link_maps})", unsafe_allow_html=True)
            else:
                st.warning("Este cliente no tiene coordenadas configuradas.")
            
            st.markdown("---")
            st.write("📸 **Constancia de Visita**")
            
            # Captura de foto
            foto = st.camera_input("Tomar foto del punto", key=f"cam_{index}")
            st.info("📍 *El GPS de alta precisión se registrará al guardar la visita.*")
            
            if st.button("✅ Guardar Visita", key=f"btn_{index}"):
                if foto is not None:
                    with st.spinner("Subiendo foto y guardando registro..."):
                        try:
                            # 1. Subir Foto a Drive
                            carpeta_id = st.secrets["drive_folder_id"]
                            file_metadata = {
                                'name': f"{id_cliente}_{fecha_hoy}.jpg",
                                'parents': [carpeta_id]
                            }
                            media = MediaIoBaseUpload(io.BufferedReader(foto), mimetype='image/jpeg', resumable=True)
                            archivo_subido = drive_service.files().create(body=file_metadata, media_body=media, fields='id, webViewLink').execute()
                            link_foto = archivo_subido.get('webViewLink')
                            
                            # 2. Guardar en Excel
                            hora_actual = datetime.datetime.now().strftime("%H:%M:%S")
                            hoja_visitas = gc.open_by_key(SHEET_ID).worksheet("Visitas_Realizadas")
                            
                            hoja_visitas.append_row([
                                nombre, 
                                f"{fecha_seleccionada} {hora_actual}", 
                                lat, # Latitud guardada
                                lon, # Longitud guardada
                                link_foto
                            ])
                            st.success("¡Visita guardada exitosamente!")
                        except Exception as e:
                            st.error(f"Error al guardar: {e}")
                else:
                    st.warning("⚠️ Debes tomar una foto antes de guardar la visita.")
