# Le proxy de socket de l'amont, avec un seul réglage changé : le délai
# d'inactivité de HAProxy.
#
# Le modèle de configuration de l'image amont fixe `timeout client 10m` et
# `timeout server 10m`, sans variable pour les régler. Or le `docker run -i` d'une
# session reste muet bien plus longtemps : session qui attend l'utilisateur, ou
# commande longue sans sortie.
#
# Mesuré avec l'image amont, côté `docker run` seulement (ce qui arrive au
# conteneur après la coupure n'a pas été observé) :
#   - `docker run -i` muet dans les deux sens : le CLI sort à 600 s pile, en code
#     125, avec « error waiting for container: unexpected EOF » ;
#   - conteneur qui écrit un octet par minute, client muet : toute la sortie
#     arrive, mais le CLI sort quand même en code 125 à la fin, avec le même
#     message affiché à 600 s.
# Mesuré avec le même réglage porté à 24 h (gabarit monté sur l'image amont) : le
# même `docker run -i` muet a tenu 11 minutes et fini en code 0.
#
# Déduit, pas observé : dans le second cas, ce qui est coupé est la requête
# `wait` de la CLI (muette jusqu'à la sortie du conteneur). C'est ce que disent le
# message et le code de sortie, pas une capture du trafic.
#
# Choisi, pas mesuré : 7 jours. L'image construite ici n'a été vérifiée que par
# son gabarit (les deux seules lignes changées), son démarrage et ses réponses
# `_ping` et `info`, pas par un `docker run` muet de 7 jours. Au-delà, la coupure
# reviendrait, par extrapolation de l'observation à 10 minutes : le `docker run`
# de la session sortirait en code 125. C'est le prix de ne jamais garder
# indéfiniment une connexion perdue.
#
# Le `grep` fait échouer la construction si une montée de version de l'amont
# change ces lignes : sans lui, le `sed` ne trouverait rien et le délai de 10
# minutes reviendrait sans bruit.
FROM tecnativa/docker-socket-proxy:0.3.0
RUN sed -i -E 's/^(    timeout (client|server)) 10m$/\1 7d/' /usr/local/etc/haproxy/haproxy.cfg.template \
 && [ "$(grep -Ec '^    timeout (client|server) 7d$' /usr/local/etc/haproxy/haproxy.cfg.template)" = 2 ]
