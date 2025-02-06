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
    search_results = search(app_name, lang="es", country=country)
    
    if search_results:
        app_id = search_results[0]['appId']
        st.success(f"✅ Aplicación encontrada: {search_results[0]['title']} (ID: {app_id}) en {country.upper()}")

        app_data = app(app_id, lang='es', country=country)
        all_reviews = []
        continuation_token = None
        max_iterations = 10  # Limitar iteraciones para evitar bucles infinitos
        progress_bar = st.progress(0)

        for i in range(max_iterations):
            try:
                result, continuation_token = reviews(
                    app_id, lang='es', country=country, count=200, continuation_token=continuation_token
                )
                all_reviews.extend(result)
                progress_bar.progress((i + 1) / max_iterations)
                if not continuation_token:
                    break
                time.sleep(2)
            except Exception as e:
                st.error(f"Error al obtener reseñas: {e}")
                break
        
        progress_bar.empty()
        df_reviews = pd.DataFrame(all_reviews)
        cutoff_date = datetime.today() - timedelta(days=180)
        df_reviews["at"] = pd.to_datetime(df_reviews["at"])
        df_reviews = df_reviews[df_reviews["at"] >= cutoff_date]

        # Evolutivo de opiniones por día
        df_reviews["date"] = df_reviews["at"].dt.date  # Cambiar la agregación a diaria
        df_reviews["date"] = pd.to_datetime(df_reviews["date"])  # Asegurar que sea formato de fecha

        # Agrupación diaria
        daily_counts = df_reviews.groupby("date").size().reset_index(name="Cantidad de Reseñas").sort_values(by="date")
        daily_avg_score = df_reviews.groupby("date")["score"].mean().reset_index(name="Calificación Promedio").sort_values(by="date")

        fig1 = go.Figure()

        # Barras de cantidad de reseñas
        fig1.add_trace(go.Bar(x=daily_counts['date'], y=daily_counts['Cantidad de Reseñas'], 
                            name='Cantidad de Reseñas', marker=dict(color='red'), opacity=0.6, yaxis='y1'))

        # Línea de calificación promedio
        fig1.add_trace(go.Scatter(x=daily_avg_score['date'], y=daily_avg_score['Calificación Promedio'], 
                                mode='lines+markers', name='Calificación Promedio', 
                                line=dict(color='blue', width=2), yaxis='y2'))

        # Configuración del gráfico
        fig1.update_layout(
            title="📈 Evolución de reseñas diaria",
            yaxis=dict(title='Cantidad de Reseñas', side='left'),
            yaxis2=dict(title='Calificación Promedio', overlaying='y', side='right'),
            legend=dict(orientation='h', yanchor='bottom', y=0.95, xanchor='center', x=0.5)
        )

        # Ajustar el eje X cronológicamente
        fig1.update_xaxes(tickangle=-45, tickformat='%d-%m-%Y')

        # **🔹 KPIs PRIMERO**
        st.markdown("---")
        st.markdown("<h3 style='text-align: center;'>📊 Métricas de la Aplicación</h3>", unsafe_allow_html=True)

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

        # **🔹 EVOLUCIÓN SEGUNDO**
        st.markdown("---")
        st.plotly_chart(fig1, use_container_width=True, key="fig1")

        # **🔹 DISTRIBUCIÓN Y NUBE AL FINAL**
        df_reviews['score_label'] = df_reviews['score'].apply(lambda x: f'{int(x)}⭐')
        fig_hist = px.histogram(df_reviews, x='score_label', nbins=5, title="📊 Distribución de Calificaciones")
        fig_hist.update_layout(height=400)  # Asegurar que tenga la misma altura que la nube de palabras

        # Nube de palabras
        text = " ".join(str(review) for review in df_reviews["content"].dropna())
        wordcloud = WordCloud(width=800, height=400, background_color='white', stopwords=custom_stopwords).generate(text)
        
        col1, col2 = st.columns(2)

        with col1:
            st.plotly_chart(fig_hist, use_container_width=True, key="fig_hist")

        with col2:
            st.markdown("<h3 style='text-align: center;'>☁️ Nube de Palabras en Reseñas</h3>", unsafe_allow_html=True)
            st.image(wordcloud.to_array(), use_container_width=True, output_format="PNG")

        # Descargar datos
        csv = df_reviews.to_csv(index=False).encode("utf-8")
        st.download_button("📄 Descargar CSV", data=csv, file_name="reseñas_google_play.csv", mime="text/csv")
