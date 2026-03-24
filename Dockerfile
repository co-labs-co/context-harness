# ContextHarness Skills Registry - HTTP Server
# Serves skills.json and skill files via nginx with CORS support

FROM nginx:alpine

# Copy nginx configuration
COPY registry/nginx.conf /etc/nginx/nginx.conf

# Copy registry files
COPY skills.json marketplace.json /usr/share/nginx/html/
COPY skill /usr/share/nginx/html/skill

# Copy web frontend
COPY registry/web /usr/share/nginx/html

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/skills.json || exit 1
