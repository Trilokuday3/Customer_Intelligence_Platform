# spark-submit client for the streaming profile. Same image family as the
# spark-master/spark-worker services so Python and Spark versions match.
FROM apache/spark:3.5.1-python3

USER root
RUN python3 -m pip install --no-cache-dir psycopg2-binary
COPY spark/stream_ingest_job.py spark/upsert_sql.py /app/

# Runs as root so the mounted ivy-cache and checkpoint volumes are writable.
CMD ["/opt/spark/bin/spark-submit", \
     "--master", "spark://spark-master:7077", \
     "--conf", "spark.jars.ivy=/ivy", \
     "--conf", "spark.driver.host=spark-submit", \
     "--conf", "spark.driver.bindAddress=0.0.0.0", \
     "--packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1,org.postgresql:postgresql:42.7.3", \
     "/app/stream_ingest_job.py"]
