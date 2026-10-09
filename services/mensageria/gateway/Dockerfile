FROM evoapicloud/evolution-api:v2.3.7
COPY interativos-237.cjs /evolution/meshcraft-interativos-237.cjs
RUN node /evolution/meshcraft-interativos-237.cjs /evolution/dist/main.js \
    && node --check /evolution/dist/main.js
