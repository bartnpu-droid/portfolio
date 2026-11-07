# Serves the static site (site/) with Caddy. Listens on $PORT (set by the host), 8080 by default.
FROM caddy:2-alpine
COPY Caddyfile /etc/caddy/Caddyfile
COPY site /srv
