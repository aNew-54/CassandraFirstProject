from dotenv import load_dotenv
import os
import time
from dateutil import parser
from textblob import TextBlob
from googleapiclient.discovery import build
from cassandra.cluster import Cluster
from cassandra.policies import RoundRobinPolicy

load_dotenv('Credenciales.env')
YOUTUBE_API_KEY = os.getenv('API_KEY')

ALBUM_VIDEOS = {
    'Never Gonna Give You Up': 'dQw4w9WgXcQ'
}

MAX_COMMENTS_PER_VIDEO = 1000000

cluster = Cluster(['127.0.0.1'], protocol_version=4, load_balancing_policy=RoundRobinPolicy())
session = cluster.connect('reddit_analytics')

insert_stmt = session.prepare("""
    INSERT INTO youtube_live_comments (video_id, fecha, autor, comentario, sentimiento)
    VALUES (?, ?, ?, ?, ?)
""")

select_stmt = session.prepare("""
    SELECT fecha, autor, comentario, sentimiento 
    FROM youtube_live_comments 
    WHERE video_id = ? 
    ORDER BY fecha DESC 
    LIMIT 5
""")

youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

for song_name, video_id in ALBUM_VIDEOS.items():
    print(f"\n--- Procesando: {song_name} ({video_id}) ---")
    
    total_procesados = 0
    token = None

    while total_procesados < MAX_COMMENTS_PER_VIDEO:
        try:
            request = youtube.commentThreads().list(
                part="snippet",
                videoId=video_id,
                maxResults=100,
                pageToken=token,
                textFormat="plainText",
                order="relevance"
            )
            response = request.execute()

            batch_count = 0
            for item in response['items']:
                comment = item['snippet']['topLevelComment']['snippet']
                texto = comment['textDisplay']
                score = TextBlob(texto).sentiment.polarity

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
                    pass
            
            total_procesados += batch_count
            print(f"   -> Guardados {batch_count} comentarios (Total: {total_procesados})")

            if 'nextPageToken' in response:
                token = response['nextPageToken']
            else:
                break 
                
            time.sleep(0.5)

        except Exception as e:
            print(f"   [X] Error: {e}")
            break

    print(f"\n--- Últimos 5 comentarios registrados para {song_name} ---")
    try:
        rows = session.execute(select_stmt, [video_id])
        for row in rows:
            print(f"[{row.fecha}] {row.autor}: {row.comentario} (Sent: {row.sentimiento})")
    except Exception as e:
        print(f"   [!] Error al consultar: {e}")