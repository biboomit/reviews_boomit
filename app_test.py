import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from wordcloud import WordCloud
from google_play_scraper import app, reviews, search
import time
import base64
from datetime import datetime, timedelta
import openai
import requests  # Para consultas a la API de Apple
from app_store_scraper import AppStore

# 🔹 **Configurar la página antes de cualquier otro código**
st.set_page_config(page_title="Boomit - Social Intelligence", layout="wide")

# 🔹 **Función de login**
def login():
    st.title("🔐 Iniciar sesión")
    username = st.text_input("Correo electrónico", key="user_input")
    password = st.text_input("Contraseña", type="password", key="pass_input", help="Ingrese su contraseña")
    login_button = st.button("Ingresar")

    if login_button:
        if username in st.secrets["users"] and st.secrets["users"][username] == password:
            st.session_state["authenticated"] = True
            st.session_state["username"] = username
            st.session_state["show_welcome"] = True
            st.rerun()
        else:
            st.error("❌ Correo o contraseña incorrectos")

# 🔹 **Verificar si el usuario está autenticado**
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    login()
    st.stop()

# 🔹 **Selección de Plataforma y Aplicación**
st.markdown("### 📱 Selecciona una plataforma y aplicación")
col1, col2 = st.columns(2)
with col1:
    selected_platform = st.radio(
        "📱 Plataforma:",
        ["Google Play Store", "App Store (iOS)", "Comparar Ambas"],
        horizontal=True
    )

with col2:
    app_name = st.text_input("🔎 Nombre de la aplicación:")

# 🔹 **Selector de país (solo para Google Play)**
country_mapping = {
    "Argentina": "ar", "Chile": "cl", "Colombia": "co", "Ecuador": "ec",
    "El Salvador": "sv", "Estados Unidos": "us", "Guatemala": "gt",
    "Honduras": "hn", "México": "mx", "Nicaragua": "ni", "Panamá": "pa",
    "Paraguay": "py", "Perú": "pe"
}

selected_country = None
if selected_platform in ["Google Play Store", "Comparar Ambas"]:
    selected_country = st.selectbox("🌍 Seleccione el país:", list(country_mapping.keys()))


# Definir el rango de los últimos 90 días
today = datetime.today()
ninety_days_ago = today - timedelta(days=90)

# 🔹 **Inicialización de variables para evitar errores**
app_id_android, app_id_ios = None, None
df_reviews = pd.DataFrame(columns=["at", "score", "content"])

# Inicializar métricas con "No disponible" para evitar errores antes de cargar datos
downloads_android = "No disponible"
last_release_android = "No disponible"
avg_score_android = "No disponible"
total_reviews_android = "No disponible"

avg_score_ios = "No disponible"
total_reviews_ios = "No disponible"

if app_name:
    with st.spinner("🔄 Buscando y cargando datos de la aplicación..."):
        country = country_mapping[selected_country] if selected_country else None

        # **Buscar en Google Play Store**
        if selected_platform in ["Google Play Store", "Comparar Ambas"] and selected_country:
            try:
                search_results = search(app_name, lang="es", country=country)
                if search_results:
                    app_id_android = search_results[0]['appId']
                    st.success(f"✅ Google Play: {search_results[0]['title']} (ID: {app_id_android}) en {country.upper()}")
            except Exception as e:
                st.error(f"❌ Error buscando en Google Play: {e}")

        # **Buscar en App Store**
        if selected_platform in ["App Store (iOS)", "Comparar Ambas"]:
            try:
                url = f"https://itunes.apple.com/search?term={app_name.replace(' ', '+')}&country=us&entity=software"
                response = requests.get(url, timeout=10).json()
                if response.get("results"):
                    app_id_ios = response["results"][0]["trackId"]
                    st.success(f"✅ App Store: {response['results'][0]['trackName']} (ID: {app_id_ios})")
            except requests.exceptions.Timeout:
                st.error("❌ Error: La búsqueda en App Store tardó demasiado. Inténtalo de nuevo.")
            except Exception as e:
                st.error(f"❌ Error buscando en App Store: {e}")

        # Si no se encuentra en ningún store
        if not app_id_android and not app_id_ios:
            st.error("❌ No se encontró la aplicación en ninguna tienda.")
            st.stop()

        # 🔹 **Obtener detalles de la aplicación**
        if app_id_android:
            try:
                app_data = app(app_id_android, lang='es', country=country)
                downloads_android = app_data.get("installs", "No disponible")
                last_release_android = datetime.fromtimestamp(app_data.get("updated", 0)).strftime("%Y-%m-%d %H:%M") if app_data.get("updated") else "No disponible"
                avg_score_android = round(app_data.get("score", 0), 1)  # Redondear a 1 decimal
                total_reviews_android = app_data.get("reviews", "No disponible")
            except Exception as e:
                st.error(f"❌ Error obteniendo datos de Google Play: {e}")

# Cargar reseñas de App Store
if app_id_ios:
    try:
        ios_app = AppStore(country="us", app_name=app_name, app_id=app_id_ios)
        ios_app.review()
        df_reviews_ios = pd.DataFrame(ios_app.reviews)

        # Verificar si hay reseñas antes de continuar
        if not df_reviews_ios.empty:
            # Renombrar columnas para que coincidan con Android
            column_mapping = {"date": "at", "rating": "score"}
            df_reviews_ios.rename(columns=column_mapping, inplace=True)

            # Convertir la fecha si existe
            if "at" in df_reviews_ios.columns:
                df_reviews_ios["at"] = pd.to_datetime(df_reviews_ios["at"], errors="coerce")
            else:
                st.warning("⚠️ No se encontraron fechas válidas en las reseñas de iOS.")
                df_reviews_ios["at"] = pd.NaT  # Evitar errores en el filtrado posterior

            # Asegurar que existe la columna de puntaje
            if "score" not in df_reviews_ios.columns:
                st.warning("⚠️ No se encontró la columna 'rating' en iOS. Se omitirán calificaciones.")
                df_reviews_ios["score"] = None  # Agregar columna vacía si no existe

            df_reviews_ios["source"] = "iOS"
        else:
            st.warning("⚠️ No se encontraron reseñas de iOS.")

    except Exception as e:
        st.error(f"❌ Error obteniendo reseñas de App Store: {e}")

# 🔹 **Carga de Reseñas**
df_reviews_android = pd.DataFrame()
df_reviews_ios = pd.DataFrame()

if app_id_android or app_id_ios:
    with st.spinner("📥 Cargando reseñas..."):
        # Cargar reseñas de Google Play
        if app_id_android:
            try:
                reviews_android, _ = reviews(
                    app_id_android, lang="es", country=country, count=200
                )
                df_reviews_android = pd.DataFrame(reviews_android)

                # Verificar que la columna "at" existe antes de seguir
                if "at" in df_reviews_android.columns:
                    df_reviews_android["at"] = pd.to_datetime(df_reviews_android["at"], errors="coerce")
                    df_reviews_android = df_reviews_android[df_reviews_android["at"] >= ninety_days_ago]  # Filtrar últimos 90 días
                    df_reviews_android["source"] = "Android"
                else:
                    df_reviews_android = pd.DataFrame()  # Reiniciar si no tiene "at"

            except Exception as e:
                st.error(f"❌ Error obteniendo reseñas de Google Play: {e}")

        # Cargar reseñas de App Store
        if app_id_ios:
            try:
                ios_app = AppStore(country="us", app_name=app_name, app_id=app_id_ios)
                ios_app.review(how_many=1000)  # Obtener hasta 1000 reseñas para mejor filtrado
                df_reviews_ios = pd.DataFrame(ios_app.reviews)

                # Verificar si hay reseñas antes de continuar
                if not df_reviews_ios.empty:
                    # Verificar si la columna "date" existe en los datos de iOS
                    if "date" in df_reviews_ios.columns:
                        df_reviews_ios.rename(columns={"date": "at"}, inplace=True)  # Renombrar "date" a "at"
                        df_reviews_ios["at"] = pd.to_datetime(df_reviews_ios["at"], errors="coerce")
                        df_reviews_ios = df_reviews_ios[df_reviews_ios["at"] >= ninety_days_ago]  # Filtrar últimos 90 días
                        df_reviews_ios["source"] = "iOS"
                    else:
                        st.warning("⚠️ No se encontraron fechas válidas en las reseñas de iOS.")
                        df_reviews_ios = pd.DataFrame()  # Vaciar si no tiene fechas

                    # Verificar si la columna "rating" existe
                    if "rating" in df_reviews_ios.columns:
                        df_reviews_ios.rename(columns={"rating": "score"}, inplace=True)  # Renombrar "rating" a "score"
                    else:
                        st.warning("⚠️ No se encontró la columna 'rating' en iOS. Se omitirán calificaciones.")
                        df_reviews_ios["score"] = None  # Agregar columna vacía si no existe

                else:
                    st.warning("⚠️ No se encontraron reseñas de iOS.")

            except Exception as e:
                st.error(f"❌ Error obteniendo reseñas de App Store: {e}")

# **Combinar reseñas de ambas plataformas si están disponibles**
df_reviews = pd.concat([df_reviews_android, df_reviews_ios], ignore_index=True)


# **FILTRO DE FECHAS**
if app_name and (app_id_android or app_id_ios):  # Solo muestra si se ha buscado una app
    if df_reviews.empty:
        st.warning("⚠️ No hay reseñas disponibles para esta aplicación.")
        df_filtered = pd.DataFrame()  # Evitar errores en el código posterior
    elif "at" not in df_reviews.columns or df_reviews["at"].dropna().empty:
        st.warning("⚠️ No hay fechas válidas en las reseñas obtenidas.")
        df_filtered = pd.DataFrame()
    else:
        st.markdown("---")
        st.markdown("### 📅 Filtrar reseñas por fecha")

        # Convertir la columna 'at' a datetime si aún no lo está
        if not pd.api.types.is_datetime64_any_dtype(df_reviews["at"]):
            df_reviews["at"] = pd.to_datetime(df_reviews["at"], errors='coerce')

        # Evitar errores si todas las fechas son NaT
        if df_reviews["at"].dropna().empty:
            st.warning("⚠️ No hay fechas válidas en las reseñas obtenidas.")
            df_filtered = pd.DataFrame()
        else:
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("📅 Desde:", value=df_reviews["at"].min())
            with col2:
                end_date = st.date_input("📅 Hasta:", value=df_reviews["at"].max())

            # Aplicar el filtro de fechas
            df_filtered = df_reviews[(df_reviews["at"] >= pd.to_datetime(start_date)) & 
                                     (df_reviews["at"] <= pd.to_datetime(end_date))]

            # Verificación después del filtrado
            if df_filtered.empty:
                st.warning("⚠️ No hay reseñas en el rango de fechas seleccionado.")
else:
    df_filtered = pd.DataFrame()
    st.warning("⚠️ No hay reseñas disponibles para filtrar.")


if not df_filtered.empty:
    # Para Android
    android_reviews = df_filtered[df_filtered["source"] == "Android"]
    avg_score_android = android_reviews["score"].mean() if not android_reviews.empty else "No disponible"
    total_reviews_android = len(android_reviews) if not android_reviews.empty else "No disponible"

    # Para iOS
    ios_reviews = df_filtered[df_filtered["source"] == "iOS"]
    avg_score_ios = ios_reviews["score"].mean() if not ios_reviews.empty else "No disponible"
    total_reviews_ios = len(ios_reviews) if not ios_reviews.empty else "No disponible"
else:
    avg_score_android = "No disponible"
    total_reviews_android = "No disponible"
    avg_score_ios = "No disponible"
    total_reviews_ios = "No disponible"

# Verifica que se haya ingresado una app, seleccionado un país y una plataforma
if app_name and selected_country and selected_platform and (app_id_android or app_id_ios):
    # 🔹 **Mostrar KPIs combinados con valores filtrados**
    st.markdown("---")
    st.markdown("<h3 style='text-align: center;'>📊 Métricas de la Aplicación</h3>", unsafe_allow_html=True)

    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns([1, 1, 1, 1])
    st.markdown("---")

    st.markdown("""
        <style>
            .kpi-container {
                display: flex;
                justify-content: center;
                gap: 15px;
                flex-wrap: wrap;
            }
            .kpi-box {
                background-color: rgba(255, 100, 100, 0.9);
                padding: 15px;
                border-radius: 15px;
                text-align: center;
                font-weight: bold;
                box-shadow: 4px 4px 10px rgba(0,0,0,0.2);
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-height: 130px;
                max-width: 100%;
                word-wrap: break-word;
            }
            .kpi-title { font-size: 18px; color: #fff; font-weight: bold; text-align: center; }
            .kpi-value { font-size: 16px; color: #fff; font-weight: bold; text-align: center; line-height: 1.4; }
        </style>
    """, unsafe_allow_html=True)



    st.markdown("""
        <style>
            .kpi-container {
                display: flex;
                justify-content: center;
                gap: 15px;
                flex-wrap: wrap;
            }
            .kpi-box {
                background-color: rgba(255, 100, 100, 0.9);
                padding: 15px;
                border-radius: 15px;
                text-align: center;
                font-weight: bold;
                box-shadow: 4px 4px 10px rgba(0,0,0,0.2);
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-height: 130px;
                max-width: 100%;
                word-wrap: break-word;
            }
            .kpi-title { font-size: 18px; color: #fff; font-weight: bold; text-align: center; }
            .kpi-value { font-size: 16px; color: #fff; font-weight: bold; text-align: center; line-height: 1.4; }
        </style>
    """, unsafe_allow_html=True)


    def render_kpi(title, android_value, ios_value, is_integer=False):
        if is_integer:
            android_display = f"{int(android_value):,}" if isinstance(android_value, (float, int)) else android_value
            ios_display = f"{int(ios_value):,}" if isinstance(ios_value, (float, int)) else ios_value
        else:
            android_display = f"{android_value:.1f}" if isinstance(android_value, (float, int)) else android_value
            ios_display = f"{ios_value:.1f}" if isinstance(ios_value, (float, int)) else ios_value

        return f"""
            <div class="kpi-box">
                <div class="kpi-title">{title}</div>
                <div class="kpi-value">Android: {android_display}</div>
                <div class="kpi-value">iOS: {ios_display}</div>
            </div>
        """

    with col_kpi1:
        st.markdown(render_kpi("⭐ Puntuación", avg_score_android, avg_score_ios), unsafe_allow_html=True)
    with col_kpi2:
        st.markdown(render_kpi("💬 Reseñas", total_reviews_android, total_reviews_ios, is_integer=True), unsafe_allow_html=True)  # Aquí aseguramos que sean enteros
    with col_kpi3:
        st.markdown(render_kpi("📥 Descargas", downloads_android, "No disponible"), unsafe_allow_html=True)
    with col_kpi4:
        st.markdown(render_kpi("🆕 Última Actualización", last_release_android, "No disponible"), unsafe_allow_html=True)


# 🔹 **Selector de nivel de agregación**
if not df_reviews.empty:
    st.markdown("---")
    st.markdown("### 📊 Selecciona el nivel de agregación:")
    agg_option = st.radio("", ["Diario", "Semanal", "Mensual", "Anual"], index=1, horizontal=True)

    # Convertir la columna 'at' a datetime si no lo es
    df_reviews["at"] = pd.to_datetime(df_reviews["at"], errors='coerce')

    # **Aplicar agregación según la selección**
    if agg_option == "Diario":
        df_reviews["date"] = df_reviews["at"].dt.date  # Mantener en formato de fecha
    elif agg_option == "Semanal":
        df_reviews["date"] = df_reviews["at"].dt.to_period("W").apply(lambda r: r.start_time)
    elif agg_option == "Mensual":
        df_reviews["date"] = df_reviews["at"].dt.to_period("M").apply(lambda r: r.start_time)
    elif agg_option == "Anual":
        df_reviews["date"] = df_reviews["at"].dt.to_period("Y").apply(lambda r: r.start_time)

    # Convertir todo a timestamps después de la conversión de periodos
    df_reviews["date"] = pd.to_datetime(df_reviews["date"], errors='coerce')

    # **Agrupar por fecha y plataforma**
    grouped_counts = df_reviews.groupby(["date", "source"]).size().reset_index(name="Cantidad de Reseñas")
    grouped_avg_score = df_reviews.groupby(["date", "source"])["score"].mean().reset_index(name="Calificación Promedio")

    # 🔹 **Corrección para iOS: NO rellenar fechas vacías, solo mantener datos reales**
    if not grouped_counts.empty:
        android_data = grouped_counts[grouped_counts["source"] == "Android"]
        ios_data = grouped_counts[grouped_counts["source"] == "iOS"]

        android_avg_score = grouped_avg_score[grouped_avg_score["source"] == "Android"]
        ios_avg_score = grouped_avg_score[grouped_avg_score["source"] == "iOS"]

# # 🔹 **Aplicar el filtro de fechas al dataframe antes de graficar**
if not df_filtered.empty:
    filtered_counts = grouped_counts[(grouped_counts["date"] >= pd.to_datetime(start_date)) & 
                                     (grouped_counts["date"] <= pd.to_datetime(end_date))]
    
    filtered_avg_score = grouped_avg_score[(grouped_avg_score["date"] >= pd.to_datetime(start_date)) & 
                                           (grouped_avg_score["date"] <= pd.to_datetime(end_date))]
    
    # 🔹 **Fusionar y alinear los datos de ambas plataformas**
    all_dates = pd.date_range(start=start_date, end=end_date, freq="D")
    df_dates = pd.DataFrame({"date": all_dates})
    
    merged_counts = df_dates.merge(filtered_counts, on="date", how="left").fillna(0)
    merged_avg_score = df_dates.merge(filtered_avg_score, on="date", how="left").fillna(0)

    # 🔹 **Convertir la estructura a formato de barras agrupadas**
    pivot_counts = merged_counts.pivot(index="date", columns="source", values="Cantidad de Reseñas").fillna(0)
    pivot_avg_score = merged_avg_score.pivot(index="date", columns="source", values="Calificación Promedio").fillna(0)

    # Asegurar que ambas columnas existan en pivot_counts
if "Android" not in pivot_counts.columns:
    pivot_counts["Android"] = 0
if "iOS" not in pivot_counts.columns:
    pivot_counts["iOS"] = 0

# 🔹 **Crear gráfico con barras agrupadas**
fig1 = go.Figure()

# Agregar las barras de Android
fig1.add_trace(go.Bar(
    x=pivot_counts.index,
    y=pivot_counts["Android"],
    name="Android",
    marker=dict(color="red"),
))

# Agregar las barras de iOS
fig1.add_trace(go.Bar(
    x=pivot_counts.index,
    y=pivot_counts["iOS"],
    name="iOS",
    marker=dict(color="green"),
))

# 🔹 **Agregar líneas de calificación promedio**
if "Android" in pivot_avg_score.columns and not pivot_avg_score["Android"].isna().all():
    fig1.add_trace(go.Scatter(
        x=pivot_avg_score.index,
        y=pivot_avg_score["Android"],
        mode="lines+markers",
        name="Calificación Promedio - Android",
        line=dict(color="blue", width=2),
        yaxis="y2",
    ))

if "iOS" in pivot_avg_score.columns and not pivot_avg_score["iOS"].isna().all():
    fig1.add_trace(go.Scatter(
        x=pivot_avg_score.index,
        y=pivot_avg_score["iOS"],
        mode="lines+markers",
        name="Calificación Promedio - iOS",
        line=dict(color="orange", width=2),
        yaxis="y2",
    ))

# 🔹 **Configurar diseño del gráfico con barras agrupadas**
fig1.update_layout(
    title="📈 Evolución de reseñas",
    xaxis=dict(title="Fecha", tickangle=-45, tickformat="%b %d"),
    yaxis=dict(title="Cantidad de Reseñas", side="left"),
    yaxis2=dict(title="Calificación Promedio", overlaying="y", side="right"),
    legend=dict(x=0, y=1.1, orientation="h"),
    barmode="group",  # **AGRUPAR LAS BARRAS CORRECTAMENTE**
)

# Mostrar el gráfico en Streamlit
st.plotly_chart(fig1, use_container_width=True)





