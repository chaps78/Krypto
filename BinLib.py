from binance.client import Client
import json





class basics():



    #############################################
    #
    # return le dictionnaire de crypto ou devise sur le compte avec le solde de la crypto (la devise est la key et le solde le contenu du dictionnaire
    # IN:
    #   -API kraken connetion objet
    # OUT:
    #   -dictionnaire DEVISE:SOLDE
    #
    #############################################

    def get_found(self,client):
        try:
            info = client.get_account()
            retour = {}
            for el in info["balances"]:
                if el["asset"] == "EUR":
                    retour['ZEUR']=el["free"]
                elif el["asset"] == "DOGE":
                    retour['DOGE']=el["free"]
                elif el["asset"] == "XRP":
                    retour['XRP']=el["free"]

        except:
            retour = ["ERROR"]
        return retour


basic = basics()


with open('bin_key.json') as json_file:
    config = json.load(json_file)
client = Client(config["api"], config["secret"])
#print(basic.get_found(client))

result = client.create_order(symbol="XRPEUR", side='BUY', type='LIMIT', quantity=40, price="0.2",timeInForce='GTC')
print(result)
