#!/bin/bash
ssh -p 443 -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -R 0:localhost:9101 a.pinggy.io 2>&1 | while IFS= read -r line; do
    echo "$line"
    if [[ "$line" =~ https://[^[:space:]]+\.run\.pinggy-free\.link ]]; then
        echo "$line" > /tmp/pinggy_url.txt
    fi
done