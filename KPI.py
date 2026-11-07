from bininterface import binAcces
from sqlInterface import sqlAcces
from datetime import datetime


class Kpi():

    def __init__(self):
        """Instancie les accès Binance et SQL."""
        self.bin = binAcces()
        self.sql = sqlAcces()

    def stat_mois(self,symbol,annee,mois):
        """Affiche, pour un mois, le nombre d'exécutions par palier et par niveau.

        Parcourt les paliers entre le plus bas achat et la plus haute vente du mois.
        """
        min=self.sql.min_buy(symbol,annee,mois)
        max=self.sql.max_sell(symbol,annee,mois)
        result={}
        while min<max:
            result_inter={}
            result_inter["BUY"]=self.sql.count_buy_ID_ecart(symbol,annee,mois,min)
            result_inter["SELL"]=self.sql.count_sell_ID_ecart(symbol,annee,mois,min)
            result[min]=result_inter
            min+=1
        keys = result.keys()
        for key in keys:
            print(str(key)+":BUY:"
                  +str(result[key]["BUY"][0])
                  +":"+str(result[key]["BUY"][1])
                  +":"+str(result[key]["BUY"][2])
                  +":SELL:"
                  +str(result[key]["SELL"][0])
                  +":"+str(result[key]["SELL"][1])
                  +":"+str(result[key]["SELL"][2]))
            

    def gain_month_global(self,year,month,ID_client):
        """Affiche et renvoie le gain d'un mois pour toutes les stratégies d'un client.

        Les gains sont convertis dans la devise de base du client.

        Returns:
            float : total du mois.
        """
        print("\n\n#########################################################")
        print("#              KPI YEAR "+str(year) + " MONTH "+str(month)+ "\t                #")
        print("#########################################################")
        symbols = self.sql.get_symbols_client(ID_client)
        base_client = self.sql.get_clients_infos()[ID_client]["base"]
        total=0
        for symbol in symbols:
            resultat = self.sql.get_gain_mois(symbol,year,month)
            if resultat != None:
                devise_info = self.sql.get_devises_from_symbol(symbol,ID_client)
                if devise_info["devise2"] == base_client:
                    print("#\t" + symbol +" : \t\t## \t"+str(round(resultat,2))+" "+base_client+"  \t#")
                    total += resultat
                else:
                    Price = float(self.bin.get_price(devise_info["devise2"]+base_client,ID_client)["price"])
                    print("#\t"+symbol +" : "+ str(round(resultat,2))
                          + " " + devise_info["devise2"] 
                          + "\t## \t"+str(round(resultat*Price,2))+" "+base_client+"  \t#")
                    total+=resultat*Price
        print("#########################################################")
        print("#\t\t\tTOTAL : "+ str(round(total,2))+ "\t\t\t#")
        print("#########################################################")
        return total

###########################################################################
#                                 MAIN                                    #
###########################################################################
def main():
    """Outil en ligne de commande.

        python3 KPI.py       menu : gain mensuel ou statistiques par palier
    """
    kpi = Kpi()
    sql = sqlAcces()
    print("Select a client:")
    clients_liste = sql.get_clients_infos()
    for client in clients_liste:
        print(str(client)+" - "+ str(clients_liste[client]["name"]))
    ID_client = int(input("Enter your choice : "))
    print("1-Gain du mois\n2-Recap de la quantitée d'ordres")
    choice = input("Enter your choice [1-2]: ")
    if choice == '1':
        current_month = datetime.now().month
        current_year = datetime.now().year
        nbr_mois = int(input("combien de mois de rétro: "))
        somme = 0
        kpi.gain_month_global(2025,11,ID_client)
        kpi.gain_month_global(2025,12,ID_client)
        for i in range(nbr_mois):
            if current_month-i<0:
                current_year -=1
                current_month +=12
                
            somme += kpi.gain_month_global(current_year,current_month-(nbr_mois-i-1),ID_client)
        print("Total des "+str(nbr_mois)+" derniers mois: "+str(somme))
        print("Moyenne sur les "+str(nbr_mois)+" derniers mois: "+str(somme/nbr_mois))

    symbols = sql.get_symbols()
    if choice == '2':
        print("sur quelle paire?")
        for el in symbols:
            print(str(symbols.index(el))+"-"+el)
        choice2 = input("?")

        print("\n"+str(symbols[int(choice2)])+":\n")
        current_month = datetime.now().month

        back_month = input("combien de mois en arrière ? : ")
        kpi.stat_mois(symbols[int(choice2)],2024,current_month-int(back_month))


if __name__ == '__main__':
     main()
