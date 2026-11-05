#!/usr/bin/env bash
# Pilotage du bot de trading (service systemd krypto-bot), sur le serveur du bot.
#
#   ./deploy/krypto-bot.sh            menu
#   ./deploy/krypto-bot.sh start      démarrer
#   ./deploy/krypto-bot.sh stop       arrêt propre (termine l'opération en cours)
#   ./deploy/krypto-bot.sh restart    redémarrer (après un git pull)
#   ./deploy/krypto-bot.sh status     état
#
# Les actions qui modifient le service demandent le mot de passe sudo.

SERVICE="krypto-bot"
DEPLOY_DIR="$(cd "$(dirname "$0")" && pwd)"
BOT_DIR="$(dirname "$DEPLOY_DIR")"
UNIT_SRC="$DEPLOY_DIR/krypto-bot.service"
UNIT_DST="/etc/systemd/system/${SERVICE}.service"
HEARTBEAT="$BOT_DIR/bot.heartbeat"

pause() { [ -n "$MENU" ] && { echo; read -rp "Entrée pour revenir au menu..." _; }; }

etat() {
    if systemctl is-active --quiet "$SERVICE"; then
        echo "actif"
    elif [ -f "$UNIT_DST" ]; then
        echo "arrêté"
    else
        echo "non installé"
    fi
}

# PID des trader.py lancés à la main (hors service systemd)
bots_manuels() {
    local main_pid
    main_pid=$(systemctl show -p MainPID --value "$SERVICE" 2>/dev/null)
    pgrep -f "python[0-9.]* .*trader\.py" | grep -vx "${main_pid:-0}"
}

battement() {
    if [ -f "$HEARTBEAT" ]; then
        echo "dernier battement il y a $(( $(date +%s) - $(stat -c %Y "$HEARTBEAT") )) s"
    else
        echo "pas de battement"
    fi
}

# Refuse de démarrer si un bot lancé à la main tourne encore (deux bots = ordres en double)
verifier_doublon() {
    local pids
    pids=$(bots_manuels)
    if [ -n "$pids" ]; then
        echo "Un trader.py lancé à la main tourne encore (PID : $(echo $pids))."
        echo "Arrête-le d'abord (choix 9 du menu), sinon deux bots passeraient des ordres."
        return 1
    fi
}

demarrer()   { verifier_doublon && sudo systemctl start "$SERVICE" && echo "Démarré."; }
arreter()    { echo "Arrêt propre en cours (jusqu'à 2 min)..."; sudo systemctl stop "$SERVICE" && echo "Arrêté."; }
redemarrer() { verifier_doublon && echo "Redémarrage (arrêt propre puis démarrage)..." \
               && sudo systemctl restart "$SERVICE" && echo "Redémarré."; }
statut()     { systemctl status "$SERVICE" --no-pager; echo; battement; }

case "$1" in
    start)   demarrer; exit $? ;;
    stop)    arreter; exit $? ;;
    restart) redemarrer; exit $? ;;
    status)  statut; exit 0 ;;
    "")      ;;
    *)       echo "Usage : $0 [start|stop|restart|status]"; exit 1 ;;
esac

MENU=1
while true; do
    clear
    echo "=========================================="
    echo "   Krypto BOT  -  état : $(etat)"
    echo "   $(battement)"
    manuels=$(bots_manuels)
    [ -n "$manuels" ] && echo "   ! trader.py lancé à la main : PID $(echo $manuels)"
    echo "=========================================="
    echo " 1 - Etat du service"
    echo " 2 - Etat vu par l'API (/bot, ce qu'affiche le front)"
    echo " 3 - Voir les logs en direct (Ctrl+C pour sortir)"
    echo " 4 - Démarrer"
    echo " 5 - Redémarrer (après un git pull)"
    echo " 6 - Arrêter proprement"
    echo " 7 - Installer / mettre à jour le service et l'activer au démarrage"
    echo " 8 - Ne plus lancer au démarrage"
    echo " 9 - Arrêter un trader.py lancé à la main"
    echo " q - Quitter"
    echo "------------------------------------------"
    read -rp "Choix : " choix
    echo
    case "$choix" in
        1) statut; pause ;;
        2) curl -sS --max-time 10 http://127.0.0.1:8000/bot && echo || echo "L'API ne répond pas."; pause ;;
        3) trap 'true' INT; journalctl -u "$SERVICE" -f; trap - INT ;;
        4) demarrer; pause ;;
        5) redemarrer; pause ;;
        6) arreter; pause ;;
        7) verifier_doublon \
             && sudo cp "$UNIT_SRC" "$UNIT_DST" \
             && sudo systemctl daemon-reload \
             && sudo systemctl enable --now "$SERVICE" \
             && echo "Service installé et démarré."; pause ;;
        8) sudo systemctl disable "$SERVICE" && echo "Ne démarrera plus au boot (toujours actif jusqu'à l'arrêt)."; pause ;;
        9) pids=$(bots_manuels)
           if [ -z "$pids" ]; then
               echo "Aucun trader.py lancé à la main."
           else
               ps -o pid,lstart,cmd -p "$(echo $pids | tr ' ' ',')"
               read -rp "Envoyer SIGTERM à ces processus ? [o/N] " ok
               if [ "$ok" = "o" ]; then
                   kill -TERM $pids
                   for _ in $(seq 1 120); do [ -z "$(bots_manuels)" ] && break; sleep 1; done
                   if [ -z "$(bots_manuels)" ]; then echo "Arrêté."; else echo "Toujours en vie : kill -9 $(echo $(bots_manuels))"; fi
               fi
           fi
           pause ;;
        q|Q) exit 0 ;;
        *) echo "Choix inconnu."; pause ;;
    esac
done
