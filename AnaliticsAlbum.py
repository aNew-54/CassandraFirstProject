import streamlit as st
import pandas as pd
from cassandra.cluster import Cluster
from cassandra.policies import RoundRobinPolicy
import sys


try:
    import asyncore
except ImportError:
    try:
        import pyasyncore as asyncore
        sys.modules['asyncore'] = asyncore
    except ImportError:
        pass

# --- 1. CONFIGURACIÓN E INVENTARIO ---
st.set_page_config(page_title="Análisis: From Zero", layout="wide", page_icon="💿")

# DICCIONARIO DEL ÁLBUM (Linkin Park - From Zero)
ALBUM_VIDEOS = {
    'The Emptiness Machine': 'SRXH9AbT280', 
    'Cut the Bridge': '_f9b0NB5o4E',
    'Heavy is the Crown': 'ZAt8oxY0GQo',
    'Over Each Other': 'fSHoePrnmMw',
    'Casualty': 'aoverLVhD-8',
    'Overflow': 'qaMxFaIZiKY',
    'Two Faced': 'kivUsDGWojU',
    'Stained': 'TWmOZB-9xAw',
    'IGYEIH': 'pa4kv2Z5mvQ',
    'Good Things Go': 'Ip0jJACsE_g',
    'Up From The Bottom': '97Mj6pXYMd8',
    'Unshatter': '_B3ONO5nh6g',
    'Let You Fade': 'jv-laQtaLjE'
}

# Invertimos el diccionario para buscar Nombre a partir del ID (útil para gráficas)
ID_TO_NAME = {v: k for k, v in ALBUM_VIDEOS.items()}

# --- 2. CONEXIÓN A CASSANDRA ---
@st.cache_resource
def get_session():
    try:
        cluster = Cluster(['127.0.0.1'], protocol_version=4, load_balancing_policy=RoundRobinPolicy())
        session = cluster.connect('reddit_analytics')
        return session
    except Exception as e:
        st.error(f"Error conectando a Cassandra: {e}")
        return None

session = get_session()

# --- 3. INTERFAZ GRÁFICA ---
st.title("💿 Dashboard de Análisis: Álbum 'From Zero'")
st.markdown("Análisis de aceptación y sentimiento de comentarios en YouTube.")

# Creamos pestañas para organizar la información
tab1, tab2 = st.tabs(["📊 Comparativa del Álbum", "🎵 Detalle por Canción"])

# ==========================================
# PESTAÑA 1: COMPARATIVA GENERAL
# ==========================================
with tab1:
    st.header("Rendimiento General del Álbum")
    
    if st.button("Generar Reporte Comparativo", type="primary"):
        if session:
            # Preparamos la query con todos los IDs
            ids_lista = list(ALBUM_VIDEOS.values())
            ids_formato_cql = ", ".join([f"'{x}'" for x in ids_lista])
            
            query = f"SELECT video_id, sentimiento, autor FROM youtube_live_comments WHERE video_id IN ({ids_formato_cql})"
            
            try:
                rows = session.execute(query)
                df = pd.DataFrame(list(rows))
                
                if not df.empty:
                    # 1. Agregamos el nombre de la canción al DataFrame
                    df['cancion'] = df['video_id'].map(ID_TO_NAME)
                    
                    # 2. KPIs Generales
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Total Comentarios Analizados", len(df))
                    col_b.metric("Promedio Sentimiento Álbum", f"{df['sentimiento'].mean():.2f}")
                    
                    # Canción favorita (mayor promedio)
                    ranking = df.groupby('cancion')['sentimiento'].mean().sort_values(ascending=False)
                    mejor_cancion = ranking.idxmax()
                    mejor_score = ranking.max()
                    col_c.metric("Canción Favorita", mejor_cancion, f"{mejor_score:.2f}")

                    st.divider()

                    # 3. Gráficos
                    c1, c2 = st.columns(2)
                    
                    with c1:
                        st.subheader("Ranking de Aceptación (Sentimiento Promedio)")
                        # Convertimos a dataframe para que Streamlit lo grafique bien con etiquetas
                        st.bar_chart(ranking)
                        st.caption("Eje Y: Sentimiento (-1 a 1) | Eje X: Canciones")

                    with c2:
                        st.subheader("Volumen de Comentarios (Buzz)")
                        volumen = df['cancion'].value_counts()
                        st.bar_chart(volumen)
                        st.caption("Cantidad de comentarios recolectados por canción")

                    # 4. Tabla de Datos Agrupados
                    st.subheader("Tabla de Datos")
                    resumen = df.groupby('cancion')['sentimiento'].agg(['count', 'mean', 'min', 'max'])
                    resumen.columns = ['Total Comentarios', 'Sentimiento Promedio', 'Mínimo', 'Máximo']
                    st.dataframe(resumen.sort_values(by='Sentimiento Promedio', ascending=False))

                else:
                    st.warning("No se encontraron datos en Cassandra para este álbum. ¿Ejecutaste el script de carga?")
            
            except Exception as e:
                st.error(f"Error en la consulta: {e}")

# ==========================================
# PESTAÑA 2: DETALLE INDIVIDUAL
# ==========================================
with tab2:
    st.header("Explorador de Comentarios")
    
    # Selector (Dropdown) en lugar de escribir ID
    opcion_cancion = st.selectbox("Selecciona una canción:", list(ALBUM_VIDEOS.keys()))
    
    # Obtenemos el ID automáticamente del diccionario
    video_id_seleccionado = ALBUM_VIDEOS[opcion_cancion]
    
    if st.button(f"Analizar '{opcion_cancion}'"):
        query = f"SELECT fecha, autor, comentario, sentimiento FROM youtube_live_comments WHERE video_id = '{video_id_seleccionado}'"
        
        try:
            rows = session.execute(query)
            df_song = pd.DataFrame(list(rows))
            
            if not df_song.empty:
                # Métricas
                c1, c2 = st.columns(2)
                promedio = df_song['sentimiento'].mean()
                c1.metric("Sentimiento Promedio", f"{promedio:.2f}")
                
                # Interpretación rápida
                if promedio > 0.2: estado = "🔥 Éxito Rotundo"
                elif promedio > 0: estado = "✅ Positivo"
                elif promedio > -0.2: estado = "⚖️ Mixto/Polémico"
                else: estado = "❌ Rechazo"
                c2.metric("Veredicto", estado)
                
                # Gráfico de distribución
                st.subheader("Distribución de Opiniones")
                def clasificar(x):
                    if x > 0.1: return 'Positivo'
                    if x < -0.1: return 'Negativo'
                    return 'Neutro'
                
                df_song['tipo'] = df_song['sentimiento'].apply(clasificar)
                st.bar_chart(df_song['tipo'].value_counts())
                
                # Mostrar comentarios destacados (Positivos y Negativos)
                st.subheader("Comentarios Destacados")
                col_pos, col_neg = st.columns(2)
                
                with col_pos:
                    st.success("Top 3 Comentarios Positivos")
                    top_pos = df_song.nlargest(3, 'sentimiento')
                    for i, row in top_pos.iterrows():
                        st.markdown(f"**{row['autor']}**: {row['comentario']}")
                        st.caption(f"Score: {row['sentimiento']:.2f}")
                        st.write("---")

                with col_neg:
                    st.error("Top 3 Comentarios Críticos")
                    top_neg = df_song.nsmallest(3, 'sentimiento')
                    for i, row in top_neg.iterrows():
                        st.markdown(f"**{row['autor']}**: {row['comentario']}")
                        st.caption(f"Score: {row['sentimiento']:.2f}")
                        st.write("---")

            else:
                st.info(f"No hay datos guardados para '{opcion_cancion}'.")

        except Exception as e:
            st.error(f"Error: {e}")