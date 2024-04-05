from binance.client import Client
import json



with open('bin_key.json') as json_file:
    config = json.load(json_file)
client = Client(config["api"], config["secret"])
info = client.get_account()
for el in info["balances"]:
    if el["asset"] == "EUR" or el["asset"] == "DOGE" or el["asset"] == "XRP":
        print(el)
#df = pd.DataFrame(info["balances"])
#df["free"] = df["free"].astype(float).round(4)
#df = df[df["free"] > 0]
#print(df)

class basics():

    def __init__(self):
        #Declaration d'une variable interne pour l ecart
        self.ecart=ECART
        self.bet = 42
        self.flag_bet_changement = 42


    #############################################
    #
    # return le dictionnaire de crypto ou devise sur le compte avec le solde de la crypto (la devise est la key et le solde le contenu du dictionnaire
    # IN:
    #   -API kraken connetion objet
    # OUT:
    #   -dictionnaire DEVISE:SOLDE
    #
    #############################################

    def get_found(selk,client):
        try:
            info = client.get_account()
            retour = {}
            for el in info["balances"]:
                if el["asset"] == "EUR":
                    retour['ZEUR']=el["free"]
                elif el["asset"] == "DOGE":
                    retour['ZEUR']=el["free"]
                elif el["asset"] == "XRP":
                    retour['ZEUR']=el["free"]

        except:
            retour = ["ERROR"]
        return retour
