FROM node:20-alpine AS builder

WORKDIR /app

# Install dependencies needed for node-gyp if necessary
RUN apk add --no-cache python3 make g++

COPY package*.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM node:20-alpine AS runner

WORKDIR /app

# Install ffmpeg for media processing (often needed by WhatsApp bots)
RUN apk add --no-cache ffmpeg

COPY package*.json ./
RUN npm ci --omit=dev

COPY --from=builder /app/dist ./dist

# Create a non-root user (optional, but good practice)
# We will skip it for now to avoid permission issues with mounted volumes

EXPOSE 3000

CMD ["npm", "start"]
