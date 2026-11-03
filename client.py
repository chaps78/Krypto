import time
import sys

from bininterface import binAcces
from sqlInterface import sqlAcces
from KPI import Kpi
from telegramInterface import teleAcces
from sheetInterface import sheetAcces

class Clients():
    def __init__(self):
        self.sql = sqlAcces()
        self.bin = binAcces()


    def display_wallet(self,client):
        wallet = self.bin.get_wallet(client)
        for el in wallet:
            print(el)
    
    def market_order(self,client):
        symbol = input("select pair\n")
        montant = input("amount\n")
        sens = input("BUY/SELL\n")
        
        self.bin.new_market_order(symbol,montant,sens,client)

    def limit_order(self,client):
        symbol = input("select pair\n")
        montant = input("amount\n")
        sens = input("BUY/SELL\n")
        limit = input("limit\n")
        
        self.bin.new_manual_limite_order(symbol,montant,limit,sens,0,client)
    
    def list_orders(self,ID_client,symbol):
        symbol_splited = symbol.split("_")[0]
        orders = self.bin.clients[ID_client].get_all_orders(symbol=symbol_splited)
        print("#########################################################################################")
        for order in orders:
            if order['status'] == "NEW" or order['status'] == "PARTIAL":
                print("# ID : " + str(order["orderId"]) + "\tSide : " + order["side"] + "\tLimite : " 
                      + str(order['price']) + "\tAmount : " + str(order['origQty']))
                
    def list_orders_for_dashboard(self,ID_client,symbol):
        symbol_splited = symbol.split("_")[0]
        orders = self.bin.clients[ID_client].get_all_orders(symbol=symbol_splited)
        new_db_orders = self.sql.get_orders_status_symbol_filter("NEW",symbol,ID_client)
        print("#########################################################################################")
        for order in orders:
            if order['status'] == "NEW" or order['status'] == "PARTIAL":
                for ordre_db in new_db_orders:
                    if order["orderId"] == ordre_db["ID"]:
                        print("# ID : " + str(order["orderId"]) + "\tSide : " + order["side"] + "\tLimite : " 
                            + str(order['price']) + "\tAmount : " + str(order['origQty']))
                
    def cancel_order(self,ID_client,symbol):
        self.list_orders(ID_client,symbol)
        ID = input("Select the ID of order you whant to cancel : ")
        self.bin.cancel_order(ID,ID_client)
        
    def dashboard_client(self,ID_client):
        wallet = self.bin.get_wallet(ID_client)
        devises = self.sql.get_symbols_actif_client(ID_client)
        devises_info = self.sql.get_devises_from_Clien_ID(ID_client)
        print("\n#########################################################################################")
        print("#\t\t\t\t\tWallet\t\t\t\t\t\t#")
        print("#########################################################################################")
        sum_usdt = 0.0
        for crypto in wallet:
            total = float(crypto["free"])+float(crypto["locked"])
            print("# "+crypto["asset"]+ "\t: Free : "+ crypto["free"]+"\tlock : "+crypto["locked"]+ "\tTotal : "+str(total))
            if crypto["asset"] != "USDT":
                taux = self.bin.get_price(crypto["asset"]+"USDT",ID_client)
                try:
                    US_price = total*float(taux["price"])
                    sum_usdt += US_price
                    print("#\t USDT : "+str(US_price))
                except:
                    print("#\tNO USDT Price ")
            else:
                sum_usdt += total
        us_eur_taux = self.bin.get_price("EURUSDT",ID_client)
        sum_eur = sum_usdt/float(us_eur_taux["price"])
        print("\n#########################################################################################")
        print("#\t\t total USDT : "+str(sum_usdt)+"\t\t\t\t\t\t#")
        print("#\t\t total EUR : "+str(sum_eur)+"\t\t\t\t\t\t#")
        for devise in devises:
            print("#########################################################################################")
            print("#\t\t\t\t\t"+ devise+ "\t\t\t\t\t#")
            self.list_orders_for_dashboard(ID_client,devise)
            print("#\t\t\tPERCENTS %\t\t")
            print("# Down : " + str(devises_info[devise]["down"]) 
                  + "\tLocal : " + str(devises_info[devise]["local"])
                  + "\tUP : "+ str(devises_info[devise]["up"])
                  + "\tEpargne : "+ str(devises_info[devise]["epargne_prcent"])
                  + "\tFactu : "+ str(devises_info[devise]["factu_percent"]))
            print("#\t\t\t\t\tRepartition\t\t\t\t\t#")
            print("# Gain total : " + str('%.3f' % devises_info[devise]["benef_all"])
                  + "\tEpargne : " + str('%.3f' % devises_info[devise]["epargne"])
                  + "\tFacturation : " + str('%.3f' % devises_info[devise]["factu"])
                  )
        print("#########################################################################################")


def main():
    Client = Clients()
    clients_liste = Client.sql.get_clients_infos()
    if len(sys.argv) == 2:
        a = sys.argv[1]
        if a == "new_client":
            nom = input("Nom du client : ")
            API_Key = input("API_Key : ")
            secret = input("secret : ")
            telegram = input("telegram chat ID : ")
            base = input("Devise de base de l'utilisateur : ")
            Client.sql.new_client(nom,API_Key,secret,base,telegram)

        else:
            print("argument non reconnu \n new_client")
    else:
            
        print("Select a client:")
        for client in clients_liste:
            print(str(client)+" - "+ str(clients_liste[client]["name"]))
        client = int(input("Enter your choice : "))
        print("\n\t#######################\n")

        print("What action do you whant to do?")
        print("1 - Display Wallet\n2 - Market order\n3 - Open orders list\n4 - New limit order\n5 - Cancel order\n6 - Dashboard")
        action_selected = input("Enter your choice : ")
        if action_selected == "1":
            Client.display_wallet(client)

        elif action_selected == "2":
            Client.market_order(client)
        elif action_selected == "3":
            symbol = input("Whith symbol : ")
            Client.list_orders(client,symbol)
        elif action_selected == "4":
            Client.limit_order(client)
        elif action_selected == "5":
            symbol = input("Whith symbol : ")
            Client.cancel_order(client,symbol)
        elif action_selected == "6":

            Client.dashboard_client(client)




if __name__ == '__main__':
     main()