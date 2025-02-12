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

# 🔹 **Configurar la página antes de cualquier otro código**
st.set_page_config(page_title="Dashboard de Gestión - Google Play Store", layout="wide")

# 🔹 **Cargar credenciales desde `st.secrets`**
try:
    USERS = dict(st.secrets["users"])  # Convertir `st.secrets` en diccionario
except Exception:
    st.error("❌ Error al cargar las credenciales. Verifica `secrets.toml`.")
    st.stop()

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
            st.session_state["show_welcome"] = True  # Inicializar mensaje de bienvenida
            st.rerun()  
        else:
            st.error("❌ Correo o contraseña incorrectos")

# 🔹 **Verificar si el usuario está autenticado**
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    login()
    st.stop()  # 🔹 **Detenemos la ejecución si no está autenticado**

# 🔹 **Mostrar mensaje de bienvenida solo si `show_welcome` es True**
if st.session_state.get("show_welcome", False):
    st.success(f"✅ Bienvenido, {st.session_state['username']}")

# Inicializar df_reviews como un DataFrame vacío con las columnas necesarias
df_reviews = pd.DataFrame(columns=["at", "score", "content"])

# Cargar stopwords desde un archivo externo
with open("stopwords.txt", "r", encoding="utf-8") as f:
    custom_stopwords = set(word.strip() for word in f.readlines())

# Cargar imagen del logo
logo_path = "company_logo.png"  # Asegúrate de que la imagen está en la misma carpeta del script

# Usar HTML y CSS para alinear correctamente el logo y el título
st.markdown(f"""
    <div style="display: flex; align-items: center; gap: 17px;">
        <img src="data:image/png;base64,{base64.b64encode(open(logo_path, 'rb').read()).decode()}" width="120">
        <h1 style="margin: 5;">Dashboard de Gestión - Google Play Store</h1>
    </div>
""", unsafe_allow_html=True)

# Selección del país y app
country_mapping = {
    "Argentina": "ar",
    "Chile": "cl",
    "Colombia": "co",
    "Ecuador": "ec",
    "El Salvador": "sv",
    "Estados Unidos": "us",
    "Guatemala": "gt",
    "Honduras": "hn",
    "México": "mx",
    "Nicaragua": "ni",
    "Panamá": "pa",
    "Paraguay": "py",
    "Perú": "pe"
}

col1, col2 = st.columns(2)
with col1:
    selected_country = st.selectbox("🌍 Seleccione el país de la tienda:", list(country_mapping.keys()), key="selected_country")
with col2:
    app_name = st.text_input("🔎 Ingrese el nombre de la aplicación:", key="app_name")

# 🔹 **Cuando el usuario elige un país y una app, ocultar el mensaje de bienvenida**
if selected_country and app_name:
    if st.session_state.get("show_welcome", False):  # Verifica si el mensaje de bienvenida sigue activo
        st.session_state["show_welcome"] = False  # Ocultar mensaje de bienvenida
        st.rerun()  # 🔹 **Forzar actualización de la página**

    country = country_mapping[selected_country]
    search_results = search(app_name, lang="es", country=country)

    if search_results:
        app_id = search_results[0]['appId']
        st.success(f"✅ Aplicación encontrada: {search_results[0]['title']} (ID: {app_id}) en {country.upper()}")

        app_data = app(app_id, lang='es', country=country)
        st.write("Datos obtenidos de app_data:", app_data)
        num_downloads = app_data.get("realInstalls", "No disponible")  # realInstalls es más preciso
        timestamp = app_data.get("updated", None) 

        # Convertir `updated` a fecha legible
        if isinstance(timestamp, int):
            last_release_date = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")
        else:
            last_release_date = "No disponible"

        # Guardar valores en sesión para persistencia
        st.session_state["num_downloads"] = num_downloads
        st.session_state["last_release_date"] = last_release_date

        
        if "df_reviews" not in st.session_state:
            all_reviews = []
            continuation_token = None
            max_iterations = 10  

            with st.spinner("📥 Cargando reseñas..."):
                for i in range(max_iterations):
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

            if all_reviews:  # Solo guardamos si hay datos
                df_reviews = pd.DataFrame(all_reviews)
                df_reviews["at"] = pd.to_datetime(df_reviews["at"])
                df_reviews = df_reviews[df_reviews["at"] >= datetime.today() - timedelta(days=90)]
                
                # Agregar descargas al DataFrame en cada fila para poder filtrarlas luego
                df_reviews["installs"] = num_downloads if isinstance(num_downloads, (int, float)) else 0

                # Guardar en la sesión de Streamlit
                st.session_state["df_reviews"] = df_reviews  

        df_reviews = st.session_state["df_reviews"]

        # **FILTRO DE FECHAS**
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.date_input("📅 Desde:", df_reviews["at"].min())
        with col2:
            end_date = st.date_input("📅 Hasta:", df_reviews["at"].max())

        #Verificar que installs realmente está en df_reviews
        st.write("Columnas de df_reviews antes de filtrar:", df_reviews.columns)
        st.write("Vista previa de df_reviews:", df_reviews.head())
        # Filtrar df_reviews basado en la selección de fechas
        df_filtered = df_reviews[(df_reviews["at"] >= pd.to_datetime(start_date)) & (df_reviews["at"] <= pd.to_datetime(end_date))]

        # Calcular descargas aproximadas basadas en reseñas dentro del período seleccionado
        if not df_filtered.empty:
            total_reviews = df_reviews.shape[0]  # Total de reseñas en todo el período
            filtered_reviews_count = df_filtered.shape[0]  # Reseñas dentro del rango filtrado

            # Estimación de descargas basadas en la proporción de reseñas en el período filtrado
            if total_reviews > 0:
                num_downloads_filtered = int((filtered_reviews_count / total_reviews) * st.session_state["num_downloads"])
            else:
                num_downloads_filtered = "No disponible"
        else:
            num_downloads_filtered = "No disponible"



        # Verificar si hay datos en el rango seleccionado
        if not df_filtered.empty:
            avg_score = df_filtered["score"].mean()  # Puntuación promedio
            total_reviews = df_filtered.shape[0]  # Total de reseñas en el período seleccionado

            # Última actualización basada en la fecha más reciente del filtro
            last_update = df_filtered["at"].max().strftime("%Y-%m-%d")

            # 📅 Nueva métrica: Fecha del comentario más reciente basado en el filtro de fechas
            most_recent_review_date = df_filtered["at"].max().strftime("%Y-%m-%d %H:%M") if not df_filtered.empty else "No disponible"

            # Actualizar las métricas en las tarjetas
            st.markdown("---")
            st.markdown("<h3 style='text-align: center;'>📊 Métricas de la Aplicación</h3>", unsafe_allow_html=True)

            col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5 = st.columns(5)
            
            with col_kpi1:
                st.markdown("<h3 style='text-align: center; font-size:22px;'>⭐ Puntuación</h3>", unsafe_allow_html=True)
                st.markdown(f"<h2 style='text-align: center;'>{round(avg_score, 2)}</h2>", unsafe_allow_html=True)

            with col_kpi2:
                st.markdown("<h3 style='text-align: center; font-size:22px;'>💬 Total Reseñas</h3>", unsafe_allow_html=True)
                st.markdown(f"<h2 style='text-align: center;'>{total_reviews:,}</h2>", unsafe_allow_html=True)

            with col_kpi3:
                st.markdown("<h3 style='text-align: center; font-size:22px;'>📥 Descargas</h3>", unsafe_allow_html=True)
                st.markdown(f"<h2 style='text-align: center;'>{st.session_state.get('num_downloads', 'No disponible')}</h2>", unsafe_allow_html=True)

            with col_kpi4:
                st.markdown("<h3 style='text-align: center; font-size:22px;'>🆕 Último Release</h3>", unsafe_allow_html=True)
                st.markdown(f"<h4 style='text-align: center;'>{st.session_state.get('last_release_date', 'No disponible')}</h4>", unsafe_allow_html=True)

            with col_kpi5:
                st.markdown("<h3 style='text-align: center; font-size:22px;'>📅 Review más reciente</h3>", unsafe_allow_html=True)
                st.markdown(f"<h4 style='text-align: center;'>{most_recent_review_date}</h4>", unsafe_allow_html=True)

        else:
            st.warning("No hay datos en el rango de fechas seleccionado.")

        # Línea separadora antes de la selección de agregación
        st.markdown("---")    

        # **Selector de agregación**
        st.markdown("### 📊 Selecciona el nivel de agregación:")
        agg_option = st.radio("", ["Diario", "Semanal", "Mensual", "Anual"], index=1, horizontal=True)

        if agg_option == "Diario":
            df_reviews["date"] = df_reviews["at"].dt.date  # Mantener en formato de fecha
        elif agg_option == "Semanal":
            df_reviews["date"] = df_reviews["at"].dt.to_period("W").apply(lambda r: r.start_time)
        elif agg_option == "Mensual":
            df_reviews["date"] = df_reviews["at"].dt.to_period("M").apply(lambda r: r.start_time)
        elif agg_option == "Anual":
            df_reviews["date"] = df_reviews["at"].dt.to_period("Y").apply(lambda r: r.start_time)
        # Convertir todo a timestamps después de la conversión de periodos para evitar errores
        df_reviews["date"] = pd.to_datetime(df_reviews["date"], errors='coerce')



        # **Gráfico de evolución**
        grouped_counts = df_reviews.groupby("date").size().reset_index(name="Cantidad de Reseñas")
        grouped_avg_score = df_reviews.groupby("date")["score"].mean().reset_index(name="Calificación Promedio")

        fig1 = go.Figure()

        # Agregar las barras rojas de cantidad de reseñas con etiquetas de valores
        fig1.add_trace(go.Bar(
            x=grouped_counts['date'], 
            y=grouped_counts['Cantidad de Reseñas'], 
            name='Cantidad de Reseñas', 
            marker=dict(color='red'), 
            opacity=0.7,
            yaxis='y1',
            text=grouped_counts['Cantidad de Reseñas'],  # Etiquetas de valores
            textposition='outside'  # Ubicación de las etiquetas
        ))

        # Agregar la línea azul de calificación promedio con etiquetas de valores
        fig1.add_trace(go.Scatter(
            x=grouped_avg_score['date'], 
            y=grouped_avg_score['Calificación Promedio'], 
            mode='lines+markers+text',  # Se agregan etiquetas de valores
            name='Calificación Promedio', 
            line=dict(color='blue', width=2), 
            yaxis='y2',
            text=grouped_avg_score['Calificación Promedio'].round(2),  # Etiquetas con 2 decimales
            textposition='top center'  # Ubicación de las etiquetas
        ))

        # Configurar el diseño del gráfico
        fig1.update_layout(
            title="📈 Evolución de reseñas",
            xaxis=dict(title="Fecha", tickangle=-45, tickformat="%b %Y"),
            yaxis=dict(title="Cantidad de Reseñas", side='left'),
            yaxis2=dict(title="Calificación Promedio", overlaying='y', side='right'),
            legend=dict(x=0, y=1.1, orientation="h"),
            barmode="group"
        )

        # Mostrar el gráfico en Streamlit
        st.plotly_chart(fig1, use_container_width=True)


       # **Histograma y Nube de Palabras**
        col1, col2 = st.columns(2)
        df_reviews['score_label'] = df_reviews['score'].apply(lambda x: f'{int(x)}⭐')

        with col1:
            st.markdown("### 📊 Distribución de Calificaciones") 
            # Crear histograma con etiquetas
            fig_hist = px.histogram(df_reviews, x='score_label', nbins=5, title="", text_auto=True)      

            # Ajustar altura, diseño y eliminar títulos de ejes
            fig_hist.update_layout(
                height=400, 
                bargap=0.1,
                xaxis_title="",  # Elimina el título del eje X
                yaxis_title=""   # Elimina el título del eje Y
            )     
            # Mostrar el histograma en Streamlit
            st.plotly_chart(fig_hist, use_container_width=True)


        with col2:
            st.markdown("### ☁️ Nube de Palabras en Reseñas")
            text = " ".join(str(review) for review in df_reviews["content"].dropna())
            wordcloud = WordCloud(width=800, height=450, background_color='white', stopwords=custom_stopwords).generate(text)
            st.image(wordcloud.to_array(), use_container_width=True)



        # **Selector de Top Comentarios**
        st.markdown("---")
        comment_option = st.selectbox("📌 Selecciona tipo de comentarios:", ["Recientes", "Mejores", "Peores"])

        if not df_filtered.empty:
            if comment_option == "Recientes":
                comments = df_filtered[['at', 'score', 'content']].sort_values(by='at', ascending=False).head(10)
            elif comment_option == "Mejores":
                comments = df_filtered[['score', 'content', 'at']].sort_values(by='score', ascending=False).head(10)
            else:
                comments = df_filtered[['score', 'content', 'at']].sort_values(by='score', ascending=True).head(10)

            # **Convertir la columna "score" en estrellas**
            comments["score"] = comments["score"].apply(lambda x: "⭐" * int(x))

            # **Renombrar columnas**
            comments = comments.rename(columns={"at": "Fecha", "content": "Comentario", "score": "Calificación"})

            # **Mostrar la tabla si hay comentarios**
            st.dataframe(comments, hide_index=True, use_container_width=True)
        else:
            st.warning("No hay comentarios en el rango de fechas seleccionado.")


        # **Estilos para ajustar ancho fijo en las dos primeras columnas y expandir la tercera**
        styled_df = comments.style.set_table_styles([
            {"selector": "th", "props": [("text-align", "center")]},  # Centrar encabezados
            {"selector": "td", "props": [("text-align", "center")]},  # Centrar celdas
            {"selector": "td:nth-child(1)", "props": [("width", "150px")]},  # Fijar ancho de "Fecha"
            {"selector": "td:nth-child(2)", "props": [("width", "100px")]},  # Fijar ancho de "Calificación"
            {"selector": "td:nth-child(3)", "props": [("width", "auto"), ("white-space", "normal"), ("word-wrap", "break-word")]}  # Expandir "Comentario"
        ])


# Configuración de OpenAI
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
openai.api_key = OPENAI_API_KEY

if not df_reviews.empty:
            # **Análisis con Asistente de OpenAI**
            st.markdown("---")
            st.markdown("### 🤖 Análisis de Boomit One AI sobre las Reseñas")

            if "content" in df_reviews.columns:
                filtered_reviews = df_reviews[(df_reviews["at"] >= pd.to_datetime(start_date)) & (df_reviews["at"] <= pd.to_datetime(end_date))]
                date_range_text = f"Las siguientes reviews corresponden al período desde {start_date} hasta {end_date}.\n\n"
                comments_text = date_range_text + "\n".join(filtered_reviews["content"].dropna().head(50).tolist()).strip()


                
                if comments_text:  # Solo llamar a OpenAI si hay contenido válido
                    OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]  # Reemplaza con tu clave de OpenAI
                    openai.api_key = OPENAI_API_KEY
                    
                    def get_openai_insights(comments_text):
                        """Genera insights a partir de los comentarios usando un asistente preexistente de OpenAI"""
                        try:
                            client = openai.OpenAI(api_key=OPENAI_API_KEY)  # Crear cliente de OpenAI

                            # Crear un hilo de conversación
                            thread = client.beta.threads.create()

                            # Enviar mensaje al asistente en el hilo creado
                            client.beta.threads.messages.create(
                                thread_id=thread.id,
                                role="user",
                                content=comments_text
                            )

                            # Ejecutar el asistente en el hilo
                            run = client.beta.threads.runs.create(
                                thread_id=thread.id,
                                assistant_id=st.secrets["ASSISTANT_ID"]
                            )

                            # Mostrar indicador de carga
                            with st.spinner("🔄 Generando insights, por favor espera..."):
                                # Esperar la respuesta del asistente
                                while run.status != "completed":
                                    time.sleep(2)  # Espera 2 segundos antes de revisar el estado nuevamente
                                    run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)

                            # Obtener el mensaje de respuesta del asistente
                            messages = client.beta.threads.messages.list(thread_id=thread.id)
                            response_text = messages.data[0].content[0].text.value  # Extraer contenido

                            return response_text

                        except Exception as e:
                            return f"Error al obtener insights de OpenAI: {e}"
                    
                    insights = get_openai_insights(comments_text)
                    st.markdown("#### 🔍 Insights Generados")
                    st.info(insights)
                else:
                    st.warning("No hay suficientes comentarios para generar insights.")


