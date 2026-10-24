FROM nginx:alpine

# Azure uses the cloud configuration by default.
# Docker Compose will override this for local development.
ARG NGINX_CONFIG=nginx.cloud.conf

COPY ${NGINX_CONFIG} /etc/nginx/templates/default.conf.template

COPY . /usr/share/nginx/html

EXPOSE 80