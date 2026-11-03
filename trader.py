import time

from bininterface import binAcces
from sqlInterface import sqlAcces
from telegramInterface import teleAcces
from sheetInterface import sheetAcces



class Basics():

    def __init__(self):
        self.sql = sqlAcces()
        self.bin = binAcces()
        self.tele = teleAcces()
        self.sheet = sheetAcces()

    def plus_proche(self,symbol,ID_client):
        ecart_bet_dic = self.sql.get_ecart_bet_from_symbol(symbol)
        prix_tmp = self.bin.get_price(symbol,ID_client)
        prix = prix_tmp["price"]
        breakpoint()
        delta = abs(float(ecart_bet_dic[0][1])-float(prix))
        prix_proche_ID=0
        keys = ecart_bet_dic.keys()
        for key in keys:
            if abs(float(prix)-float(ecart_bet_dic[key][0]))<delta:
                delta = abs(float(prix)-float(ecart_bet_dic[key][0]))
                prix_proche_ID = key
        return prix_proche_ID

    def initialise(self,symbol,ID_client):
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

    def verification_2_ordres_V2(self,symbol,ID_client):
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
                        breakpoint()
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
                    self.sheet.update_all_info(symbol)
                    # un ordre ferme et un NEW
                elif len(ordres_partial) == 1:
                    self.tele.send_message("nouvel ordre avec un partial FILLED")
                    self.sql.new_log_debug("verification_2_ordres_V2","un ordre FILLED et un PARTIALY : "+str(ordres_DB),symbol)
                    self.un_ordre_filled_autre_partial(ordres_partial,symbol,ID_client)
                    # un ordre ferme et l autre partialy FILLED
            elif len(ordres_DB) == 0 :
                self.tele.send_message("deux ordres clos en meme temps "+symbol)
                self.sql.new_log_debug("verification_2_ordres_V2","deux ordres FILLED : "+str(ordres_DB),symbol)
                self.tele.send_message("sql OK")
                self.deux_ordres_filled(symbol,ID_client)
                #Deux ordres ont ete fermes
            elif len(ordres_DB) > 2 :
                self.sql.new_log_error("verification_2_ordres_V2_trader","probleme de trade", symbol)
        except Exception as inst:
            self.sql.new_log_debug("Ordres V2",str(inst),symbol)
            return inst

    def get_taux_reinjection(self, benef):
        paliers = [
            (5, 1000),
            (10, 500),
            (15, 300),
            (25, 200),
            (40, 150),
            (60, 100),
        ]
        for seuil, taux in paliers:
            if benef < seuil:
                return taux
        return 50

    def get_taux_up(self, benef):
        paliers = [
            (10, 100),
            (15, 50),
            (25, 30),
            (40, 20),
            (60, 15),
        ]
        for seuil, taux in paliers:
            if benef < seuil:
                return taux
        return 10
    
        
    def reinject_benef(self,symbol,ID_client,last_filled):
        benef_tmp = self.sql.get_benef_TMP_and_benef_all_from_symbol(symbol)["TMP"]
        if benef_tmp>0:
            try:
                debug_flag = 0
                repart = self.sql.get_reinject_repartition(symbol)
                debug_flag = 1
                self.tele.send_message("Je passe dans le reinject function")
                if type(repart["local"])==str:
                    self.tele.send_message("Je passe dans le cas du STR a la place du pourcent repart : "+str(last_filled["benefice"]))
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
            self.tele.send_message("Reinject UP "+symbol +str(total)+"\n ID "+str(ID_client))
            if int(dev_entier) == 1:
                self.bin.new_market_order(symbol,int(total/taux_convert),"BUY",ID_client)
                self.sql.add_to_ecart(symbol,ID,int(total/taux_convert))
                self.sql.add_2_up_tmp(symbol,-int(total/taux_convert)*taux_convert)
            else:
                self.bin.new_market_order(symbol,total/taux_convert,"BUY",ID_client)
                self.sql.add_to_ecart(symbol,ID,total/taux_convert)
                self.sql.add_2_up_tmp(symbol,-total)
        


    def reinject_local(self,symbol,last_filled,qtt):
        current_bet = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,float(last_filled["ID_ecart"])-1)[3]
        prix = float(self.sql.get_ecart_bet_from_symbol_and_ID(symbol,int(last_filled["ID_ecart"])-1)[2])
        self.sql.update_bet_with_ID(symbol,int(last_filled["ID_ecart"])-1,float(current_bet)+qtt/prix)
        self.sql.add_to_ajout(symbol,int(last_filled["ID_ecart"])-1,qtt/prix)

    def un_ordre_filled_autre_new(self,ordres_ouvert,symbol,ID_client):
        for ordre_ouvert in ordres_ouvert:
            self.bin.cancel_order(ordre_ouvert["ID"],ID_client)
        last_filled_order = self.sql.get_last_filled(symbol,ID_client)
        self.sql.new_log_debug("Nouveaux ordres apres filled",str(last_filled_order),symbol)
        self.bin.new_achat(symbol,last_filled_order["ID_ecart"],ID_client)
        self.bin.new_vente(symbol,last_filled_order["ID_ecart"],ID_client)

    def un_ordre_filled_autre_partial(self,ordres_partiel,symbol,ID_client):
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
        niveaux = self.sql.get_time_since_open(symbol,ID_client)
        keys = niveaux.keys()
        for key in keys:
            #Delais d attente de 30 min pour un ordre niveau 4
            if int(niveaux[key]["niveau"]) == 4 and niveaux[key]["time"].seconds > 1800:
                self.bin.baisser_niveau_ordre(key,ID_client)
            # Delas d attente de 1 heures pour un ordre de niveau 3
            if int(niveaux[key]["niveau"]) == 3 and niveaux[key]["time"].seconds > 3600:
                self.bin.baisser_niveau_ordre(key,ID_client)
            # Delas d attente de 2 heures pour un ordre de niveau 2
            if int(niveaux[key]["niveau"]) == 2 and niveaux[key]["time"].seconds > 7200:
                self.sql.baisser_niveau_ordre_SQL(key,1)

###########################################################################
#                                 MAIN                                    #
###########################################################################
def main():
    basic = Basics()
    DEVISES=basic.sql.get_symbols_actif()

    basic.tele.send_message("Bonjour 1")
    # Pour demarrer une nouvelle paire, decommenter et adapter :
    #basic.initialise("SYMBOLE_SUFFIXE", ID_client)

    while True:
        for user_ID in DEVISES.keys():
            for DEVISE in DEVISES[user_ID]:
                basic.verification_2_ordres_V2(DEVISE,user_ID)
                basic.verification_niveau_VS_timer(DEVISE,user_ID)
                time.sleep(4)


if __name__ == '__main__':
     main()
