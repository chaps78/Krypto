import sys

from bininterface import binAcces
from sqlInterface import sqlAcces

class Clients():
    def __init__(self):
        """Instancie les accès SQL et Binance."""
        self.sql = sqlAcces()
        self.bin = binAcces()


    def display_wallet(self,client):
        """Affiche les soldes non nuls d'un compte."""
        wallet = self.bin.get_wallet(client)
        for el in wallet:
            print(el)
    
    def market_order(self,client):
        """Demande paire, quantité et sens, puis passe un ordre au marché."""
        symbol = input("select pair\n")
        montant = input("amount\n")
        sens = input("BUY/SELL\n")
        
        self.bin.new_market_order(symbol,montant,sens,client)

    def limit_order(self,client):
        """Demande paire, quantité, sens et prix, puis passe un ordre limite manuel."""
        symbol = input("select pair\n")
        montant = input("amount\n")
        sens = input("BUY/SELL\n")
        limit = input("limit\n")
        
        self.bin.new_manual_limite_order(symbol,montant,limit,sens,0,client)
    
    def list_orders(self,ID_client,symbol):
        """Affiche les ordres ouverts sur Binance pour une paire."""
        symbol_splited = symbol.split("_")[0]
        orders = self.bin.clients[ID_client].get_all_orders(symbol=symbol_splited)
        print("#########################################################################################")
        for order in orders:
            if order['status'] == "NEW" or order['status'] == "PARTIAL":
                print("# ID : " + str(order["orderId"]) + "\tSide : " + order["side"] + "\tLimite : " 
                      + str(order['price']) + "\tAmount : " + str(order['origQty']))
                
    def cancel_order(self,ID_client,symbol):
        """Affiche les ordres ouverts d'une paire puis annule celui choisi."""
        self.list_orders(ID_client,symbol)
        ID = input("Select the ID of order you whant to cancel : ")
        self.bin.cancel_order(ID,ID_client)
        
def main():
    """Outil en ligne de commande.

        python3 client.py             menu : wallet, ordres, annulation
        python3 client.py new_client  ajoute un compte client
    """
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
        print("1 - Display Wallet\n2 - Market order\n3 - Open orders list\n4 - New limit order\n5 - Cancel order")
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




if __name__ == '__main__':
     main()