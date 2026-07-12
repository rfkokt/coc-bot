#!/usr/bin/env bash
# Jalanin SearXNG di localhost:8080 dengan JSON API aktif.
set -e
cd "$(dirname "$0")"
docker run --rm -d \
  --name searxng-coc \
  -p 8080:8080 \
  -v "$(pwd)/settings.yml:/etc/searxng/settings.yml:ro" \
  -e "BASE_URL=http://localhost:8080/" \
  searxng/searxng:latest
echo "SearXNG jalan di http://localhost:8080"
echo "Test:  curl 'http://localhost:8080/search?q=clash+of+clans&format=json'"
