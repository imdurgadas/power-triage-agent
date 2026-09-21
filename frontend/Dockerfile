# Stage 1: Build React/Vite assets
FROM registry.access.redhat.com/ubi9/nodejs-20-minimal:latest AS builder

# Run build steps as root so npm can write to /app
USER root
WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
RUN npm run build

# Stage 2: Serve via Red Hat UBI nginx
FROM registry.access.redhat.com/ubi9/nginx-122:latest

# UBI nginx-122 default document root is /opt/app-root/src
COPY --from=builder /app/dist /opt/app-root/src
# Inject locations into the default server block (nginx.default.d is included inside server{})
COPY nginx.conf /opt/app-root/etc/nginx.default.d/app.conf

# UBI nginx image runs as non-root (uid 1001) by default
EXPOSE 8080

CMD ["nginx", "-g", "daemon off;"]
