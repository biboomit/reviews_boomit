import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from wordcloud import WordCloud, STOPWORDS
from google_play_scraper import app, reviews, search
import time
from datetime import datetime, timedelta

# Configuración del diseño
st.set_page_config(page_title="Dashboard de Gestión - Google Play Store", layout="wide")

# Cargar stopwords desde un archivo externo
with open("stopwords.txt", "r", encoding="utf-8") as f:
    custom_stopwords = set(word.strip() for word in f.readlines())

# Estilos personalizados
st.markdown("""
    <style>
        .title {
            font-size: 30px;
            font-weight: bold;
            text-align: center;
            color: #ffffff;
        }
        .comment-box {
            padding: 12px;
            background-color: #222222;
            border-radius: 8px;
            margin-bottom: 10px;
            color: white;
            font-size: 14px;
        }
        .comment-group-title {
            font-size: 18px;
            font-weight: bold;
            margin-bottom: 8px;
        }
    </style>
""", unsafe_allow_html=True)

# Título del Dashboard
st.markdown("<p class='title'>📊 Dashboard de Gestión - Google Play Store</p>", unsafe_allow_html=True)

# Selección del país
country_mapping = {
    "Estados Unidos": "us", "Argentina": "ar", "México": "mx", "España": "es",
    "Colombia": "co", "Chile": "cl", "Perú": "pe", "Brasil": "br",
    "Francia": "fr", "Alemania": "de", "Italia": "it", "Reino Unido": "gb",
    "Canadá": "ca", "Uruguay": "uy", "Nicaragua": "ni", "Ecuador": "ec",
    "Panamá": "pa", "Costa Rica": "cr", "Paraguay": "py"
}

selected_country = st.selectbox("🌍 Seleccione el país de la tienda:", list(country_mapping.keys()))

if selected_country:
    country = country_mapping[selected_country]
    app_name = st.text_input("🔎 Ingrese el nombre de la aplicación:")
else:
    country = None
    app_name = None

if country and app_name and app_name.strip():
    search_results = search(app_name, lang="es", country=country)
    
    if search_results:
        app_id = search_results[0]['appId']
        st.success(f"✅ Aplicación encontrada: {search_results[0]['title']} (ID: {app_id}) en {country.upper()}")

        app_data = app(app_id, lang='es', country=country)

        all_reviews = []
        continuation_token = None
        max_iterations = 50
        iteration = 0

        while iteration < max_iterations:
            try:
                result, continuation_token = reviews(
                    app_id, lang='es', country=country, count=200, continuation_token=continuation_token)
                all_reviews.extend(result)
                if not continuation_token or len(result) == 0:
                    break
                time.sleep(2)
                iteration += 1
            except Exception as e:
                st.error(f"Error al obtener reseñas: {e}")
                break

        df_reviews = pd.DataFrame(all_reviews)

        if not df_reviews.empty:
            # Datos de la aplicación
            app_info = {
                "Title": app_data["title"], "Genre": app_data["genre"], "Score": app_data["score"],
                "Reviews": app_data["reviews"], "Installs": app_data["installs"], "Developer": app_data["developer"],
                "Release Date": app_data["released"], "Last Updated": app_data["lastUpdatedOn"], "Version": app_data["version"],
                "Icon": app_data["icon"]
            }

            # 📥 Botón de descarga arriba de todo
            st.markdown("---")
            st.subheader("📥 Descargar datos de reseñas")

            csv = df_reviews.to_csv(index=False).encode("utf-8")
            excel_filename = "reseñas_google_play.xlsx"
            df_reviews.to_excel(excel_filename, index=False, engine='xlsxwriter')

            col7, col8 = st.columns(2)
            with col7:
                st.download_button("📄 Descargar CSV", data=csv, file_name="reseñas_google_play.csv", mime="text/csv")

            with col8:
                with open(excel_filename, "rb") as excel_file:
                    st.download_button("📊 Descargar Excel", data=excel_file, file_name=excel_filename, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

            # 📊 KPIs de la App
            st.markdown("---")
            col1, col2, col3, col4 = st.columns([1.5, 2, 2, 2])

            with col1:
                st.image(app_info["Icon"], width=120)
                st.subheader(app_info["Title"])
                st.write(f"📌 Género: {app_info['Genre']}")
                st.write(f"⭐ Puntuación: {app_info['Score']} / 5")
                st.write(f"💬 Total Reseñas: {app_info['Reviews']}")
                st.write(f"📥 Descargas: {app_info['Installs']}")
                st.write(f"👨‍💻 Desarrollador: {app_info['Developer']}")
                st.write(f"📅 Lanzamiento: {app_info['Release Date']}")
                st.write(f"🆕 Última actualización: {app_info['Last Updated']}")
                st.write(f"📌 Versión: {app_info['Version']}")

            # 💬 Sección de comentarios
            today = datetime.today().strftime('%Y-%m-%d')
            last_15_days = (datetime.today() - timedelta(days=15)).strftime('%Y-%m-%d')

            recent_comments = df_reviews.nlargest(5, 'at')
            last_15_comments = df_reviews[df_reviews['at'].astype(str) >= last_15_days]
            best_comments = last_15_comments.nlargest(5, 'score')
            worst_comments = last_15_comments.nsmallest(5, 'score')

            with col2:
                st.markdown("<p class='comment-group-title'>🕒 Comentarios más recientes</p>", unsafe_allow_html=True)
                for _, row in recent_comments.iterrows():
                    st.markdown(f"<div class='comment-box'>⭐ {row['score']} - {row['content']}<br><small>{row['at']}</small></div>", unsafe_allow_html=True)

            with col3:
                st.markdown("<p class='comment-group-title'>👍 Top 5 comentarios positivos (últimos 15 días)</p>", unsafe_allow_html=True)
                for _, row in best_comments.iterrows():
                    st.markdown(f"<div class='comment-box'>⭐ {row['score']} - {row['content']}<br><small>{row['at']}</small></div>", unsafe_allow_html=True)

            with col4:
                st.markdown("<p class='comment-group-title'>👎 Top 5 comentarios negativos (últimos 15 días)</p>", unsafe_allow_html=True)
                for _, row in worst_comments.iterrows():
                    st.markdown(f"<div class='comment-box'>⭐ {row['score']} - {row['content']}<br><small>{row['at']}</small></div>", unsafe_allow_html=True)

            # 📊 Gráficos (bajo los comentarios)
            st.markdown("---")
            col5, col6 = st.columns(2)

            with col5:
                st.subheader("📊 Distribución de Calificaciones")
                if "score" in df_reviews.columns and not df_reviews["score"].isna().all():
                    fig, ax = plt.subplots(figsize=(6, 4))
                    sns.countplot(x=df_reviews["score"], palette="Blues", ax=ax)
                    ax.set_xlabel("Calificación")
                    ax.set_ylabel("Cantidad")
                    ax.set_title("⭐ Distribución de Calificaciones")
                    st.pyplot(fig)

            with col6:
                st.subheader("☁️ Nube de Palabras en Reseñas")
                text = " ".join(str(review) for review in df_reviews["content"].dropna())
                wordcloud = WordCloud(width=600, height=400, background_color='white', stopwords=custom_stopwords, max_words=50).generate(text)
                fig, ax = plt.subplots(figsize=(6, 4))
                ax.imshow(wordcloud, interpolation='bilinear')
                ax.axis("off")
                st.pyplot(fig)
