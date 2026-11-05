from bininterface import binAcces
from sqlInterface import sqlAcces
from datetime import datetime, timezone, timedelta
import sys


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

    def set_dashboard_info(self,symbol):
        """Enregistre le relevé du jour d'une stratégie dans Dashboard.

        Capital de la grille = paliers sous le prix (en devise de cotation) + crypto
        des paliers au-dessus valorisée au prix actuel. Enregistre aussi le prix, le
        gain de la veille, l'épargne, la facturation et up_TMP.
        """
        date = datetime.now(timezone.utc)
        ID_client = self.sql.get_ID_client_from_symbol(symbol)
        symbol_plited = symbol.split("_")[0]
        instant_price = float(self.bin.get_price(symbol_plited,ID_client)["price"])
        e_b = self.sql.get_ecart_bet_from_symbol(symbol)
        graph_capital = 0.0
        qtt_crypto = 0.0
        for el in e_b:
            if e_b[el][0]<instant_price:
                graph_capital += e_b[el][0]*e_b[el][1]
            else:
                qtt_crypto += e_b[el][1]
        graph_capital += qtt_crypto*instant_price
        devise = self.sql.get_devises_from_symbol(symbol,ID_client)

        #Recuperation des gains de la veille
        veille = datetime.now() - timedelta(days=1)
        day_gain = self.sql.get_gain_jour(symbol,veille.year,veille.month,veille.day)
        epargne = devise["epargne"]
        factu = devise["factu"]
        tmp_up = devise["UP_tmp"]
        self.sql.set_dashboard(symbol,date,graph_capital,instant_price,day_gain,epargne,factu,tmp_up)

    def get_dashboard_KPI(self,symbol):
        """Envoie au client sur Telegram le tableau de performance d'une stratégie.

        ROI actif (évolution du capital) et passif (évolution du prix) sur 24 h,
        7 jours, 30 jours et depuis le premier relevé. Pas d'envoi pour BTCEUR_JF_2.
        Attention : la colonne 30 J affiche la somme de tous les gains, pas 30 jours.
        """
        devises = self.sql.get_devises_from_symbol_real(symbol)
        date_0 = datetime.now()    
        date_1 = datetime.now() - timedelta(days=1)
        date_7 = datetime.now() - timedelta(days=7)
        date_30 = datetime.now() - timedelta(days=30)
                
        dash_0 = self.sql.get_dashboard_infos(symbol,str(date_0.year)+"-"+"{0:0=2d}".format(date_0.month)+"-"+"{0:0=2d}".format(date_0.day))
        dash_1 = self.sql.get_dashboard_infos(symbol,str(date_1.year)+"-"+"{0:0=2d}".format(date_1.month)+"-"+"{0:0=2d}".format(date_1.day))
        dash_7 = self.sql.get_dashboard_infos(symbol,str(date_7.year)+"-"+"{0:0=2d}".format(date_7.month)+"-"+"{0:0=2d}".format(date_7.day))
        dash_30 = self.sql.get_dashboard_infos(symbol,str(date_30.year)+"-"+"{0:0=2d}".format(date_30.month)+"-"+"{0:0=2d}".format(date_30.day))
        dash_MAX = self.sql.get_older_dashboard_infos(symbol)
        capital_portfolio = dash_0["cap_graph"] + dash_0["epargne"] + dash_0["factu"] + dash_0["up_TMP"]
        e_b = self.sql.get_ecart_bet_from_symbol(symbol)
        qtt_crypto_graph = 0.0
        for el in e_b:
            if e_b[el][0]>dash_0["instant_price"]:
                qtt_crypto_graph += e_b[el][1]
        percent_c = (qtt_crypto_graph*dash_0["instant_price"])/capital_portfolio
        if dash_1 != None:
            ###Crypto ROI 24
            capital_portfolio_1 = dash_1["cap_graph"] + dash_1["epargne"] + dash_1["factu"] + dash_1["up_TMP"]
            ROI_24_Actif=100 * (capital_portfolio/capital_portfolio_1-1)
            ROI_24_Actif_FIDU = "{:.2f}".format(ROI_24_Actif*capital_portfolio_1/100)
            gain_24 = "{:.2f}".format(dash_0["gain_day"])
            pourcent_passif = dash_0["instant_price"]/dash_1["instant_price"]
            ROI_24_passif = "{:.2f}".format(100 * (pourcent_passif-1))
            ROI_24_passif_FIDU = "{:.2f}".format(capital_portfolio_1 * (pourcent_passif-1))
            ROI_24_Actif="{:.2f}".format(100 * (capital_portfolio/capital_portfolio_1-1))
        else:
            ROI_24_Actif = "NA"
            ROI_24_Actif_FIDU = "NA"
            gain_24 = "NA"
            ROI_24_passif = "NA"
            ROI_24_passif_FIDU = "NA"
        if dash_7 != None:
            ###Crypto ROI MAX
            capital_portfolio_7 = dash_7["cap_graph"] + dash_7["epargne"] + dash_7["factu"] + dash_7["up_TMP"]
            ROI_7_Actif=100 * (capital_portfolio/capital_portfolio_7-1)
            ROI_7_Actif_FIDU = "{:.2f}".format(ROI_7_Actif*capital_portfolio_7/100)
            gain_7 = "{:.2f}".format(self.sql.get_sum_7_days_dashboard_benef(symbol))
            pourcent_passif = dash_0["instant_price"]/dash_7["instant_price"]
            ROI_7_passif = "{:.2f}".format(100 * (pourcent_passif-1))
            ROI_7_passif_FIDU = "{:.2f}".format(capital_portfolio_7 * (pourcent_passif-1))
            ROI_7_Actif="{:.2f}".format(100 * (capital_portfolio/capital_portfolio_7-1))
        else:
            ROI_7_Actif = "NA"
            ROI_7_Actif_FIDU = "NA"
            gain_7 = "NA"
            ROI_7_passif = "NA"
            ROI_7_passif_FIDU = "NA"
        if dash_30 != None:
            ###Crypto ROI MAX
            capital_portfolio_30 = dash_30["cap_graph"] + dash_30["epargne"] + dash_30["factu"] + dash_30["up_TMP"]
            ROI_30_Actif=100 * (capital_portfolio/capital_portfolio_30-1)
            ROI_30_Actif_FIDU = "{:.2f}".format(ROI_30_Actif*capital_portfolio_30/100)
            gain_30 = "{:.2f}".format(self.sql.get_sum_dashboard_benef(symbol))
            pourcent_passif = dash_0["instant_price"]/dash_30["instant_price"]
            ROI_30_passif = "{:.2f}".format(100 * (pourcent_passif-1))
            ROI_30_passif_FIDU = "{:.2f}".format(capital_portfolio_30 * (pourcent_passif-1))
            ROI_30_Actif="{:.2f}".format(100 * (capital_portfolio/capital_portfolio_30-1))
        else:
            ROI_30_Actif = "NA"
            ROI_30_Actif_FIDU = "NA"
            gain_30 = "NA"
            ROI_30_passif = "NA"
            ROI_30_passif_FIDU = "NA"
        if dash_MAX != None:
            ###Crypto ROI MAX
            capital_portfolio_MAX = dash_MAX["cap_graph"] + dash_MAX["epargne"] + dash_MAX["factu"] + dash_MAX["up_TMP"]
            ROI_MAX_Actif=100 * (capital_portfolio/capital_portfolio_MAX-1)
            ROI_MAX_Actif_FIDU = "{:.2f}".format(ROI_MAX_Actif*capital_portfolio_MAX/100)
            gain_MAX = "{:.2f}".format(self.sql.get_sum_dashboard_benef(symbol))
            pourcent_passif = dash_0["instant_price"]/dash_MAX["instant_price"]
            ROI_MAX_passif = "{:.2f}".format(100 * (pourcent_passif-1))
            ROI_MAX_passif_FIDU = "{:.2f}".format(capital_portfolio_MAX * (pourcent_passif-1))
            ROI_MAX_Actif="{:.2f}".format(100 * (capital_portfolio/capital_portfolio_MAX-1))
        else:
            ROI_MAX_Actif = "NA"
            ROI_MAX_Actif_FIDU = "NA"
            gain_MAX = "NA"
            ROI_MAX_passif = "NA"
            ROI_MAX_passif_FIDU = "NA"


        str_message = "#################################################"
        str_message += "\n#\t\t"+symbol+"\t\t\t#"
        str_message += "\n#################################################"
        str_message += "\nPercent "+devises["devise1"]+" : " + "{:.2f}".format(percent_c*100)
        str_message += "\nPercent "+devises["devise2"]+" : "+ "{:.2f}".format(100 - percent_c*100)
        str_message += "\n#################################################"
        str_message += "\n\t\t\t\t\t                 | 24 H\t| 7 J\t| 30 J\t|   MAX\t#"
        str_message += "\nROI Actif (%)\t  |" + ROI_24_Actif + "\t|" + ROI_7_Actif + "\t|" + ROI_30_Actif + "\t|" + ROI_MAX_Actif + "\t# "
        str_message += "\nROI Actif "+devises["devise2"]+"\t|" + ROI_24_Actif_FIDU + "\t|" + ROI_7_Actif_FIDU + "\t|" + ROI_30_Actif_FIDU + "\t|" + ROI_MAX_Actif_FIDU + "\t# "
        str_message += "\nGain BOT    \t   |"+gain_24+"\t|"+gain_7+"\t|"+gain_30+"\t|"+gain_MAX+"\t#"
        str_message += "\n#################################################"
        str_message += "\nROI Passif (%)\t   |" + ROI_24_passif + "\t|" + ROI_7_passif + "\t|" + ROI_30_passif + "\t|" + ROI_MAX_passif + "\t# "
        str_message += "\nROI Passif "+devises["devise2"]+"\t|" + ROI_24_passif_FIDU + "\t|" + ROI_7_passif_FIDU + "\t|" + ROI_30_passif_FIDU + "\t|" + ROI_MAX_passif_FIDU + "\t# "
        str_message += "\n#################################################"
        clients = self.sql.get_clients_infos()
        if symbol != "BTCEUR_JF_2":
            self.sql.tele.send_message(str_message,clients[devises["client"]]["tele"])

    def new_dashboard(self,symbol,ID_client):
        """Rapport spécifique au compte de Jeff, envoyé sur Telegram.

        Valeur du wallet en EUR comparée à un simple achat-conservation de BTC
        (capital initial 5111 EUR au 28/11/2024). ID client 6 codé en dur.
        """
        str_message = "###########"
        str_message += "\n#\t\t Hello Jeff\t\t\t#"
        str_message += "\n###########"
        #Attention ID spécifique à Jeff à changer par la suite
        wallet = self.bin.get_wallet(6)
        sum_eur = 0.0
        for crypto in wallet:
            total = float(crypto["free"])+float(crypto["locked"])
            print("# "+crypto["asset"]+ "\t: Free : "+ crypto["free"]+"\tlock : "+crypto["locked"]+ "\tTotal : "+str(total))
            if crypto["asset"] != "EUR":
                taux = self.bin.get_price(crypto["asset"]+"EUR",ID_client)
                try:
                    US_price = total*float(taux["price"])
                    sum_eur += US_price
                    print("#\t EUR : "+str(US_price))
                except:
                    print("#\tNO EUR Price ")
            else:
                sum_eur += total
        init_capital = 5111
        init_price = 90300
        BTC_init = init_capital/init_price
        btc_eur_taux = self.bin.get_price("BTCEUR",ID_client)
        floating = BTC_init*float(btc_eur_taux["price"])
        str_message += "\ninitial capital (28/11/2024) EUR : " +str(init_capital)
        str_message +="\ncurrent capital in EUR : "+str(int(sum_eur))
        ROI_Actif_percent = ((sum_eur-init_capital)/init_capital)*100
        str_message +="\nROI actif (EUR): " + str(int(sum_eur-init_capital)) + " ("+str(round(ROI_Actif_percent,2))+"%)"
        str_message +="\nfloating in EUR : "+ str(int(floating))
        ROI_flotant_percent = ((floating-init_capital)/init_capital)*100
        str_message +="\nROI floating (EUR): " + str(int(floating-init_capital)) + " ("+str(round(ROI_flotant_percent,2))+"%)"
        clients = self.sql.get_clients_infos()
        devises = self.sql.get_devises_from_symbol_real("BTCEUR_JF_2")
        self.sql.tele.send_message(str_message,clients[devises["client"]]["tele"])





###########################################################################
#                                 MAIN                                    #
###########################################################################
def main():
    """Outil en ligne de commande.

        python3 KPI.py day   relevé + rapport Telegram pour toutes les stratégies actives
        python3 KPI.py jeff  rapport du compte de Jeff uniquement
        python3 KPI.py       menu : gain mensuel ou statistiques par palier
    """
    DEVISE="PEPEEUR_1"
    kpi = Kpi()
    sql = sqlAcces()
    bin = binAcces()
    mois = 9
    a=""
    if len(sys.argv) > 1:
        a = sys.argv[1]
    if a == "day":
        symbols = kpi.sql.get_symbols_actif()
        for ID_client in symbols:
            for symbol in symbols[ID_client]:
                kpi.set_dashboard_info(symbol)
                kpi.get_dashboard_KPI(symbol)
                if symbol == "BTCEUR_JF_2":
                    kpi.new_dashboard(symbol,6)

    elif a == "jeff":
        symbols = kpi.sql.get_symbols_actif()
        for ID_client in symbols:
            for symbol in symbols[ID_client]:
                if symbol == "BTCEUR_JF_2":
                    print("On passe bien par ici")
                    kpi.new_dashboard(symbol,6)

    else:
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
