#!/bin/sh
# Aplicado pela manutenção; a candidata não recebe socket nem montagem do host.
set -eu
ponte="$1"
case "$ponte" in br-????????????) ;; *) exit 2 ;; esac
iptables -w -N DOCKER-USER 2>/dev/null || true
iptables -w -C INPUT -i "$ponte" -j DROP 2>/dev/null || iptables -w -I INPUT 1 -i "$ponte" -j DROP
iptables -w -C DOCKER-USER -i "$ponte" ! -o "$ponte" -j DROP 2>/dev/null || iptables -w -I DOCKER-USER 1 -i "$ponte" ! -o "$ponte" -j DROP
