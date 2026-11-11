import sqlite3
from datetime import datetime, timezone, timedelta
import sys
import os

from telegramInterface import teleAcces
from messages import sur, quantite

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


class sqlAcces():
    def __init__(self):
        """Ouvre DB.db (dans le dossier du script) et prépare Telegram pour les alertes d'erreur."""
        self.con = sqlite3.connect(os.path.join(BASE_DIR, "DB.db"))
        self.cur = self.con.cursor()
        self.tele = teleAcces()


    def new_order(self,ID,symbol,montant,limite,status,date_debut,date_fin,montant_exec,type,sens,ID_ecart,flag_ajout,ID_client,niveau=1,benefice=0.0):
        """Enregistre un nouvel ordre dans la table Ordres.

        flag_ajout : toujours 0 (ancien mécanisme UP, retiré ; colonne conservée).
        """
        try:
            self.cur.execute("INSERT INTO Ordres VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (ID,symbol,montant,limite,status,date_debut,date_fin,montant_exec,type,sens,ID_ecart,int(niveau),int(flag_ajout),benefice,ID_client))
        except sqlite3.IntegrityError as inst:
            self.new_log_error("new_order_SQL",str(inst),symbol)
            return inst
        retour = self.con.commit()
        return retour


    def update_order(self,ID,status,date_fin="",montant_exec="0"):
        """Met à jour le statut, la date de fin et la quantité exécutée d'un ordre."""
        try:
            self.cur.execute("UPDATE Ordres SET status=?,date_fin=?,montant_execute=? WHERE ID=?",
                             (status,date_fin,montant_exec,str(ID)))
        except sqlite3.IntegrityError as inst:
            ordre = self.get_order_info_by_ID(ID)
            self.new_log_error("update_order_SQL",str(inst),ordre["symbol"])
            return inst
        retour = self.con.commit()
        return retour


    def get_orders_status_symbol_filter(self,status,symbol,ID_client):
        """Renvoie les ordres d'une stratégie et d'un client ayant un statut donné.

        Returns:
            list de dict (voir convert_fetch_to_dico).
        """
        try:
            res = self.cur.execute("SELECT * FROM Ordres WHERE status=? AND symbol=? AND ID_client=?",(str(status),str(symbol),str(ID_client)))

        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_orders_status_filter_SQL",str(inst),symbol)
            return inst
        self.con.commit()
        ordres = []
        for ordre in res.fetchall():
            ordres.append(self.convert_fetch_to_dico(ordre))
        return ordres


    def get_time_since_open(self,symbol,ID_user):
        """Renvoie l'ancienneté et le niveau des ordres NEW d'une stratégie.

        Returns:
            dict {ID_ordre: {"time": timedelta depuis l'ouverture, "niveau": int}}.
        """
        ordres_ouverts = self.get_orders_status_symbol_filter("NEW",symbol,ID_user)
        retour = {}
        for ordre_ouvert in ordres_ouverts:
            retour[ordre_ouvert["ID"]] = {"time":((datetime.now(timezone.utc)-datetime.fromisoformat(ordre_ouvert["date_debut"]))),
                                          "niveau":ordre_ouvert["niveau"]}
        return retour



    def get_order_info_by_ID(self,ID):
        """Renvoie un ordre sous forme de dict, ou {} s'il est absent de la base."""
        try:
            res = self.cur.execute("SELECT * FROM Ordres WHERE ID='"+str(ID)+"'")
            self.con.commit()
            ordre_sql = res.fetchall()
            if ordre_sql != []:
                ordre_format = self.convert_fetch_to_dico(ordre_sql[0])
            else:
                return {}
        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_order_info_by_ID_SQL",str(inst),ordre_format["symbol"])
            return inst
        return ordre_format


    def new_log_error(self,emplacement,message,symbol):
        """Enregistre une erreur dans Log et l'envoie sur Telegram.

        Un échec de l'écriture ou de l'envoi est seulement affiché (pas de nouvel
        appel à new_log_error, qui pourrait boucler).
        """
        try:
            self.cur.execute("INSERT INTO Log VALUES(?,?,?,?,?)",
                             (datetime.now(timezone.utc),str(emplacement),str(message),"ERREUR",symbol))
            self.con.commit()
        except Exception as inst:
            print("new_log_error : écriture Log impossible : "+str(inst))
        try:
            self.tele.send_message("log erreur : "+str(message))
        except Exception as inst:
            print("new_log_error : envoi Telegram impossible : "+str(inst))

    def new_log_debug(self,emplacement,message,symbol):
        """Enregistre un message DEBUG dans Log si Config.debug_log vaut 1."""
        res = self.cur.execute("SELECT debug_log FROM Config")
        self.con.commit()
        debug_activate = res.fetchall()[0]
        if debug_activate[0] == 1:
            try:
                self.cur.execute("INSERT INTO Log VALUES(?,?,?,?,?)",(datetime.now(timezone.utc),str(emplacement),str(message),"DEBUG",symbol))
            except Exception as inst:
                self.new_log_error("new_log_debug_SQL",str(inst),symbol)
            self.con.commit()


    def set_ecart_bet(self,fichier_CSV):
        """Charge une grille depuis un CSV dans ecart_bet.

        Format d'une ligne : ID,symbol,prix,bet.
        """
        file = open(fichier_CSV, "r")
        lines = file.readlines()
        file.close()
        try:
            for ligne in lines:
                tab_ligne = ligne.split(",")
                self.cur.execute("INSERT INTO ecart_bet (ID,symbol,prix,bet) VALUES(?,?,?,?)",
                                 (tab_ligne[0],tab_ligne[1],float(tab_ligne[2]),float(tab_ligne[3])))
        except Exception as inst:
            self.new_log_error("set_ecart_bet_SQL",str(inst),"NA")
        self.con.commit()

    def get_ecart_bet_from_symbol(self,symbol):
        """Renvoie la grille complète d'une stratégie.

        Returns:
            dict {ID: [prix, bet]}.
        """
        try:
            res = self.cur.execute("SELECT * FROM ecart_bet WHERE symbol='"+str(symbol)+"'")
        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_ecart_bet_from_symbol_SQL",str(inst),symbol)
            return inst
        self.con.commit()
        ecarts_SQL = res.fetchall()
        ecart_dico = {}
        for ecart_SQL in ecarts_SQL:
            ecart_dico[int(ecart_SQL[0])]=[ecart_SQL[2],ecart_SQL[3]]
        return ecart_dico
    
    #####################################################
    #[2] donne la limite
    #[3] donne le montant du bet
    #####################################################
    def get_ecart_bet_from_symbol_and_ID(self,symbol,ID):
        """Renvoie un palier de la grille.

        Returns:
            tuple (ID, symbol, prix, bet) : [2] = prix, [3] = bet.
            IndexError si le palier n'existe pas.
        """
        try:
            res = self.cur.execute("SELECT * FROM ecart_bet WHERE ID='"+str(ID)+"' AND symbol='"+str(symbol)+"'")
        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_ecart_bet_from_symbol_and_ID_SQL",str(inst),symbol)
            return inst
        self.con.commit()
        ###############
        #Idealement renvoyer un dictionnaire au lieu du tableau
        ###############
        ret = res.fetchall()
        return ret[0]

    def get_last_filled(self,symbol,ID_client):
        """Renvoie le dernier ordre LIMIT exécuté (FILLED) d'une stratégie et d'un client.

        Attention : "dernier" est déterminé par la date d'ouverture (date_debut),
        pas par la date d'exécution.

        Returns:
            dict de l'ordre, ou "" si aucun.
        """
        try:
            res = self.cur.execute("SELECT *, MAX(date_debut) FROM Ordres WHERE status='FILLED' AND type='LIMIT' AND symbol='"
                                   +str(symbol)+"' AND ID_client='"+str(ID_client)+"'")
        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_last_filled_SQL",str(inst),symbol)
            return ""
        self.con.commit()
        ordres = res.fetchall()
        if ordres[0] == (None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None):
            return ""
        ordre = self.convert_fetch_to_dico(ordres[0])
        return ordre

    def get_last_filled_buy(self,symbol):
        """Renvoie le dernier achat LIMIT exécuté d'une stratégie (tous clients).

        Les ordres au marché (achats up, ventes de financement, soldes de partiels)
        sont exclus : ils n'ont pas de palier (ID_ecart = 0).

        Returns:
            dict de l'ordre, ou "" si aucun.
        """
        try:
            res = self.cur.execute("SELECT *, MAX(date_debut) FROM Ordres WHERE sens='BUY' AND status='FILLED' AND type='LIMIT' AND symbol='"+str(symbol)+"'")
        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_last_filled_SQL",str(inst),symbol)
            return ""
        self.con.commit()
        ordres = res.fetchall()
        if ordres[0] == (None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None):
            return ""
        ordre = self.convert_fetch_to_dico(ordres[0])
        return ordre

    def get_last_filled_sell(self,symbol):
        """Renvoie la dernière vente LIMIT exécutée d'une stratégie (tous clients).

        Les ordres au marché sont exclus (voir get_last_filled_buy).

        Returns:
            dict de l'ordre, ou "" si aucun.
        """
        try:
            res = self.cur.execute("SELECT *, MAX(date_debut) FROM Ordres WHERE sens='SELL' AND status='FILLED' AND type='LIMIT' AND symbol='"+str(symbol)+"'")
        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_last_filled_SQL",str(inst),symbol)
            return ""
        self.con.commit()
        ordres = res.fetchall()
        if ordres[0] == (None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None):
            return ""
        ordre = self.convert_fetch_to_dico(ordres[0])
        return ordre

    def update_bet_with_ID(self,symbol,ID,bet_value):
        """Fixe la quantité (bet) d'un palier de la grille."""
        try:

            self.cur.execute("UPDATE ecart_bet SET bet="
                             +str(bet_value)
                             +" WHERE ID="
                             +str(ID)
                             +" AND symbol='"+symbol+"'")
        except sqlite3.IntegrityError as inst:
            self.new_log_error("update_bet_with_ID_SQL",str(inst),symbol)
            return inst
        self.con.commit()


    def ajout_epargne_paire_devise(self,symbol,qtt,ID_client):
        """Ajoute un montant au compteur d'épargne (Devises.epargne) d'une stratégie."""
        epargne = self.get_devises_from_symbol(symbol,ID_client)["epargne"]
        try:
            self.cur.execute("UPDATE Devises SET epargne=? WHERE symbol=?",
                             (qtt+epargne,symbol))
        except sqlite3.IntegrityError as inst:
            self.new_log_error("ajout_benef_paire_devise",str(inst),symbol)
            return inst
        retour = self.con.commit()
        return retour
    
    def calcul_benef_with_ID(self,symbol,ID,limite=0,montant=0):
        """Gain théorique d'un aller-retour du palier ID vers le palier ID+1.

        gain = (prix[ID+1] - prix[ID]) * bet[ID] - frais (0,075 % à l'achat et à la vente).
        Les paramètres limite et montant sont ignorés.

        Returns:
            float, dans la devise de cotation.
        """
        FEE = 0.00075
        limite = self.get_ecart_bet_from_symbol_and_ID(symbol,ID)
        ecart_dessus = self.get_ecart_bet_from_symbol_and_ID(symbol,ID+1)
        delta=float(ecart_dessus[2])-float(limite[2])
        benef = delta*float(limite[3])-FEE*(float(limite[3])*float(limite[2])+float(limite[3])*float(ecart_dessus[2]))
        return benef
    
        

    def convert_fetch_to_dico(self,ordre):
        """Convertit une ligne de la table Ordres en dict (sans la colonne ID_client)."""
        ordre_dico = {"ID":ordre[0],
                      "symbol":ordre[1],
                      "montant":ordre[2],
                      "limite":ordre[3],
                      "status":ordre[4],
                      "date_debut":ordre[5],
                      "date_fin":ordre[6],
                      "montant_execute":ordre[7],
                      "type":ordre[8],
                      "sens":ordre[9],
                      "ID_ecart":ordre[10],
                      "niveau":ordre[11],
                      "flag_ajout":ordre[12],
                      "benefice":ordre[13],
                 }
        return ordre_dico

    def get_symbols(self):
        """Renvoie la liste de toutes les stratégies (actives ou non)."""
        try:
            res = self.cur.execute("SELECT * FROM Devises")

        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_symbols_SQL",str(inst),"GET_SYMBOL")
            return inst
        devises_SQL = res.fetchall()

        devises_ret=[]
        for devise_SQL in devises_SQL:
            devises_ret.append(devise_SQL[0])
        return devises_ret
    
    def get_symbols_client(self,ID_client):
        """Renvoie la liste des stratégies d'un client (actives ou non)."""
        try:
            res = self.cur.execute("SELECT * FROM Devises WHERE client='"+str(ID_client)+"'")

        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_symbols_SQL",str(inst),"GET_SYMBOL")
            return inst
        devises_SQL = res.fetchall()

        devises_ret=[]
        for devise_SQL in devises_SQL:
            devises_ret.append(devise_SQL[0])
        return devises_ret
    
    def get_symbols_actif_client(self,ID_client):
        """Renvoie la liste des stratégies actives d'un client."""
        try:
            res = self.cur.execute("SELECT * FROM Devises WHERE actif=1 AND client='"+str(ID_client)+"'")

        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_symbols_SQL",str(inst),"GET_SYMBOL")
            return inst
        devises_SQL = res.fetchall()

        devises_ret=[]
        for devise_SQL in devises_SQL:
            devises_ret.append(devise_SQL[0])
        return devises_ret
    
    def get_symbols_actif(self):
        """Renvoie les stratégies actives, regroupées par client.

        Returns:
            dict {ID_client: [symbol, ...]}.
        """
        try:
            res = self.cur.execute("SELECT * FROM Devises WHERE actif=1")

        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_symbols_actifs_SQL",str(inst),"GET_SYMBOL")
            return inst
        devises_SQL = res.fetchall()

        devises_ret={}
        for devise_SQL in devises_SQL:
            devises_ret[devise_SQL[8]]=[]
        for devise_SQL in devises_SQL:
            devises_ret[devise_SQL[8]].append(devise_SQL[0])
        return devises_ret
    
    def get_devises_from_symbol(self,symbol,ID_client):
        """Renvoie les paramètres et compteurs d'une stratégie (table Devises).

        Returns:
            dict (devise1, devise2, down, local, up, epargne, actif, client, benef_all,
            benef_tmp, factu_percent, factu, UP_tmp, epargne_prcent, dev_entiere,
            obj_gain), ou "" si la stratégie n'existe pas pour ce client.
        """
        try:
            res = self.cur.execute("SELECT * FROM Devises WHERE symbol='"+str(symbol)+"' and client='"+str(ID_client)+"'")

        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_devises_from_symbol_SQL",str(inst),symbol)
            return inst
        try:
            devises = res.fetchall()[0]
            formated_devises = {"devise1":devises[1],
                                "devise2":devises[2],
                                "down":devises[3],
                                "local":devises[4],
                                "up":devises[5],
                                "epargne":devises[6],
                                "actif":devises[7],
                                "client":devises[8],
                                "benef_all":devises[9],
                                "benef_tmp":devises[10],
                                "factu_percent":devises[11],
                                "factu":devises[12],
                                "UP_tmp":devises[13],
                                "epargne_prcent":devises[14],
                                "dev_entiere":devises[15],
                                "obj_gain":devises[16]
                                }
        except:
            return ""
        return(formated_devises)
    
    def get_devises_from_symbol_real(self,symbol):
        """Comme get_devises_from_symbol(), sans filtrer sur le client."""
        try:
            res = self.cur.execute("SELECT * FROM Devises WHERE symbol='"+str(symbol)+"'")

        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_devises_from_symbol_SQL",str(inst),symbol)
            return inst
        try:
            devises = res.fetchall()[0]
            formated_devises = {"devise1":devises[1],
                                "devise2":devises[2],
                                "down":devises[3],
                                "local":devises[4],
                                "up":devises[5],
                                "epargne":devises[6],
                                "actif":devises[7],
                                "client":devises[8],
                                "benef_all":devises[9],
                                "benef_tmp":devises[10],
                                "factu_percent":devises[11],
                                "factu":devises[12],
                                "UP_tmp":devises[13],
                                "epargne_prcent":devises[14],
                                "dev_entiere":devises[15],
                                "obj_gain":devises[16]
                                }
        except:
            return ""
        return(formated_devises)
    
    def get_max_ID_from_symbol(self,symbol):
        """Renvoie le plus grand ID de palier de la grille d'une stratégie."""
        try:
            res = self.cur.execute("SELECT MAX(ID) FROM ecart_bet WHERE symbol='"+str(symbol)+"'")

        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_max_ID_from_symbol_SQL",str(inst),symbol)
            return inst
        max = res.fetchall()[0]
        return max[0]

    def get_last_reste(self,symbol):
        """Renvoie le dernier relevé de la table reste : {"devise1", "devise2"}.

        Attention : la table reste n'est plus alimentée par le code actuel.
        """
        try:
            res = self.cur.execute("SELECT max(date),symbol,devise1,devise2,last_ID FROM reste WHERE symbol='"+symbol+"'")
        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_last_reste_SQL",str(inst),symbol)
            return inst
        self.con.commit()
        reste = res.fetchall()[0]
        reste_dic = {"devise1":reste[2],"devise2":reste[3]}
        return reste_dic

    #Pour un double achat on recupere le montant entre les deux ordres
    def get_montant_entre_ordres(self,symbol,ID_bas,ID_haut):
        """Somme des bets des paliers situés strictement entre deux paliers.

        L'ordre des deux ID est indifférent. Sert quand l'achat et la vente sont
        exécutés en même temps.
        """
        if ID_bas>ID_haut:
            tmp=ID_bas
            ID_bas=ID_haut
            ID_haut=tmp
        somme=0
        ID_bas +=1
        while ID_bas < ID_haut:
            somme += self.get_ecart_bet_from_symbol_and_ID(symbol,ID_bas)[3]
            ID_bas +=1
        return somme

    def calcul_benefice(self,symbol,last_filled):
        """Calcule le bénéfice réel d'un ordre limite exécuté et l'enregistre.

        Le calcul dépend du sens et du niveau (un niveau 3 ou 4 couvre plusieurs
        paliers). Les frais (0,075 %) de l'ordre sont déduits ; un achat de niveau
        1 ou 2 ne compte que ses frais. Le résultat est enregistré sur l'ordre et
        ajouté à benef_all et benef_TMP. Alerte Telegram si la quantité de l'ordre
        ne correspond pas à la somme des bets attendus.
        """
        FEE=0.00075
        ecart_bet = self.get_ecart_bet_from_symbol(symbol)
        ID_ecart_filled = last_filled["ID_ecart"]

        if last_filled["sens"]=="SELL":
            if last_filled["niveau"] == 1 or last_filled["niveau"] == 2:
                fee_courant=last_filled["montant"]*FEE*last_filled["limite"]
                benef=last_filled["montant"]*(ecart_bet[ID_ecart_filled+1][0]-ecart_bet[ID_ecart_filled][0])
                self.update_order_benef(last_filled["ID"],str(benef-fee_courant),symbol)
            elif last_filled["niveau"] == 3:
                fee_courant=last_filled["montant"]*FEE*last_filled["limite"]
                B1=ecart_bet[ID_ecart_filled-1][1]
                B2=ecart_bet[ID_ecart_filled-2][1]
                if int(B1+B2) != int(last_filled["montant"]):
                    self.alerte_montant(symbol,last_filled,[ID_ecart_filled-2,ID_ecart_filled-1])
                Benef1 = B1*(ecart_bet[ID_ecart_filled+1][0]-ecart_bet[ID_ecart_filled][0])
                Benef2 = B2*(ecart_bet[ID_ecart_filled+1][0]-ecart_bet[ID_ecart_filled-1][0])
                self.update_order_benef(last_filled["ID"],str(Benef1+Benef2-fee_courant),symbol)
            elif last_filled["niveau"] == 4:
                fee_courant=last_filled["montant"]*FEE*last_filled["limite"]
                B1=ecart_bet[ID_ecart_filled-1][1]
                B2=ecart_bet[ID_ecart_filled-2][1]
                B3=ecart_bet[ID_ecart_filled-3][1]
                if int(B1+B2+B3) != int(last_filled["montant"]):
                    self.alerte_montant(symbol,last_filled,[ID_ecart_filled-3,ID_ecart_filled-2,ID_ecart_filled-1])
                Benef1 = B1*(ecart_bet[ID_ecart_filled+1][0]-ecart_bet[ID_ecart_filled][0])
                Benef2 = B2*(ecart_bet[ID_ecart_filled+1][0]-ecart_bet[ID_ecart_filled-1][0])
                Benef3 = B3*(ecart_bet[ID_ecart_filled+1][0]-ecart_bet[ID_ecart_filled-2][0])
                self.update_order_benef(last_filled["ID"],str(Benef1+Benef2+Benef3-fee_courant),symbol)




        elif last_filled["sens"]=="BUY":
            if last_filled["niveau"] == 1 or last_filled["niveau"] == 2:
                fee_courant=last_filled["montant"]*FEE*last_filled["limite"]
                self.update_order_benef(last_filled["ID"],str(-fee_courant),symbol)

            elif last_filled["niveau"] == 3:
                fee_courant=last_filled["montant"]*FEE*last_filled["limite"]
                B1=ecart_bet[ID_ecart_filled][1]        #B1 utilise uniquement pour la verification
                B2=ecart_bet[ID_ecart_filled+1][1]
                if int(B1+B2) != int(last_filled["montant"]):
                    self.alerte_montant(symbol,last_filled,[ID_ecart_filled,ID_ecart_filled+1])
                Benef2 = B2 * (ecart_bet[ID_ecart_filled+1][0]-ecart_bet[ID_ecart_filled][0])
                self.update_order_benef(last_filled["ID"],str(Benef2-fee_courant),symbol)
            
            elif last_filled["niveau"] == 4:
                fee_courant=last_filled["montant"]*FEE*last_filled["limite"]
                B1=ecart_bet[ID_ecart_filled][1]        #B1 utilise uniquement pour la verification
                B2=ecart_bet[ID_ecart_filled+1][1]
                B3=ecart_bet[ID_ecart_filled+2][1]
                if int(B1+B2+B3) != int(last_filled["montant"]):
                    self.alerte_montant(symbol,last_filled,[ID_ecart_filled,ID_ecart_filled+1,ID_ecart_filled+2])
                Benef2 = B2 * (ecart_bet[ID_ecart_filled+1][0]-ecart_bet[ID_ecart_filled][0])
                Benef3 = B3 * (ecart_bet[ID_ecart_filled+2][0]-ecart_bet[ID_ecart_filled][0])
                self.update_order_benef(last_filled["ID"],str(Benef2+Benef3-fee_courant),symbol)
    
    def alerte_montant(self,symbol,last_filled,paliers):
        """Alerte Telegram (un seul message) : la quantité de l'ordre exécuté ne
        correspond pas à la somme actuelle des bets des paliers qu'il couvre."""
        def texte():
            ecart_bet = self.get_ecart_bet_from_symbol(symbol)
            actif = self.get_devises_from_symbol_real(symbol)["devise1"]
            attendu = sum(ecart_bet[p][1] for p in paliers)
            sens = "Vente" if last_filled["sens"] == "SELL" else "Achat"
            return ("⚠️ "+symbol+" · quantité inattendue\n"
                    +sens+" niv. "+str(last_filled["niveau"])+" au palier "+str(last_filled["ID_ecart"])+" : "
                    +quantite(last_filled["montant"])+" "+actif+" dans l'ordre, mais les paliers "
                    +" + ".join(str(p) for p in paliers)+" totalisent aujourd'hui "
                    +quantite(attendu)+" "+actif+".\n"
                    "Le bénéfice enregistré pour cet ordre peut être faux.")
        self.tele.send_message(sur(texte,"probleme de montant : "+symbol+" ordre "+str(last_filled["ID"])
                                   +" montant "+str(last_filled["montant"])))

    def update_order_benef(self,ID,benef,symbol):
        """Enregistre le bénéfice d'un ordre et l'ajoute à benef_all et benef_TMP."""
        benef_round= str(round(float(benef),8))
        self.add_to_benef_all_and_benef_TMP(symbol,benef)
        try:
            self.cur.execute("UPDATE Ordres SET benefice=? WHERE ID=?",
                             (benef_round,str(ID)))
        except sqlite3.IntegrityError as inst:
            ordre = self.get_order_info_by_ID(ID)
            self.new_log_error("update_order_benef_SQL",str(inst),ordre["symbol"])
            return inst
        retour = self.con.commit()
        return retour
    
    
    def add_to_benef_all_and_benef_TMP(self,symbol,benef):
        """Ajoute un bénéfice au cumul total (benef_all) et au montant à redistribuer (benef_TMP)."""
        try:
            benefs_DB = self.get_benef_TMP_and_benef_all_from_symbol(symbol)
            new_benef_all = benefs_DB["ALL"] + float(benef)
            new_benef_tmp = benefs_DB["TMP"] + float(benef)
            self.cur.execute("UPDATE Devises SET benef_all="+str(new_benef_all)+",benef_TMP="+str(new_benef_tmp)+" WHERE symbol='"+symbol+"'")
            self.con.commit()
        except sqlite3.IntegrityError as inst:
            self.new_log_error("add_to_benef_all_and_benef_TMP_SQL",str(inst),symbol)
            return inst    
    
    def add_to_benef_TMP(self,symbol,benef):
        """Ajoute un montant à benef_TMP uniquement (montant négatif pour le remettre à zéro)."""
        try:
            benefs_DB = self.get_benef_TMP_and_benef_all_from_symbol(symbol)
            new_benef_all = benefs_DB["ALL"] + float(benef)
            new_benef_tmp = benefs_DB["TMP"] + float(benef)
            self.cur.execute("UPDATE Devises SET benef_TMP="+str(new_benef_tmp)+" WHERE symbol='"+symbol+"'")
            self.con.commit()
        except sqlite3.IntegrityError as inst:
            self.new_log_error("add_to_benef_TMP_SQL",str(inst),symbol)
            return inst
        

    def get_benef_TMP_and_benef_all_from_symbol(self,symbol):
        """Renvoie {"ALL": benef_all, "TMP": benef_TMP} d'une stratégie."""
        try:
            res = self.cur.execute("SELECT benef_TMP, benef_all FROM Devises WHERE symbol='"+str(symbol)+"'")

        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_benef_TMP_and_benef_all_from_symbol_SQL",str(inst),"GET_SYMBOL")
            return inst
        benefices = res.fetchall()[0]
        benefices_dic = {"ALL":benefices[1],"TMP":benefices[0]}
        return benefices_dic
    
    def add_to_factu_from_symbol(self,symbol,ajout):
        """Ajoute un montant au compteur de facturation (Devises.factu)."""
        try:
            factu = self.get_factu_from_symbol(symbol)
            new_factu = factu + ajout
            self.cur.execute("UPDATE Devises SET factu="+str(new_factu)+" WHERE symbol='"+symbol+"'")
            self.con.commit()
        except sqlite3.IntegrityError as inst:
            self.new_log_error("add_to_factu_from_symbol_SQL",str(inst),symbol)
            return inst
    
    def get_reinject_repartition(self,symbol):
        """Renvoie les pourcentages de répartition du bénéfice d'une stratégie.

        Returns:
            dict {"down", "local", "up", "epargne_prct", "factu_prct"}.
            "local" peut contenir le nom d'une autre stratégie (voir Basics.reinject_benef).
        """
        try:
            res = self.cur.execute("SELECT down, local, up, epargne_percent, factu_percent FROM Devises WHERE symbol='"+str(symbol)+"'")

        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_reinject_repartition_SQL",str(inst),"GET_SYMBOL")
            return inst
        repart = res.fetchall()[0]
        repart_dic = {"down":repart[0],
                         "local":repart[1],
                         "up":repart[2],
                         "epargne_prct":repart[3],
                         "factu_prct":repart[4]}
        return repart_dic
    

    def get_factu_from_symbol(self,symbol):
        """Renvoie le compteur de facturation d'une stratégie (0 si vide)."""
        try:
            res = self.cur.execute("SELECT factu FROM Devises WHERE symbol='"+str(symbol)+"'")

        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_factu_from_symbol_SQL",str(inst),"GET_SYMBOL")
            return inst
        factu = res.fetchall()[0][0]
        if factu == None:
            factu=0
        return factu
    
    def get_dev_entiere(self,symbol):
        """Renvoie 1 si les quantités de la stratégie doivent être entières, 0 sinon."""
        try:
            res = self.cur.execute("SELECT dev_entiere FROM Devises WHERE symbol='"+str(symbol)+"'")

        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_factu_from_symbol_SQL",str(inst),"GET_SYMBOL")
            return inst
        tmp = res.fetchall()
        ent = tmp[0][0]
        return ent


    def get_gain_mois(self,symbol,annee,mois):
        """Somme des bénéfices des ordres ouverts (date_debut) un mois donné.

        Returns:
            float, ou None si aucun ordre.
        """
        date = str(annee)+"-"+"%02.0f"%mois
        try:
            res = self.cur.execute("SELECT SUM(benefice) FROM Ordres WHERE symbol='"
                                   +str(symbol)+"' AND date_debut LIKE '"+date+"%'")
        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_gain_mois_SQL",str(inst),symbol)
            return ""
        self.con.commit()
        ordres = res.fetchall()
        return ordres[0][0]
    
    def max_sell(self,symbol,annee,mois):
        """Renvoie le plus haut palier vendu (FILLED) sur un mois donné."""
        date = str(annee)+"-"+"%02.0f"%mois
        try:
            res = self.cur.execute("SELECT MAX(ID_ecart) FROM Ordres WHERE sens='SELL' AND status='FILLED' AND symbol='"
                                   +str(symbol)+"' AND date_debut LIKE '"+date+"%'")
        except sqlite3.IntegrityError as inst:
            self.new_log_error("max_sell_SQL",str(inst),symbol)
            return ""
        self.con.commit()
        ordres = res.fetchall()
        max_sell = ordres[0][0]
        return max_sell

    def min_buy(self,symbol,annee,mois):
        """Renvoie le plus bas palier acheté (FILLED) sur un mois donné."""
        date = str(annee)+"-"+"%02.0f"%mois
        try:
            res = self.cur.execute("SELECT MIN(ID_ecart) FROM Ordres WHERE sens='BUY' AND status='FILLED' AND symbol='"
                                   +str(symbol)+"' AND date_debut LIKE '"+date+"%'")
        except sqlite3.IntegrityError as inst:
            self.new_log_error("min_buy_SQL",str(inst),symbol)
            return ""
        self.con.commit()
        ordres = res.fetchall()
        min_sell = ordres[0][0]
        return min_sell
    
    def count_sell_ID_ecart(self,symbol,annee,mois,ID_ecart):
        """Compte les ventes exécutées sur un palier pendant un mois.

        Returns:
            [nombre niveaux 1-2, nombre niveau 3, nombre niveau 4].
        """
        date = str(annee)+"-"+"%02.0f"%mois
        try:
            res = self.cur.execute("SELECT COUNT() FROM Ordres "
                                   +"WHERE sens='SELL' AND status='FILLED' AND symbol='"
                                   +str(symbol)+"' AND date_debut LIKE '"+date+"%' AND ID_ecart='"+str(ID_ecart)+"'"
                                   +" AND niveau<3" )
        except sqlite3.IntegrityError as inst:
            self.new_log_error("count_sell_ID_ecart_SQL",str(inst),symbol)
            return ""
        self.con.commit()
        ordres = res.fetchall()
        count_1_2 = ordres[0][0]
        try:
            res = self.cur.execute("SELECT COUNT() FROM Ordres "
                                   +"WHERE sens='SELL' AND status='FILLED' AND symbol='"
                                   +str(symbol)+"' AND date_debut LIKE '"+date+"%' AND ID_ecart='"+str(ID_ecart)+"'"
                                   +" AND niveau=3" )
        except sqlite3.IntegrityError as inst:
            self.new_log_error("count_sell_ID_ecart_SQL",str(inst),symbol)
            return ""
        self.con.commit()
        ordres = res.fetchall()
        count_3 = ordres[0][0]
        try:
            res = self.cur.execute("SELECT COUNT() FROM Ordres "
                                   +"WHERE sens='SELL' AND status='FILLED' AND symbol='"
                                   +str(symbol)+"' AND date_debut LIKE '"+date+"%' AND ID_ecart='"+str(ID_ecart)+"'"
                                   +" AND niveau=4" )
        except sqlite3.IntegrityError as inst:
            self.new_log_error("count_sell_ID_ecart_SQL",str(inst),symbol)
            return ""
        self.con.commit()
        ordres = res.fetchall()
        count_4 = ordres[0][0]
        count=[count_1_2,count_3,count_4]
        return count
    
    def count_buy_ID_ecart(self,symbol,annee,mois,ID_ecart):
        """Compte les achats exécutés sur un palier pendant un mois.

        Returns:
            [nombre niveaux 1-2, nombre niveau 3, nombre niveau 4].
        """
        date = str(annee)+"-"+"%02.0f"%mois
        try:
            res = self.cur.execute("SELECT COUNT() FROM Ordres "
                                   +"WHERE sens='BUY' AND status='FILLED' AND symbol='"
                                   +str(symbol)+"' AND date_debut LIKE '"+date+"%' AND ID_ecart='"+str(ID_ecart)+"'"
                                   +" AND niveau<3" )
        except sqlite3.IntegrityError as inst:
            self.new_log_error("count_buy_ID_ecart_SQL",str(inst),symbol)
            return ""
        self.con.commit()
        ordres = res.fetchall()
        count_1_2 = ordres[0][0]
        try:
            res = self.cur.execute("SELECT COUNT() FROM Ordres "
                                   +"WHERE sens='BUY' AND status='FILLED' AND symbol='"
                                   +str(symbol)+"' AND date_debut LIKE '"+date+"%' AND ID_ecart='"+str(ID_ecart)+"'"
                                   +" AND niveau=3" )
        except sqlite3.IntegrityError as inst:
            self.new_log_error("count_buy_ID_ecart_SQL",str(inst),symbol)
            return ""
        self.con.commit()
        ordres = res.fetchall()
        count_3 = ordres[0][0]
        try:
            res = self.cur.execute("SELECT COUNT() FROM Ordres "
                                   +"WHERE sens='BUY' AND status='FILLED' AND symbol='"
                                   +str(symbol)+"' AND date_debut LIKE '"+date+"%' AND ID_ecart='"+str(ID_ecart)+"'"
                                   +" AND niveau=4" )
        except sqlite3.IntegrityError as inst:
            self.new_log_error("count_buy_ID_ecart_SQL",str(inst),symbol)
            return ""
        self.con.commit()
        ordres = res.fetchall()
        count_4 = ordres[0][0]
        count=[count_1_2,count_3,count_4]
        return count
    
    def baisser_niveau_ordre_SQL(self,key,new_niveau):
        """Change le niveau d'un ordre en base uniquement (l'ordre Binance n'est pas modifié)."""
        try:
            self.cur.execute("UPDATE Ordres SET niveau=? WHERE ID=?",
                             (str(new_niveau),str(key)))
        except sqlite3.IntegrityError as inst:
            ordre = self.get_order_info_by_ID(key)
            self.new_log_error("baisser_niveau_ordre_SQL_SQL",str(inst),ordre["symbol"])
            return inst
        retour = self.con.commit()
        return retour
    
    def add_to_ecart(self,symbol,ID_ecart,valeur_to_add):
        """Ajoute une quantité au bet d'un palier de la grille."""
        try:
            curent_value = self.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart)[3]
            valeur_to_update = curent_value + valeur_to_add
            self.cur.execute("UPDATE ecart_bet SET bet="+str(valeur_to_update)+" WHERE ID="+str(ID_ecart)+" AND symbol='"+symbol+"'")
        except sqlite3.IntegrityError as inst:
            self.new_log_error("add_to_ecart_SQL",str(inst),symbol)
            return inst
        self.con.commit()


            #self

    def get_clients_infos(self):
        """Renvoie tous les comptes de la table client.

        Returns:
            dict {ID_client: {"name", "api", "secret", "tele", "base"}}.
        """
        try:
            res = self.cur.execute("SELECT * FROM client")
        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_clients_infos",str(inst),"NA")
            return inst
        self.con.commit()
        clients = res.fetchall()
        clients_infos={}
        for client in clients:
            clients_infos[client[0]]={}
            clients_infos[client[0]]["name"]=client[1]
            clients_infos[client[0]]["api"]=client[2]
            clients_infos[client[0]]["secret"]=client[3]
            clients_infos[client[0]]["tele"]=client[4]
            clients_infos[client[0]]["base"]=client[5]

        return clients_infos
    
    def set_up_tmp(self,symbol,qtt):
        """Fixe Devises.up_TMP (montant "up" en attente d'investissement)."""
        try:
            self.cur.execute("UPDATE Devises SET up_TMP="
                                 +str(qtt)
                                 +" WHERE symbol='"
                                 +symbol
                                 +"'")
        except sqlite3.IntegrityError as inst:
            self.new_log_error("set_up_tmp_SQL",str(inst),symbol)
            return inst
        self.con.commit()
    
    def get_up_tmp(self,symbol):
        """Renvoie Devises.up_TMP d'une stratégie."""
        try:
            res = self.cur.execute("SELECT up_TMP FROM Devises WHERE symbol='"+symbol+"'")
        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_up_tmp_SQL",str(inst),"NA")
            return inst
        self.con.commit()
        up_TMP = res.fetchall()[0][0]
        return up_TMP
    
    def inserer(self,table,ligne):
        """Ajoute une ligne (dict colonne -> valeur) à une table de journal. Jamais de mise à jour."""
        colonnes = list(ligne.keys())
        self.cur.execute("INSERT INTO "+table+" ("+",".join(colonnes)+") VALUES ("
                         +",".join("?"*len(colonnes))+")", [ligne[c] for c in colonnes])
        self.con.commit()

    def get_parametres_reinjection(self,symbol):
        """Paramètres de la source de réinjection (étape 2) d'une stratégie.

        Valeurs par défaut (comportement d'avant) si les colonnes n'existent pas
        encore (migration deploy/etape2_journal_reinjection.py non lancée).
        """
        defaut = {"source_reinjection":"EUR","ecart_min_ma":0.0,
                  "si_reserves_insuffisantes":"suspendre","reinjection_suspendue":None}
        try:
            r = self.cur.execute("SELECT source_reinjection, ecart_min_ma, si_reserves_insuffisantes, "
                                 "reinjection_suspendue FROM Devises WHERE symbol=?",(symbol,)).fetchone()
        except sqlite3.OperationalError:
            return defaut
        if r is None:
            return defaut
        return {"source_reinjection":r[0] or "EUR","ecart_min_ma":float(r[1] or 0),
                "si_reserves_insuffisantes":r[2] or "suspendre","reinjection_suspendue":r[3]}

    def set_reinjection_suspendue(self,symbol,date):
        """Note (date ISO) ou efface (None) la suspension de la réinjection d'une stratégie."""
        self.cur.execute("UPDATE Devises SET reinjection_suspendue=? WHERE symbol=?",(date,symbol))
        self.con.commit()

    def get_derniere_moyenne(self,paire):
        """Dernières MA7/MA25 1h enregistrées par l'API pour une paire, ou None."""
        try:
            r = self.cur.execute("SELECT ouverture, ma7, ma25 FROM moyennes_mobiles WHERE paire=? AND intervalle='1h' "
                                 "ORDER BY ouverture DESC LIMIT 1",(paire,)).fetchone()
        except sqlite3.OperationalError:
            return None
        return {"ouverture":r[0],"ma7":r[1],"ma25":r[2]} if r else None

    def add_capital_injecte(self,symbol,montant):
        """Ajoute au compteur Devises.capital_injecte (part réinjectée au-delà du bénéfice)."""
        self.cur.execute("UPDATE Devises SET capital_injecte=COALESCE(capital_injecte,0)+? WHERE symbol=?",
                         (float(montant),symbol))
        self.con.commit()

    def add_2_up_tmp(self,symbol,qtt):
        """Ajoute un montant à Devises.up_TMP (part de 0 si la valeur est illisible)."""
        try:
            current_value = float(self.get_up_tmp(symbol))
        except:
            current_value = 0.0
        self.set_up_tmp(symbol,current_value+float(qtt))

    def configure_new_symbol(self,symbol,devise_1,devise_2,perc_down,perc_local,perc_up,ID_client,perc_factu,perc_epargne,dev_entiere,obj_gain):
        """Crée une stratégie dans Devises : active, compteurs à 0, e_dyn à 0."""
        try:
            self.cur.execute("INSERT INTO Devises (symbol,DEVISE1,DEVISE2,down,local,up,epargne,actif,client,"
                             "benef_all,benef_TMP,factu_percent,factu,up_TMP,epargne_percent,dev_entiere,Obj_gain,e_dyn) "
                             "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (symbol,
                              devise_1,
                              devise_2,
                              perc_down,
                              perc_local,
                              perc_up,
                              0.0,
                              1,
                              ID_client,
                              0.0,
                              0.0,
                              perc_factu,
                              0.0,
                              0.0,
                              perc_epargne,
                              dev_entiere,
                              obj_gain,
                              0))
        except sqlite3.IntegrityError as inst:
            self.new_log_error("configure_new_symbol_SQL",str(inst),symbol)
            return inst
        retour = self.con.commit()
        return retour
    
    def new_client(self,client_name,API_key,secret,devise_base,telegram_chat_ID=""):
        """Ajoute un compte client (ID = plus grand ID existant + 1).

        Sans chat Telegram fourni, utilise le chat par défaut -4541800269.
        """
        if telegram_chat_ID == "":
            telegram_chat_ID = "-4541800269"
        try:
            res = self.cur.execute("SELECT MAX(ID_client) FROM client")
            self.con.commit()
            MAX_ID = res.fetchall()[0][0]
            self.cur.execute("INSERT INTO client VALUES(?,?,?,?,?,?)",
                             (str(MAX_ID+1),client_name,str(API_key),str(secret),str(telegram_chat_ID),devise_base))
        except sqlite3.IntegrityError as inst:
            self.new_log_error("new_client_SQL",str(inst),"")
            return inst
        retour = self.con.commit()
        return retour



def main():
    """Outil en ligne de commande.

        python3 sqlInterface.py init       crée une stratégie et charge sa grille CSV
                                           (les 5 pourcentages doivent faire 100)
        python3 sqlInterface.py load_file  charge une grille CSV
    """
    sql = sqlAcces()
    DEVISE='EURUSDT_seb'
    if len(sys.argv) == 2:
        a = sys.argv[1]
        if a == "init":
            CSV_file = input("Quel est le nom du fichier CSV ? ")
            symbol = input("Quel est le symbol? ")
            percent_down = int(input("Quel est le pourcentage down? "))
            percent_local = int(input("Quel est le pourcentage local? "))
            percent_up = int(input("Quel est le pourcentage up? "))
            percent_epargne = int(input("Quel est le pourcentage d'épargne? "))
            percent_factu = int(input("Quel est le pourcentage facturation? "))

            if (percent_down + percent_local + percent_up + percent_epargne + percent_factu) != 100:
                print("La Somme des pourcentages doit être égal à 100")
            else:
                dev_entiere = int(input("la devise doit elle etre entiere ? (0/1) "))
                obj_gain = float(input("Objectif gain ? "))
                ID_client = int(input("Quel est l'ID du client ? "))
                devise_1 = input("Devise 1 ? ")
                devise_2 = input("Devise 2 ? ")
                sql.configure_new_symbol(symbol,
                                         devise_1,
                                         devise_2,
                                         percent_down,
                                         percent_local,
                                         percent_up,
                                         ID_client,
                                         percent_factu,
                                         percent_epargne,
                                         dev_entiere,
                                         obj_gain)
                sql.set_ecart_bet(CSV_file)

            print("init")
        elif a == "load_file":
            CSV_file = input("Quel est le nom du fichier CSV ? ")
            sql.set_ecart_bet(CSV_file)
        else:
            print("pas init")


if __name__ == '__main__':
     main()
