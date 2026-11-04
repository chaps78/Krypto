#!/usr/bin/env bash
# Menu de gestion du service krypto-front (front Django).
# A lancer sur le serveur front :  ./deploy/krypto-front.sh
# Les actions qui modifient le service demandent le mot de passe sudo.

SERVICE="krypto-front"
UNIT_SRC="$(cd "$(dirname "$0")" && pwd)/krypto-front.service"
UNIT_DST="/etc/systemd/system/${SERVICE}.service"
URL="http://100.90.255.68:8010/connexion/"

pause() { echo; read -rp "Entrée pour revenir au menu..." _; }

etat() {
    if systemctl is-active --quiet "$SERVICE"; then
        echo "actif"
    elif [ -f "$UNIT_DST" ]; then
        echo "arrêté"
    else
        echo "non installé"
    fi
}

while true; do
    clear
    echo "=========================================="
    echo "   Krypto FRONT  -  état : $(etat)"
    echo "=========================================="
    echo " 1 - Etat du service"
    echo " 2 - Tester le front (page de connexion)"
    echo " 3 - Voir les logs en direct (Ctrl+C pour sortir)"
    echo " 4 - Démarrer"
    echo " 5 - Redémarrer (après un git pull)"
    echo " 6 - Arrêter"
    echo " 7 - Installer / mettre à jour le service et l'activer au démarrage"
    echo " 8 - Ne plus lancer au démarrage"
    echo " q - Quitter"
    echo "------------------------------------------"
    read -rp "Choix : " choix
    echo
    case "$choix" in
        1) systemctl status "$SERVICE" --no-pager; pause ;;
        2) curl -sS -o /dev/null -w 'HTTP %{http_code}\n' --max-time 10 "$URL" || echo "Le front ne répond pas."; pause ;;
        3) trap 'true' INT; journalctl -u "$SERVICE" -f; trap - INT ;;
        4) sudo systemctl start "$SERVICE" && echo "Démarré."; pause ;;
        5) sudo systemctl restart "$SERVICE" && echo "Redémarré."; pause ;;
        6) sudo systemctl stop "$SERVICE" && echo "Arrêté."; pause ;;
        7) sudo cp "$UNIT_SRC" "$UNIT_DST" \
             && sudo systemctl daemon-reload \
             && sudo systemctl enable --now "$SERVICE" \
             && echo "Service installé et démarré."; pause ;;
        8) sudo systemctl disable "$SERVICE" && echo "Ne démarrera plus au boot (toujours actif jusqu'à l'arrêt)."; pause ;;
        q|Q) exit 0 ;;
        *) echo "Choix inconnu."; pause ;;
    esac
done
