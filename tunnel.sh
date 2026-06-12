#!/bin/bash
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -R 0:localhost:9101 -p 443 pinggy@a.pinggy.io 2>&1 | while IFS= read -r line; do
  if echo "$line" | grep -oP 'https://[a-z0-9-]+\.run\.pinggy-free\.link' | head -1 > /tmp/tunnel_url.txt; then
    echo "$line"
  fi
  echo "$line" >> /tmp/pinggy_output.txt
done
