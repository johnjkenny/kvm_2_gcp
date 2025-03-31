FROM mysql:latest

COPY init.sql /docker-entrypoint-initdb.d/
COPY docker-entrypoint.sh /custom-entrypoint.sh
RUN chmod 755 /docker-entrypoint-initdb.d/init.sql
RUN chmod 755 /custom-entrypoint.sh

ENTRYPOINT ["/custom-entrypoint.sh"]
