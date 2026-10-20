FROM nginx:stable-alpine@sha256:970364228b1e4f932abc22d321932816782cca8a20b85a77552a7cfe9acfb3b5
COPY gateway/default.conf.template /etc/nginx/templates/default.conf.template
COPY gateway/entrypoint.sh /hub-entrypoint.sh
COPY source-bundle.zip /usr/share/nginx/html/project-source.zip
RUN chmod +x /hub-entrypoint.sh && sed -i -E "s/worker_processes[[:space:]]+auto;/worker_processes 1;/" /etc/nginx/nginx.conf
EXPOSE 80
ENTRYPOINT ["/bin/sh", "/hub-entrypoint.sh"]
