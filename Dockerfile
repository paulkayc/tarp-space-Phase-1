FROM postgres:16

# Install PostGIS + dependencies
RUN apt-get update && \
    apt-get install -y postgresql-16-postgis-3 postgresql-16-postgis-3-scripts

# Install pgvector
RUN apt-get install -y postgresql-16-pgvector