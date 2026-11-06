import fcntl
import os
import signal
import sys
import time
from datetime import datetime, timezone

from bininterface import binAcces
from sqlInterface import sqlAcces
from telegramInterface import teleAcces
from sheetInterface import sheetAcces
from messages import sur, quantite, montant
import reinjection



class Basics():

    def __init__(self):
        """Instancie les accès SQL, Binance, Telegram et Google Sheet utilisés par la boucle."""
        self.sql = sqlAcces()
        self.bin = binAcces()
        self.tele = teleAcces()
        self.sheet = sheetAcces()

    def plus_proche(self,symbol,ID_client):
        """Renvoie l'ID du palier de la grille dont le prix est le plus proche du prix actuel.

        Utilisé par initialise() quand aucun ordre n'a encore été exécuté sur la stratégie.
        """
        ecart_bet_dic = self.sql.get_ecart_bet_from_symbol(symbol)
        prix_tmp = self.bin.get_price(symbol,ID_client)
        prix = prix_tmp["price"]
        delta = float("inf")
        prix_proche_ID=0
        keys = ecart_bet_dic.keys()
        for key in keys:
            if abs(float(prix)-float(ecart_bet_dic[key][0]))<delta:
                delta = abs(float(prix)-float(ecart_bet_dic[key][0]))
                prix_proche_ID = key
        return prix_proche_ID

    def initialise(self,symbol,ID_client):
        """Pose (ou repose) le couple achat/vente d'une stratégie.

        Si deux ordres NEW sont déjà en place et à jour avec Binance, ne fait rien.
        Sinon : synchronise la base, annule les ordres ouverts, puis place un achat
        et une vente autour du dernier palier exécuté (ou du palier le plus proche
        du prix si aucun ordre n'a encore été exécuté).
        A lancer à la main pour démarrer une nouvelle stratégie (voir main()).
        """
        GO = False
        ordres_ouverts = self.sql.get_orders_status_symbol_filter(self.bin.client.ORDER_STATUS_NEW,symbol,ID_client)
        if len(ordres_ouverts) == 2:
            changement = self.bin.changement_status(symbol,ID_client)
            print("changement : "+ str(changement))
            if changement == []:
                GO = True
            else:
                self.bin.changement_update(changement,symbol,ID_client)
        print(symbol + "\tGO : "+str(GO))
        if GO == False:
            changement = self.bin.changement_status(symbol,ID_client)
            self.bin.changement_update(changement,symbol,ID_client)
            ordres_ouverts = self.sql.get_orders_status_symbol_filter(self.bin.client.ORDER_STATUS_NEW,symbol,ID_client)
            for ordre_ouvert in ordres_ouverts:
                self.bin.cancel_order(ordre_ouvert["ID"],ID_client)
            last_close = self.sql.get_last_filled(symbol,ID_client)
            if last_close != "":
                ID_ecart_last_close = last_close["ID_ecart"]
            else:
                ID_ecart_last_close = self.plus_proche(symbol,ID_client)
            print(ID_ecart_last_close)
            self.bin.new_vente(symbol,ID_ecart_last_close,ID_client)
            self.bin.new_achat(symbol,ID_ecart_last_close,ID_client)

    def log_debug_sans_risque(self,emplacement,message,symbol):
        """new_log_debug() qui ne lève jamais d'exception (message de mise au point)."""
        try:
            self.sql.new_log_debug(emplacement,message,symbol)
        except Exception as inst:
            print("log debug impossible : "+str(inst))

    def unite(self,symbol):
        """Renvoie (devise achetée, devise de cotation) d'une stratégie, ex. ("PEPE", "EUR")."""
        devises = self.sql.get_devises_from_symbol_real(symbol)
        return devises["devise1"], devises["devise2"]

    def texte_partiel(self,symbol,ordre):
        """Message : un ordre exécuté, l'autre seulement en partie."""
        actif, _ = self.unite(symbol)
        sens = "achat" if ordre["sens"] == "BUY" else "vente"
        return ("⏳ "+symbol+" · un ordre exécuté, l'autre seulement en partie :\n"
                +sens+" palier "+str(ordre["ID_ecart"])+", "
                +quantite(ordre["montant_execute"])+" / "+quantite(ordre["montant"])+" "+actif+" exécutés.\n"
                "La partie exécutée est soldée au marché, puis les ordres sont replacés.")

    def texte_reinject_up(self,symbol,ID_client,total,taux_convert,ID,entier):
        """Message : réinvestissement de la part "up" par un achat au marché."""
        actif, cotation = self.unite(symbol)
        qtt = int(total/taux_convert) if entier else total/taux_convert
        return ("📈 "+symbol+" · réinvestissement de "+montant(total)+" "+cotation+"\n"
                "Achat au marché de "+quantite(qtt)+" "+actif+" à ≈ "+quantite(taux_convert)+" "+cotation+","
                " ajoutés au palier "+str(ID)+" · client "+str(ID_client))

    def verification_2_ordres_V2(self,symbol,ID_client):
        """Coeur de la boucle : détecte les exécutions et replace les ordres.

        Synchronise les statuts avec Binance, puis selon les ordres encore ouverts en base :
          - 1 NEW     : un ordre a été exécuté -> calcul du bénéfice, réinjection,
                        Telegram au client, nouveaux achat/vente, mise à jour Google Sheet.
          - 1 PARTIAL : un ordre exécuté, l'autre partiellement -> un_ordre_filled_autre_partial().
          - 0         : les deux exécutés en même temps -> deux_ordres_filled().
          - > 2       : anomalie, simplement loguée.

        Returns:
            None, ou l'exception rencontrée (déjà loguée).
        """
        try:
            changement = self.bin.changement_status(symbol,ID_client)
            self.bin.changement_update(changement,symbol,ID_client)
            ordres_new = self.sql.get_orders_status_symbol_filter(self.bin.client.ORDER_STATUS_NEW,symbol,ID_client)
            ordres_partial = self.sql.get_orders_status_symbol_filter(self.bin.client.ORDER_STATUS_PARTIALLY_FILLED,symbol,ID_client)
            ordres_DB = ordres_partial + ordres_new


            if len(ordres_DB) ==1 :
                if len(ordres_new) == 1:
                    last_filled = self.sql.get_last_filled(symbol,ID_client)
                    try:
                        self.sql.calcul_benefice(symbol,last_filled)
                    except Exception as inst:
                        self.sql.new_log_debug("Ordres V2",str(inst),symbol)
                        print("problème dans calcul benefice")
                        print(str(inst))
                    #############################################################################
                    #                                                                           #
                    #               Ajouter ici la nouvelle fonction pour le calcul de benef    #
                    #                                                                           #
                    #############################################################################
                    self.reinject_benef(symbol,ID_client,last_filled)


                    clients = self.sql.get_clients_infos()
                    if last_filled["montant_execute"] != 0.0:
                        self.tele.send_message(str(last_filled["sens"])+" : "
                                            +symbol+"\n"+str(last_filled["montant_execute"])+"\nLimite : "
                                            + str(last_filled["limite"]),clients[ID_client]["tele"])
                    else:
                        self.tele.send_message(str(last_filled["sens"])+" : "
                                            +symbol+"\n"+str(last_filled["montant"])+"\nLimite : "
                                            + str(last_filled["limite"]),clients[ID_client]["tele"])
                        ordre = self.bin.get_order_info_with_ID(symbol,ID_client,0,0,last_filled["ID"])
                        self.tele.send_message(str(ordre))
                    self.sql.new_log_debug("verification_2_ordres_V2","un ordre FILLED et un NEW : "+str(ordres_DB),symbol)
                    self.un_ordre_filled_autre_new(ordres_DB,symbol,ID_client)
                    self.sheet.update_all_info(symbol,ID_client)
                    # un ordre ferme et un NEW
                elif len(ordres_partial) == 1:
                    self.tele.send_message(sur(lambda: self.texte_partiel(symbol,ordres_partial[0]),
                                               "nouvel ordre avec un partial FILLED "+symbol))
                    self.sql.new_log_debug("verification_2_ordres_V2","un ordre FILLED et un PARTIALY : "+str(ordres_DB),symbol)
                    self.un_ordre_filled_autre_partial(ordres_partial,symbol,ID_client)
                    # un ordre ferme et l autre partialy FILLED
            elif len(ordres_DB) == 0 :
                self.tele.send_message("🔄 "+symbol+" · achat ET vente exécutés en même temps"
                                       " (forte variation du prix).\nLes deux ordres sont replacés.")
                self.sql.new_log_debug("verification_2_ordres_V2","deux ordres FILLED : "+str(ordres_DB),symbol)
                self.deux_ordres_filled(symbol,ID_client)
                #Deux ordres ont ete fermes
            elif len(ordres_DB) > 2 :
                self.sql.new_log_error("verification_2_ordres_V2_trader","probleme de trade", symbol)
        except Exception as inst:
            self.sql.new_log_debug("Ordres V2",str(inst),symbol)
            return inst

    def get_taux_reinjection(self, benef):
        """Taux (%) de la part "local" en fonction du bénéfice : barème de reinjection.py."""
        return reinjection.taux_local(benef)

    def get_taux_up(self, benef):
        """Taux (%) de la part "up" en fonction du bénéfice : barème de reinjection.py."""
        return reinjection.taux_up(benef)

    def reinject_benef(self,symbol,ID_client,last_filled):
        """Redistribue le bénéfice en attente (Devises.benef_TMP) d'une stratégie.

          - local    : taux get_taux_reinjection() -> reinject_local()
          - up       : taux get_taux_up()          -> reinject_up()
          - down     : % Devises.down              -> reinject_down()
          - épargne  : % Devises.epargne_percent   -> compteur Devises.epargne
          - facture  : % Devises.factu_percent     -> compteur Devises.factu
        puis remet benef_TMP à zéro.

        Si Devises.local contient du texte, c'est le nom d'une autre stratégie : le
        bénéfice de l'ordre est alors versé dans le up_TMP de celle-ci (et benef_TMP
        n'est pas remis à zéro).

        Returns:
            None, ou l'exception rencontrée (loguée avec l'étape atteinte : debug_flag).
        """
        benef_tmp = self.sql.get_benef_TMP_and_benef_all_from_symbol(symbol)["TMP"]
        if benef_tmp>0:
            try:
                debug_flag = 0
                repart = self.sql.get_reinject_repartition(symbol)
                debug_flag = 1
                self.log_debug_sans_risque("reinject_benef","répartition du bénéfice en attente : "+str(benef_tmp),symbol)
                if type(repart["local"])==str:
                    self.log_debug_sans_risque("reinject_benef","bénéfice "+str(last_filled["benefice"])
                                               +" versé au up_TMP de "+repart["local"],symbol)
                    self.sql.add_2_up_tmp(repart["local"],last_filled["benefice"])
                else:
                    factu = benef_tmp*repart["factu_prct"]/100
                    debug_flag = 2
                    epargne = benef_tmp*repart["epargne_prct"]/100
                    debug_flag = 3
                    down = benef_tmp*repart["down"]/100
                    debug_flag = 4
                    taux_local = self.get_taux_reinjection(benef_tmp)
                    local = benef_tmp*taux_local/100
                    debug_flag = 5
                    up_tmp = self.get_taux_up(benef_tmp)
                    up = benef_tmp*up_tmp/100
                    debug_flag = 6
                    self.reinject_local(symbol,last_filled,local)
                    debug_flag = 7
                    if down>0:
                        self.reinject_down(symbol,ID_client,down,last_filled)
                    debug_flag = 8
                    self.sql.ajout_epargne_paire_devise(symbol,epargne,ID_client)
                    debug_flag = 9
                    self.reinject_up(symbol,ID_client,up,last_filled)
                    debug_flag = 10
                    self.sql.add_to_factu_from_symbol(symbol,factu)
                    debug_flag = 11
                    self.sql.add_to_benef_TMP(symbol,-benef_tmp)
                    debug_flag = 12
            except Exception as inst:
                self.sql.new_log_debug("Ordres V2"+ " Flag = "+str(debug_flag),str(inst) ,symbol)
                self.tele.send_message("Erreur dans les fonctions Flag = "+ str(debug_flag))
                return inst
            

    def reinject_down(self,symbol,ID_client,down,last_filled):
        """Ajoute la part "down" à un palier situé sous le dernier palier exécuté.

        Descend depuis ID_ecart-1 jusqu'au premier palier dont le gain théorique
        (calcul_benef_with_ID) est inférieur à Obj_gain, et y ajoute down/prix au bet.

        Returns:
            int: ID du palier renforcé.
        """
        ID = int(last_filled["ID_ecart"])-1
        obj = float(self.sql.get_devises_from_symbol(symbol,ID_client)["obj_gain"])
        while ID >= 0:
            if self.sql.calcul_benef_with_ID(symbol,ID)<obj:
                break
            ID-=1
        prix = float(self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID)[2])
        self.sql.add_to_ecart(symbol,ID,down/prix)
        return ID
    
    def reinject_up(self,symbol,ID_client,qtt,last_filled):
        """Accumule la part "up" et l'investit quand le montant est suffisant.

        La quantité est ajoutée à Devises.up_TMP. Dès que up_TMP vaut plus de 6 USDT,
        achète au marché, ajoute la quantité achetée au premier palier au-dessus du
        dernier exécuté dont le gain théorique est inférieur à Obj_gain, puis
        décrémente up_TMP.
        """
        self.sql.add_2_up_tmp(symbol,qtt)
        total = float(self.sql.get_up_tmp(symbol))
        devise_base = self.sql.get_devises_from_symbol(symbol,ID_client)["devise2"]
        if devise_base == "USDT":
            convert_to_usdt = total
        else:
            taux_convert_to_USDT = float(self.bin.get_price(devise_base+"USDT",ID_client)["price"])
            convert_to_usdt = total*taux_convert_to_USDT

        if float(convert_to_usdt)>6:
            symbol_split = symbol.split("_")[0]
            taux_convert = float(self.bin.get_price(symbol_split,ID_client)["price"])
            ID = int(last_filled["ID_ecart"])+1
            max_ID = self.sql.get_max_ID_from_symbol(symbol)
            obj = float(self.sql.get_devises_from_symbol(symbol,ID_client)["obj_gain"])
            while ID <= max_ID:
                if self.sql.calcul_benef_with_ID(symbol,ID)<obj:
                    break
                ID+=1

            dev_entier = self.sql.get_devises_from_symbol(symbol,ID_client)["dev_entiere"]
            self.tele.send_message(sur(lambda: self.texte_reinject_up(symbol,ID_client,total,taux_convert,ID,int(dev_entier)==1),
                                       "Reinject UP "+symbol+" "+str(total)+"\n ID "+str(ID_client)))
            if int(dev_entier) == 1:
                self.bin.new_market_order(symbol,int(total/taux_convert),"BUY",ID_client)
                self.sql.add_to_ecart(symbol,ID,int(total/taux_convert))
                self.sql.add_2_up_tmp(symbol,-int(total/taux_convert)*taux_convert)
            else:
                self.bin.new_market_order(symbol,total/taux_convert,"BUY",ID_client)
                self.sql.add_to_ecart(symbol,ID,total/taux_convert)
                self.sql.add_2_up_tmp(symbol,-total)
        


    def reinject_local(self,symbol,last_filled,qtt):
        """Renforce le palier juste sous le dernier exécuté (ID_ecart-1).

        Ajoute qtt/prix au bet de ce palier et trace l'ajout dans la table ajout.
        """
        current_bet = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,float(last_filled["ID_ecart"])-1)[3]
        prix = float(self.sql.get_ecart_bet_from_symbol_and_ID(symbol,int(last_filled["ID_ecart"])-1)[2])
        self.sql.update_bet_with_ID(symbol,int(last_filled["ID_ecart"])-1,float(current_bet)+qtt/prix)
        self.sql.add_to_ajout(symbol,int(last_filled["ID_ecart"])-1,qtt/prix)

    def un_ordre_filled_autre_new(self,ordres_ouvert,symbol,ID_client):
        """Cas normal : un ordre exécuté, l'autre encore ouvert.

        Annule l'ordre restant puis pose un nouvel achat et une nouvelle vente
        autour du dernier palier exécuté.
        """
        for ordre_ouvert in ordres_ouvert:
            self.bin.cancel_order(ordre_ouvert["ID"],ID_client)
        last_filled_order = self.sql.get_last_filled(symbol,ID_client)
        self.sql.new_log_debug("Nouveaux ordres apres filled",str(last_filled_order),symbol)
        self.bin.new_achat(symbol,last_filled_order["ID_ecart"],ID_client)
        self.bin.new_vente(symbol,last_filled_order["ID_ecart"],ID_client)

    def un_ordre_filled_autre_partial(self,ordres_partiel,symbol,ID_client):
        """Cas : un ordre exécuté, l'autre partiellement exécuté.

        Annule l'ordre partiel, solde sa partie exécutée par un ordre au marché de
        sens inverse, calcule le bénéfice de cet aller-retour, puis pose un nouvel
        achat et une nouvelle vente autour du dernier palier exécuté.
        """
        for ordre in ordres_partiel:
            self.bin.cancel_order_partial(ordre["ID"],ID_client)
            sens = ordre["sens"]
            if sens == self.bin.client.SIDE_BUY:
                ID_market = self.bin.new_market_order(symbol,ordre["montant_execute"],self.bin.client.SIDE_SELL,ID_client)
            if sens == self.bin.client.SIDE_SELL:
                ID_market = self.bin.new_market_order(symbol,ordre["montant_execute"],self.bin.client.SIDE_BUY,ID_client)
        last_filled_order = self.sql.get_last_filled(symbol,ID_client)
        self.bin.calcul_benef_partial(symbol,ID_client,ordre["ID"],ID_market)
        self.sql.new_log_debug("Nouveaux ordres apres filled",str(last_filled_order),symbol)

        self.bin.new_achat(symbol,last_filled_order["ID_ecart"],ID_client)
        self.bin.new_vente(symbol,last_filled_order["ID_ecart"],ID_client)
        
    

    def deux_ordres_filled(self,symbol,ID_client):
        """Cas : l'achat et la vente ont été exécutés en même temps.

        Pose un achat sous le dernier achat et une vente au-dessus de la dernière
        vente, chacun augmenté de la quantité des paliers compris entre les deux.
        Attention : get_last_filled_buy/sell ne filtrent pas sur le client.
        """
        last_filled_order_buy = self.sql.get_last_filled_buy(symbol)
        last_filled_order_sell = self.sql.get_last_filled_sell(symbol)
        montant_interval = self.sql.get_montant_entre_ordres(symbol,
                                                             last_filled_order_buy["ID_ecart"],
                                                             last_filled_order_sell["ID_ecart"])
        bet_ecart = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,last_filled_order_buy["ID_ecart"]-1)
        self.bin.new_limite_order(symbol,
                                  bet_ecart[3]+montant_interval,
                                  bet_ecart[2],
                                  self.bin.client.SIDE_BUY,
                                  last_filled_order_buy["ID_ecart"]-1,
                                  0,
                                  ID_client)

        bet_ecart = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,last_filled_order_sell["ID_ecart"]+1)
        self.bin.new_limite_order(symbol,
                                  bet_ecart[3]+montant_interval,
                                  bet_ecart[2],
                                  self.bin.client.SIDE_SELL,
                                  last_filled_order_sell["ID_ecart"]+1,
                                  0,
                                  ID_client)

    def verification_niveau_VS_timer(self,symbol,ID_client):
        """Rapproche du prix les ordres "accélérés" qui ne sont pas exécutés.

          - niveau 4 ouvert depuis plus de 30 min -> remplacé par un ordre de niveau 3
          - niveau 3 ouvert depuis plus de 1 h    -> remplacé par un ordre de niveau 1
          - niveau 2 ouvert depuis plus de 2 h    -> simplement ré-étiqueté niveau 1 en base
        """
        niveaux = self.sql.get_time_since_open(symbol,ID_client)
        keys = niveaux.keys()
        for key in keys:
            #Delais d attente de 30 min pour un ordre niveau 4
            if int(niveaux[key]["niveau"]) == 4 and niveaux[key]["time"].total_seconds() > 1800:
                self.bin.baisser_niveau_ordre(key,ID_client)
            # Delas d attente de 1 heures pour un ordre de niveau 3
            if int(niveaux[key]["niveau"]) == 3 and niveaux[key]["time"].total_seconds() > 3600:
                self.bin.baisser_niveau_ordre(key,ID_client)
            # Delas d attente de 2 heures pour un ordre de niveau 2
            if int(niveaux[key]["niveau"]) == 2 and niveaux[key]["time"].total_seconds() > 7200:
                self.sql.baisser_niveau_ordre_SQL(key,1)

###########################################################################
#                       ARRET PROPRE ET BATTEMENT                         #
###########################################################################
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Fichier réécrit après chaque stratégie traitée : l'API s'en sert pour savoir
# si le bot tourne (date récente) ou s'il est arrêté / figé.
HEARTBEAT = os.path.join(BASE_DIR, "bot.heartbeat")
# Verrou empêchant deux instances du bot de tourner en même temps.
LOCK = os.path.join(BASE_DIR, "bot.lock")

arret_demande = False


def demander_arret(signum, frame):
    """Signal SIGTERM/SIGINT : le bot s'arrêtera après l'opération en cours."""
    global arret_demande
    arret_demande = True


def battement():
    """Ecrit la date courante dans le fichier de battement."""
    try:
        with open(HEARTBEAT, "w") as f:
            f.write(datetime.now(timezone.utc).isoformat())
    except OSError:
        pass


def verrouiller():
    """Prend le verrou d'instance unique, ou quitte si un autre bot tourne déjà."""
    fichier = open(LOCK, "w")
    try:
        fcntl.flock(fichier, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("Un autre trader.py tourne déjà : abandon.")
        sys.exit(1)
    return fichier  # à garder ouvert tant que le bot tourne


###########################################################################
#                                 MAIN                                    #
###########################################################################
def texte_demarrage(devises):
    """Message de démarrage : liste des stratégies actives ({ID_client: [symbol, ...]})."""
    toutes = [s for liste in devises.values() for s in liste]
    pluriel = "s" if len(toutes) > 1 else ""
    return ("▶️ Bot démarré · "+str(len(toutes))+" stratégie"+pluriel+" active"+pluriel
            +(" : "+", ".join(toutes) if toutes else ""))

def main():
    """Boucle principale du bot.

    Annonce le démarrage sur Telegram (stratégies actives), puis jusqu'à un arrêt demandé (SIGTERM,
    par exemple systemctl stop, ou Ctrl+C) : pour chaque client et chaque
    stratégie active (liste lue une seule fois au démarrage), vérifie les ordres
    et les niveaux, avec une pause de 4 s entre deux stratégies.
    L'arrêt n'interrompt jamais une stratégie en cours de traitement.
    """
    verrou = verrouiller()
    signal.signal(signal.SIGTERM, demander_arret)
    signal.signal(signal.SIGINT, demander_arret)

    basic = Basics()
    DEVISES=basic.sql.get_symbols_actif()

    basic.tele.send_message(sur(lambda: texte_demarrage(DEVISES),"Bonjour 1"))
    # Pour demarrer une nouvelle paire, decommenter et adapter :
    #basic.initialise("SYMBOLE_SUFFIXE", ID_client)

    while not arret_demande:
        for user_ID in DEVISES.keys():
            for DEVISE in DEVISES[user_ID]:
                if arret_demande:
                    break
                basic.verification_2_ordres_V2(DEVISE,user_ID)
                basic.verification_niveau_VS_timer(DEVISE,user_ID)
                battement()
                time.sleep(4)

    try:
        os.remove(HEARTBEAT)
    except OSError:
        pass
    print("Arrêt propre du bot.")
    try:
        basic.tele.send_message("Bot arrêté proprement")
    except Exception:
        pass
    verrou.close()


if __name__ == '__main__':
     main()
