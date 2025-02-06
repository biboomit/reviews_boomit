import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from wordcloud import WordCloud, STOPWORDS
from google_play_scraper import app, reviews, search
import time
from datetime import datetime, timedelta

# Configuración de la página
st.set_page_config(page_title="Dashboard de Gestión - Google Play Store", layout="wide")

# Cargar stopwords desde un archivo externo
with open("stopwords.txt", "r", encoding="utf-8") as f:
    custom_stopwords = set(word.strip() for word in f.readlines())

# Título del Dashboard
st.title("📊 Dashboard de Gestión - Google Play Store")

# Selección del país
country_mapping = {
    "Estados Unidos": "us", "Argentina": "ar", "México": "mx", "España": "es",
    "Colombia": "co", "Chile": "cl", "Perú": "pe", "Brasil": "br"
}

selected_country = st.selectbox("🌍 Seleccione el país de la tienda:", list(country_mapping.keys()))
app_name = st.text_input("🔎 Ingrese el nombre de la aplicación:")

if selected_country and app_name:
    country = country_mapping[selected_country]
    
    if "reviews_data" not in st.session_state:
        # Solo descargar si no está en la sesión
        with st.spinner("Descargando datos..."):
            search_results = search(app_name, lang="es", country=country)
            if search_results:
                app_id = search_results[0]['appId']
                st.session_state["app_data"] = app(app_id, lang='es', country=country)

                all_reviews = []
                continuation_token = None
                max_iterations = 10
                for _ in range(max_iterations):
                    try:
                        result, continuation_token = reviews(
                            app_id, lang='es', country=country, count=200, continuation_token=continuation_token
                        )
                        all_reviews.extend(result)
                        if not continuation_token:
                            break
                        time.sleep(2)
                    except Exception as e:
                        st.error(f"Error al obtener reseñas: {e}")
                        break
                
                df_reviews = pd.DataFrame(all_reviews)
                df_reviews["at"] = pd.to_datetime(df_reviews["at"])
                df_reviews = df_reviews[df_reviews["at"] >= datetime.today() - timedelta(days=180)]
                
                st.session_state["reviews_data"] = df_reviews  # Guardar en sesión
        
    else:
        df_reviews = st.session_state["reviews_data"]
    
    # KPIs
    st.markdown("---")
    st.markdown("<h3 style='text-align: center;'>📊 Métricas de la Aplicación</h3>", unsafe_allow_html=True)
    
    app_data = st.session_state["app_data"]
    col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
    with col_kpi1:
        st.markdown("<p style='text-align: center;'>⭐ Puntuación Promedio</p>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='text-align: center;'>{round(app_data['score'], 2)}</h2>", unsafe_allow_html=True)
    with col_kpi2:
        st.markdown("<p style='text-align: center;'>💬 Total Reseñas</p>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='text-align: center;'>{app_data['reviews']:,}</h2>", unsafe_allow_html=True)
    with col_kpi3:
        st.markdown("<p style='text-align: center;'>📥 Descargas</p>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='text-align: center;'>{app_data['installs']}</h2>", unsafe_allow_html=True)
    with col_kpi4:
        st.markdown("<p style='text-align: center;'>🆕 Última actualización</p>", unsafe_allow_html=True)
        st.markdown(f"<h2 style='text-align: center;'>{app_data['lastUpdatedOn']}</h2>", unsafe_allow_html=True)

    # Selector de nivel de detalle sin recargar toda la app
    st.markdown("---")
    selected_view = st.radio("📊 **Selecciona el nivel de agregación:**", 
                             ["Diario", "Semanal", "Mensual", "Anual"], horizontal=True)

    @st.cache_data(ttl=3600)
    def aggregate_reviews(df, view):
        """ Función que agrupa datos sin recargar la app """
        if view == "Diario":
            df["date"] = df["at"].dt.date
        elif view == "Semanal":
            df["date"] = df["at"].dt.to_period("W").apply(lambda r: r.start_time)
        elif view == "Mensual":
            df["date"] = df["at"].dt.to_period("M").apply(lambda r: r.start_time)
        elif view == "Anual":
            df["date"] = df["at"].dt.to_period("Y").apply(lambda r: r.start_time)

        df["date"] = pd.to_datetime(df["date"])
        grouped_counts = df.groupby("date").size().reset_index(name="Cantidad de Reseñas").sort_values(by="date")
        grouped_avg_score = df.groupby("date")["score"].mean().reset_index(name="Calificación Promedio").sort_values(by="date")
        return grouped_counts, grouped_avg_score

    # Obtener los datos agregados según la selección del usuario
    grouped_counts, grouped_avg_score = aggregate_reviews(df_reviews, selected_view)

    # Gráfica de evolución de reseñas
    fig1 = go.Figure()
    fig1.add_trace(go.Bar(x=grouped_counts['date'], y=grouped_counts['Cantidad de Reseñas'], 
                          name='Cantidad de Reseñas', marker=dict(color='red'), opacity=0.6, yaxis='y1'))
    fig1.add_trace(go.Scatter(x=grouped_avg_score['date'], y=grouped_avg_score['Calificación Promedio'], 
                              mode='lines+markers', name='Calificación Promedio', 
                              line=dict(color='blue', width=2), yaxis='y2'))

    fig1.update_layout(
        title="📈 Evolución de reseñas",
        yaxis=dict(title='Cantidad de Reseñas', side='left'),
        yaxis2=dict(title='Calificación Promedio', overlaying='y', side='right'),
        legend=dict(orientation='h', yanchor='bottom', y=0.95, xanchor='center', x=0.5)
    )
    fig1.update_xaxes(tickangle=-45, tickformat='%d-%m-%Y')

    st.plotly_chart(fig1, use_container_width=True, key="fig1")

    # Distribución y nube de palabras
    df_reviews['score_label'] = df_reviews['score'].apply(lambda x: f'{int(x)}⭐')
    fig_hist = px.histogram(df_reviews, x='score_label', nbins=5, title="📊 Distribución de Calificaciones")

    text = " ".join(str(review) for review in df_reviews["content"].dropna())
    wordcloud = WordCloud(width=800, height=400, background_color='white', stopwords=custom_stopwords).generate(text)

    col1, col2 = st.columns(2)
    with col1:
        st.plotly_chart(fig_hist, use_container_width=True, key="fig_hist")

    with col2:
        st.markdown("<h3 style='text-align: center;'>☁️ Nube de Palabras en Reseñas</h3>", unsafe_allow_html=True)
        st.image(wordcloud.to_array(), use_container_width=True, output_format="PNG")
