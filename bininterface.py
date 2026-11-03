from binance.client import Client
import json
from datetime import datetime, timezone
import time

from sqlInterface import sqlAcces

class binAcces():
    def __init__(self):
        self.sql = sqlAcces()
        clients_infos = self.sql.get_clients_infos()
        with open('bin_key.json') as json_file:
            config = json.load(json_file)
        self.client = Client(config["api"], config["secret"])
        self.clients={}
        for key in clients_infos.keys():
            self.clients[key]=Client(clients_infos[key]["api"], clients_infos[key]["secret"])

    def LDPEPE(self,ID_client):
        print("DLPEPE")
        #self.clients[ID_client].
        self.clients[ID_client].transfer_spot_to_margin(asset="PEPE",amount="10000")

    def new_limite_order(self,symbol,montant,limite,sens,ID_ecart,flag_ajout,ID_client,niveau=1):
        try:
            UP = 0
            if sens == self.client.SIDE_BUY and (niveau==1 or niveau == 2):
                ecart_bet = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart)
                UP = int(ecart_bet[4])
                if int(UP) >0:
                    montant += UP
                    self.sql.tele.send_message("Un ordre ouvert avec un ajout pour le UP d'un montant de : "+str(UP))


            infos_devise = self.sql.get_devises_from_symbol(symbol,ID_client)
            ajout_qtt = infos_devise["local"]
            benef = self.sql.calcul_benef_with_ID(symbol,ID_ecart,limite,montant)
            benef_ratio = benef/limite
            try:
                if sens == self.client.SIDE_SELL and (niveau==1 or niveau == 2) and benef_ratio < ajout_qtt and symbol=="XRPEUR":
                    montant += ajout_qtt
            except TypeError:
                print("ON PASSE DANS UNE ERREUR MAIS CA DOIT ETRE PLUS OU MOINS CONTROLE")

            if self.sql.get_dev_entiere(symbol):
                montant = int(montant)
            symbol_plited = symbol.split("_")[0]
            montant_call='%.8f' % montant
            if symbol_plited == "PEPEEUR":
                montant_call='%.0f' % montant
            elif symbol_plited == "BTCUSDT" or symbol_plited == "BTCEUR" or symbol_plited == "BTCUSDC":
                montant_call='%.5f' % montant
                montant_tmp = int(montant * 10 ** 5)/10 ** 5
                montant_call='%.5f' % montant_tmp
            elif symbol_plited == "ETHUSDT" or symbol_plited == "ETHEUR":
                montant_tmp = int(montant * 10 ** 4)/10 ** 4
                montant_call='%.4f' % montant_tmp
            elif symbol_plited == "XRPBNB":
                montant_tmp = int(montant * 10 ** 1)/10 ** 1
                montant_call='%.1f' % montant_tmp
            elif symbol_plited == "EURUSDT":
                montant_tmp = int(montant * 10 ** 1)/10 ** 1
                montant_call='%.1f' % montant_tmp
                limite = int(limite * 10 ** 4)/10 ** 4
                limite = float('%.4f' % limite)
            response = self.clients[ID_client].create_order(symbol=symbol_plited, 
                                            side=sens, 
                                            type=Client.ORDER_TYPE_LIMIT, 
                                            quantity=montant_call, 
                                            price='%.8f' % limite,
                                            timeInForce='GTC')
        except Exception as inst:
            self.sql.new_log_error("new_limite_order_Binance",str(inst),symbol)
            return ""
        
        self.sql.new_order(response["orderId"],symbol,montant_call,limite,response["status"],datetime.now(timezone.utc),"",0,Client.ORDER_TYPE_LIMIT,sens,ID_ecart,UP,ID_client,niveau)
        return response["orderId"]
    

    def new_manual_limite_order(self,symbol,montant,limite,sens,flag_ajout,ID_client,niveau=1):
        try:
            print("Debut fonction 1")
            if self.sql.get_dev_entiere(symbol):
                montant = int(montant)
            print("On est passé dans le IF")
            montant_call='%.8f' % float(montant)
            print("on est passé dans Montant call")
            symbol_plited = symbol.split("_")[0]
            print("Symbol :" + str(type(symbol_plited))+ " : "+ str(symbol_plited))
            if symbol_plited == "PEPEEUR":
                montant_call='%.0f' % int(montant)
            elif symbol_plited == "BTCUSDT" or symbol_plited == "BTCEUR" or symbol_plited == "BTCUSDC":
                print("on passe dans le if "+ symbol_plited)
                montant_tmp = int(float(montant) * 10 ** 5)/10 ** 5
                montant_call='%.5f' % montant_tmp
            elif symbol_plited == "ETHUSDT" or symbol_plited == "ETHEUR":
                montant_tmp = int(montant * 10 ** 4)/10 ** 4
                montant_call='%.4f' % montant_tmp
            elif symbol_plited == "XRPBNB":
                montant_tmp = int(montant * 10 ** 1)/10 ** 1
                montant_call='%.1f' % montant_tmp
            elif symbol_plited == "EURUSDT":
                montant_tmp = int(montant * 10 ** 1)/10 ** 1
                montant_call='%.1f' % montant_tmp
                limite = int(limite * 10 ** 4)/10 ** 4
                limite = float('%.4f' % limite)
            
            print("Avant l ordre")
            response = self.clients[ID_client].create_order(symbol=symbol_plited, 
                                            side=sens, 
                                            type=Client.ORDER_TYPE_LIMIT, 
                                            quantity=montant_call, 
                                            price=limite,
                                            timeInForce='GTC')
            print("Apres l ordre")
            print(str(response))
        except Exception as inst:
            self.sql.new_log_error("new_manual_limite_order",str(inst),symbol)
            return ""
        
        self.sql.new_order(response["orderId"],symbol,montant_call,limite,"MANUAL_LIMIT",datetime.now(timezone.utc),"",0,Client.ORDER_TYPE_LIMIT,sens,None,0,ID_client,niveau)
        return response["orderId"]
    

    ###############################
    #donner l ID du dernier FILLED (clos)
    ###############################
    def new_achat(self,symbol,ID_ecart,ID_client,flag_ajout=0):
        last_ordre = self.sql.get_last_filled(symbol,ID_client)
        
        if last_ordre != "":
            if last_ordre["sens"]== Client.SIDE_SELL:
                bet_ecart = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart-1)
                self.sql.new_log_debug("ouverture Achat limite apres une vente",
                                    "montant: "
                                    +str(bet_ecart[3])
                                    +"limite: "+str(bet_ecart[2]),
                                    symbol)
                self.new_limite_order(symbol,
                                    bet_ecart[3],
                                    bet_ecart[2],
                                    Client.SIDE_BUY,
                                    ID_ecart-1,
                                    flag_ajout,
                                    ID_client)
            else:
                if int(last_ordre["niveau"])==1:
                    bet_ecart = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart-1)
                    self.sql.new_log_debug("ouverture Achat limite apres niveau 1 vers 2",
                                    "montant: "
                                    +str(bet_ecart[3])
                                    +"limite: "+str(bet_ecart[2]),
                                    symbol)
                    self.new_limite_order(symbol,
                                        bet_ecart[3],
                                        bet_ecart[2],
                                        Client.SIDE_BUY,
                                        ID_ecart-1,
                                        flag_ajout,
                                        ID_client,
                                        2)
                
                elif int(last_ordre["niveau"])==2:
                    bet_ecart_1 = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart-1)
                    bet_ecart_2 = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart-2)
                    self.sql.new_log_debug("ouverture Achat limite apres niveau 2 vers 3",
                                    "montant: "
                                    +str(bet_ecart_1[3]+bet_ecart_2[3])
                                    +"limite: "+str(bet_ecart_2[2]),
                                    symbol)
                    self.new_limite_order(symbol,
                                        bet_ecart_1[3]+bet_ecart_2[3],
                                        bet_ecart_2[2],
                                        Client.SIDE_BUY,
                                        ID_ecart-2,
                                        flag_ajout,
                                        ID_client,
                                        3)
                else:
                    bet_ecart_1 = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart-1)
                    bet_ecart_2 = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart-2)
                    bet_ecart_3 = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart-3)
                    self.sql.new_log_debug("ouverture Achat limite apres niveau 3 vers 4",
                                    "montant: "
                                    +str(bet_ecart_1[3]+bet_ecart_2[3]+bet_ecart_3[3])
                                    +"limite: "+str(bet_ecart_3[2]),
                                    symbol)
                    self.new_limite_order(symbol,
                                        bet_ecart_1[3]+bet_ecart_2[3]+bet_ecart_3[3],
                                        bet_ecart_3[2],
                                        Client.SIDE_BUY,
                                        ID_ecart-3,
                                        flag_ajout,
                                        ID_client,
                                        4)
        else:
            bet_ecart = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart-1)
            self.sql.new_log_debug("ouverture Achat limite apres une vente",
                                "montant: "
                                +str(bet_ecart[3])
                                +"limite: "+str(bet_ecart[2]),
                                symbol)
            self.new_limite_order(symbol,
                                bet_ecart[3],
                                bet_ecart[2],
                                Client.SIDE_BUY,
                                ID_ecart-1,
                                flag_ajout,
                                ID_client)


    ###############################
    #donner l ID du dernier FILLED (clos)
    ###############################
    def new_vente(self,symbol,ID_ecart,ID_client,flag_ajout=0):
        last_ordre = self.sql.get_last_filled(symbol,ID_client)
        if last_ordre != "":
            if last_ordre["sens"]== Client.SIDE_BUY:
                bet_ecart_limite = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart+1)
                bet_ecart_montant = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart)
                self.sql.new_log_debug("ouverture Vente limite apres un achat",
                                    "montant: "
                                    +str(bet_ecart_montant[3])
                                    +"limite: "+str(bet_ecart_limite[2]),
                                    symbol)
                self.new_limite_order(symbol,
                                    bet_ecart_montant[3],
                                    bet_ecart_limite[2],
                                    Client.SIDE_SELL,
                                    ID_ecart+1,
                                    flag_ajout,
                                    ID_client)
            else:
                if int(last_ordre["niveau"])==1:
                    bet_ecart_limite = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart+1)
                    bet_ecart_montant = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart)
                    self.sql.new_log_debug("ouverture Vente limite passage niv 1 vers 2",
                                    "montant: "
                                    +str(bet_ecart_montant[3])
                                    +"limite: "+str(bet_ecart_limite[2]),
                                    symbol)
                    self.new_limite_order(symbol,
                                        bet_ecart_montant[3],
                                        bet_ecart_limite[2],
                                        Client.SIDE_SELL,
                                        ID_ecart+1,
                                        flag_ajout,
                                        ID_client,
                                        2)
                elif int(last_ordre["niveau"])==2:
                    bet_ecart_limite = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart+2)
                    bet_ecart_montant = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart)
                    bet_ecart_montant_2 = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart+1)
                    self.new_limite_order(symbol,
                                        bet_ecart_montant[3]+bet_ecart_montant_2[3],
                                        bet_ecart_limite[2],
                                        Client.SIDE_SELL,
                                        ID_ecart+2,
                                        flag_ajout,
                                        ID_client,
                                        3)
                else:
                    bet_ecart_limite = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart+3)
                    bet_ecart_montant = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart)
                    bet_ecart_montant_2 = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart+1)
                    bet_ecart_montant_3 = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart+2)
                    self.new_limite_order(symbol,
                                        bet_ecart_montant[3]+bet_ecart_montant_2[3]+bet_ecart_montant_3[3],
                                        bet_ecart_limite[2],
                                        Client.SIDE_SELL,
                                        ID_ecart+3,
                                        flag_ajout,
                                        ID_client,
                                        4)
        else:
            bet_ecart_limite = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart+1)
            bet_ecart_montant = self.sql.get_ecart_bet_from_symbol_and_ID(symbol,ID_ecart)
            self.sql.new_log_debug("ouverture Vente limite apres un achat",
                                "montant: "
                                +str(bet_ecart_montant[3])
                                +"limite: "+str(bet_ecart_limite[2]),
                                symbol)
            self.new_limite_order(symbol,
                                bet_ecart_montant[3],
                                bet_ecart_limite[2],
                                Client.SIDE_SELL,
                                ID_ecart+1,
                                flag_ajout,
                                ID_client)


    def new_market_order(self,symbol,montant,sens,ID_client):

        try:
            symbol_splited = symbol.split("_")[0]
            if symbol_splited == "PEPEEUR":
                montant_call='%.0f' % int(montant)
            else:
                montant_call = montant
            response = self.clients[ID_client].create_order(symbol=symbol_splited, 
                                        side=sens, 
                                        type=Client.ORDER_TYPE_MARKET, 
                                        quantity=montant_call)
        except Exception as inst:
            self.sql.new_log_error("new_market_order_Binance",str(inst),symbol)
            return ""
        
        self.sql.new_order(response["orderId"],symbol,montant,"",response["status"],datetime.now(timezone.utc),"",0,Client.ORDER_TYPE_MARKET,sens,0,0,ID_client)
        return response["orderId"]
    
    def get_order_info_with_ID(self,symbol,ID_client,ID_partial,ID_market,ID_limit):
        symbol_splited = symbol.split("_")[0]
        orders_Binance = self.clients[ID_client].get_all_orders(symbol=symbol_splited)
        retour = {}
        for ob in orders_Binance:
            if ob["orderId"] == int(ID_partial):
                retour["PARTIAL"] = ob
            if ob["orderId"] == int(ID_market):
                retour["MARKET"] = ob
            if ob["orderId"] == int(ID_limit):
                retour["FILLED"] = ob

        return retour

    
    def calcul_benef_partial(self,symbol,ID_client,ID_partial,ID_market):
        FEE=0.00075
        orders_info = self.get_order_info_with_ID(symbol,ID_client,ID_partial,ID_market,0)
        order_market = orders_info["MARKET"]
        order_partial = orders_info["PARTIAL"]
        benefice_sans_fee = abs(float(order_market["cummulativeQuoteQty"])-float(order_partial["cummulativeQuoteQty"]))
        current_fee = float(order_market["cummulativeQuoteQty"])*FEE + float(order_partial["cummulativeQuoteQty"])*FEE
        benefice = benefice_sans_fee-current_fee
        self.sql.update_order_benef(str(order_partial["orderId"]),str(benefice),symbol)


        

    def cancel_order(self,ID,ID_client):
        try:
            try:
                symbol = self.sql.get_order_info_by_ID(ID)["symbol"]
                
            except:
                symbol = input("Rappel symbol SVP : ")
            symbol_split = symbol.split("_")[0]
            ordre = self.clients[ID_client].cancel_order(symbol=symbol_split,orderId=int(ID))
        except Exception as inst:
            self.sql.new_log_error("cancel_order_Binance",str(inst),symbol)
            return ""
        self.sql.update_order(ID,ordre["status"],datetime.now(timezone.utc),ordre["executedQty"])
        retour = [ordre["status"],ordre["executedQty"]]
        return retour

    def cancel_order_partial(self,ID,ID_client):
        try:
            symbol = self.sql.get_order_info_by_ID(ID)["symbol"]
            symbol_split = symbol.split("_")[0]
            ordre = self.clients[ID_client].cancel_order(symbol=symbol_split,orderId=int(ID))
        except Exception as inst:
            self.sql.new_log_error("cancel_order_Binance",str(inst),symbol)
            return ""
        self.sql.update_order(ID,"PARTIAL",datetime.now(timezone.utc),ordre["executedQty"])
        retour = ["PARTIAL",ordre["executedQty"]]
        return retour
    
    #######################################
    #  Regarde les differences entre des ordres donnes et ce qu il y a sur binance
    #  Renvoi les differences
    #######################################
    def changement_status(self,symbol,ID_client):
        try:
            ordres_new = self.sql.get_orders_status_symbol_filter(self.client.ORDER_STATUS_NEW,symbol,ID_client)
            ordres_partial = self.sql.get_orders_status_symbol_filter(self.client.ORDER_STATUS_PARTIALLY_FILLED,symbol,ID_client)
            ordres_DB = ordres_partial + ordres_new
            symbol_splited = symbol.split("_")[0]
            orders_Binance = self.clients[ID_client].get_all_orders(symbol=symbol_splited)
            change = []
            for ob in orders_Binance:
                ordre = self.sql.get_order_info_by_ID(ob["orderId"])

                for odb in ordres_DB:
                    if ob["orderId"] == odb["ID"]:
                        if ob["status"] != odb["status"]:
                            change.append({"orderId":ob["orderId"],"status":ob["status"],"executedQty":ob["executedQty"]})
                            if odb["flag_ajout"] > 0:
                                self.sql.tele.send_message("un ordre avec UP a ete execute")
                                self.sql.set_up_bet(symbol,odb["ID_ecart"],0)
                                ID_to_UP = self.sql.get_ID_to_UP(symbol,odb["ID_ecart"],ID_client)
                                self.sql.add_to_ajout(symbol,ID_to_UP,odb["flag_ajout"])
                                self.sql.add_to_ecart(symbol,ID_to_UP,odb["flag_ajout"])

                                #mettre UP dans ecart _ bet à 0
                                #ajouter le UP dans le graph

        except Exception as inst:
            self.sql.new_log_error("changement_status_Binance",str(inst),symbol)
            time.sleep(60)
            change = []
        return change
    
    ####################################
    #Met a jour la DB a partir d une liste en input
    ####################################
    def changement_update(self,liste_ordres,symbol,ID_client):
        try:
            for ordre in liste_ordres:
                self.sql.update_order(ordre["orderId"],ordre["status"],datetime.now(timezone.utc),ordre["executedQty"])
        except Exception as inst:
            self.sql.new_log_error("changement_update_Binance",str(inst),symbol)
    
    #####################################
    # input liste des devises dont on souhaite avoir le solde
    #ex : ["EUR","DOGE","BTC"]
    #####################################
    #####################################
    # input liste des devises dont on souhaite avoir le solde
    #ex : ["EUR","DOGE","BTC"]
    #####################################
    def get_wallet(self,ID_client):
        try:
            wallet=[]
            info = self.clients[ID_client].get_account()
            for el in info["balances"]:
                if float(el["free"]) > 0:
                    wallet.append(el)
        except Exception as inst:
            self.sql.new_log_error("get_found_Binance",str(inst),"NA")
            retour = ["ERROR"]
        return wallet
    
    
    def get_price(self,symbol,ID_client):
        try:
            symbol_split = symbol.split("_")[0]
            result = self.clients[ID_client].get_symbol_ticker(symbol=symbol_split)
        except Exception as inst:
            self.sql.new_log_error("get_price_Binance",str(inst),symbol)
            return "ERROR"
        return result
    
    def baisser_niveau_ordre(self,ID_ordre,ID_client):
        ordre = self.sql.get_order_info_by_ID(ID_ordre)
        if ordre["sens"] == self.client.SIDE_BUY:
            self.baisse_niveau_achat(ordre,ID_client)
        if ordre["sens"] == self.client.SIDE_SELL:
            self.baisse_niveau_vente(ordre,ID_client)
    
    def baisse_niveau_achat(self,ordre,ID_client):
        if ordre["niveau"] == 4:
            self.cancel_order(ordre["ID"],ID_client)
            bet_ecart_1 = self.sql.get_ecart_bet_from_symbol_and_ID(ordre["symbol"],int(ordre["ID_ecart"])+1)
            bet_ecart_2 = self.sql.get_ecart_bet_from_symbol_and_ID(ordre["symbol"],int(ordre["ID_ecart"])+2)
            self.new_limite_order(ordre["symbol"],
                                  float(bet_ecart_1[3])+float(bet_ecart_2[3]),
                                  float(bet_ecart_1[2]),
                                  ordre["sens"],
                                  int(ordre["ID_ecart"])+1,
                                  ordre["flag_ajout"],
                                  ID_client,
                                  3)
        elif ordre["niveau"] == 3:
            self.cancel_order(ordre["ID"],ID_client)
            bet_ecart_1 = self.sql.get_ecart_bet_from_symbol_and_ID(ordre["symbol"],int(ordre["ID_ecart"])+1)
            self.new_limite_order(ordre["symbol"],
                                  float(bet_ecart_1[3]),
                                  float(bet_ecart_1[2]),
                                  ordre["sens"],
                                  int(ordre["ID_ecart"])+1,
                                  ordre["flag_ajout"],
                                  ID_client,
                                  1)

    def baisse_niveau_vente(self,ordre,ID_client):
        if ordre["niveau"] == 4:
            self.cancel_order(ordre["ID"],ID_client)
            bet_ecart_limite = self.sql.get_ecart_bet_from_symbol_and_ID(ordre["symbol"],int(ordre["ID_ecart"])-1)
            bet_ecart_montant = self.sql.get_ecart_bet_from_symbol_and_ID(ordre["symbol"],int(ordre["ID_ecart"])-3)
            bet_ecart_montant_2 = self.sql.get_ecart_bet_from_symbol_and_ID(ordre["symbol"],int(ordre["ID_ecart"])-2)
            self.new_limite_order(ordre["symbol"],
                                      bet_ecart_montant[3]+bet_ecart_montant_2[3],
                                      bet_ecart_limite[2],
                                      ordre["sens"],
                                      int(ordre["ID_ecart"])-1,
                                      ordre["flag_ajout"],
                                      ID_client,
                                      3)
        elif ordre["niveau"] == 3:
            self.cancel_order(ordre["ID"],ID_client)
            bet_ecart_limite = self.sql.get_ecart_bet_from_symbol_and_ID(ordre["symbol"],int(ordre["ID_ecart"])-1)
            bet_ecart_montant = self.sql.get_ecart_bet_from_symbol_and_ID(ordre["symbol"],int(ordre["ID_ecart"])-2)
            self.new_limite_order(ordre["symbol"],
                                      bet_ecart_montant[3],
                                      bet_ecart_limite[2],
                                      ordre["sens"],
                                      int(ordre["ID_ecart"])-1,
                                      ordre["flag_ajout"],
                                      ID_client,
                                      1)


def main():    
    bin = binAcces()


    bin.LDPEPE(1)
    
    


if __name__ == '__main__':
     main()
