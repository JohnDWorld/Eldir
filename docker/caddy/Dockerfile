# Caddy + plugin DNS OVH.
#
# Le certificat Let's Encrypt est obtenu par challenge DNS-01 (un
# enregistrement TXT posé via l'API OVH), et non par HTTP-01. Conséquence :
# aucun port n'a besoin d'être joignable depuis Internet, Eldir peut rester
# entièrement derrière le tailnet tout en servant un vrai certificat valide,
# ce qui est indispensable au service worker de la PWA (contexte sécurisé).
#
# L'image officielle `caddy` n'embarque aucun module DNS, d'où la
# recompilation via xcaddy.
FROM caddy:2-builder-alpine AS builder
RUN xcaddy build --with github.com/caddy-dns/ovh

FROM caddy:2-alpine
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
