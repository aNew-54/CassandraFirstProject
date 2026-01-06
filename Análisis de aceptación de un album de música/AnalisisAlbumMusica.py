from dotenv import load_dotenv
import os
import sys
import time
from datetime import datetime
from dateutil import parser
from textblob import TextBlob

# --- PARCHE PYTHON 3.12 ---
try:
    import asyncore
except ImportError:
    try:
        import pyasyncore as asyncore
        sys.modules['asyncore'] = asyncore
    except ImportError:
        sys.exit(1)

from googleapiclient.discovery import build
from cassandra.cluster import Cluster
from cassandra.policies import RoundRobinPolicy

# --- CONFIGURACIÓN ---
load_dotenv('Credenciales.env')
API_KEY = os.getenv('API_KEY')

# LISTA DE VIDEOS DEL ÁLBUM

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

MAX_COMENTARIOS_POR_VIDEO = 1000 

# --- CONEXIÓN CASSANDRA ---
cluster = Cluster(['127.0.0.1'], protocol_version=4, load_balancing_policy=RoundRobinPolicy())
session = cluster.connect('reddit_analytics')

insert_stmt = session.prepare("""
    INSERT INTO youtube_live_comments (video_id, fecha, autor, comentario, sentimiento)
    VALUES (?, ?, ?, ?, ?)
""")

youtube = build('youtube', 'v3', developerKey=API_KEY)

def procesar_video(nombre_cancion, video_id):
    print(f"\n--- Procesando: {nombre_cancion} ({video_id}) ---")
    
    token = None
    total_procesados = 0
    
    while total_procesados < MAX_COMENTARIOS_POR_VIDEO:
        try:
            # Petición con MAX RESULTS y PAGINATION
            request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=100, # Máximo permitido por YouTube
                pageToken=token, # La clave para pasar de página
                textFormat="plainText",
                order="relevance" # 'relevance' trae los más votados/importantes primero
            )
            response = request.execute()

            # Procesar lote de 100
            batch_count = 0
            for item in response['items']:
                comment = item['snippet']['topLevelComment']['snippet']
                texto = comment['textDisplay']
                
                # Análisis
                score = TextBlob(texto).sentiment.polarity
                
                # Insertar
                try:
                    session.execute(insert_stmt, [
                        video_id,
                        parser.parse(comment['publishedAt']),
                        comment['authorDisplayName'],
                        texto[:100],
                        float(score)
                    ])
                    batch_count += 1
                except Exception:
                    pass # Ignorar duplicados
            
            total_procesados += batch_count
            print(f"   -> Guardados {batch_count} comentarios (Total: {total_procesados})")

            # Obtener el token para la siguiente página
            if 'nextPageToken' in response:
                token = response['nextPageToken']
            else:
                print("   [!] Se acabaron los comentarios en este video.")
                break # Salir del bucle si no hay más páginas
                
            # Pequeña pausa para no saturar
            time.sleep(0.5)

        except Exception as e:
            print(f"   [X] Error o Cuota Excedida: {e}")
            break

# --- EJECUCIÓN DEL BATCH ---
print("INICIANDO ANÁLISIS DE ÁLBUM COMPLETO...")
for nombre, id_video in ALBUM_VIDEOS.items():
    procesar_video(nombre, id_video)

print("\n¡PROCESO TERMINADO! Revisa tu Dashboard.")
cluster.shutdown()