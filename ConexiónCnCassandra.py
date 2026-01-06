from cassandra.cluster import Cluster
from cassandra.policies import RoundRobinPolicy

try:
    cluster = Cluster(
        ['127.0.0.1'],
        protocol_version=4,
        load_balancing_policy=RoundRobinPolicy()
    )
    print("Conexión al cluster creada correctamente")
except Exception as e:
    print(" Error al crear el cluster:", e)
    cluster = None

session = None
if cluster:
    try:
        session = cluster.connect('reddit_analytics')
        print("Conectado al keyspace 'reddit_analytics'")
    except Exception as e:
        print("Error al conectar al keyspace:", e)

if session:
    try:
        select_stmt = "SELECT * FROM youtube_live_comments LIMIT 40"
        rpta = session.execute(select_stmt)

        for fila in rpta:
            print(fila)
    except Exception as e:
        print("Error al ejecutar la consulta:", e)

if cluster:
    cluster.shutdown()
