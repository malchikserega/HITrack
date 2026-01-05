FROM redis:7-alpine

RUN apk add --no-cache tzdata
ENV TZ=America/New_York

# Copy Redis configuration
COPY redis.conf /usr/local/etc/redis/redis.conf

# Run Redis with custom config
CMD ["redis-server", "/usr/local/etc/redis/redis.conf"]