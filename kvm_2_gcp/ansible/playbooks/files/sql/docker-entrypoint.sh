#!/bin/bash

cat > /etc/my.cnf << EOF
[client]
user=root
password=$MYSQL_ROOT_PASSWORD
host=127.0.0.1
port=3306
EOF

chown root:root /etc/my.cnf
chmod 400 /etc/my.cnf

sed -i "s/MY_DATABASE/$MYSQL_DATABASE/g" /docker-entrypoint-initdb.d/init.sql
sed -i "s/MY_USER/$MYSQL_USER/g" /docker-entrypoint-initdb.d/init.sql

exec /bin/bash /usr/local/bin/docker-entrypoint.sh mysqld
exit $?
