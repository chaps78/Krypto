from binance.client import Client
import json
import telebot
import time
import os

import parameters

BOT_CHAT_ID = parameters.TELEGRAM_CHAT_ID

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


    #############################################
    #
    # DESCRIPTION:
    #
    # IN:
    #   -
    #   -
    # OUT:
    #   -
    #
    #############################################

    def new_order(self,client,pair,type_B_S,ordertype,price,volume):
        try:

            
            response = client.create_order(symbol=pair, 
                                        side=type_B_S, 
                                        type=ordertype, 
                                        quantity=volume, 
                                        price=price,
                                        timeInForce='GTC')
        except:
            bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
            bot.send_message(BOT_CHAT_ID, 'check tes logs, t as une piste (a l ouverture d un ordre)')
            cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";" + "PEUT ETRE L ERREUR EST ICI -- si il n'y a pas le log suivant le probleme vient de response" +str(pair)+";"+ str(type_B_S)+";"+str(ordertype)+";"+str(price)+";"+str(volume) + "ouverture ordre 1' >> LOG/BIN_ERROR.error"
            os.system(cmd)
            cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";" + str(response) + "ouverture ordre 1' >> LOG/BIN_ERROR.error"
            os.system(cmd)
        try:
            print(str(response['orderId']))
        except:
            bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
            bot.send_message(BOT_CHAT_ID, 'check tes logs, t as une piste (a l ouverture d un ordre 2eme)')
            cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";" + str(response) + "ouverture ordre 2' >> LOG/BIN_ERROR.error"
            os.system(cmd)


        ID=""
        try:
            ID=str(response['orderId'])
        except:
            bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
            bot.send_message(BOT_CHAT_ID, 'check tes logs, t as une piste (a l ouverture d un ordre 4eme)')
            cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";" + str(response) + "ouverture ordre 3 resultat non present dans lordre' >> LOG/BIN_ERROR.error"
            os.system(cmd)
        cmd="echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";;"+type_B_S+";"+str(price) +";"+ str(volume)+";;"+ str(ID) +";' >> LOG/BIN_"+time.strftime('%Y#%m#%d')+".log"
        os.system(cmd)

        return ID

        def new_order_haleving(self,kraken,pair,type_B_S,ordertype,price,volume):
            try:
                response = kraken.query_private('AddOrder',
                                                {'pair': pair,
                                                 'type': type_B_S,
                                                 'ordertype': ordertype,
                                                 'price': price,
                                                 'volume': volume})
            except:
                bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
                bot.send_message(BOT_CHAT_ID, 'check tes logs, t as une piste (a l ouverture d un ordre)')
                cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";" + "PEUT ETRE L ERREUR EST ICI -- si il n'y a pas le log suivant le probleme vient de response" +str(pair)+";"+ str(type_B_S)+";"+str(ordertype)+";"+str(price)+";"+str(volume) + "ouverture ordre 1' >> LOG/ERROR.error"
                os.system(cmd)
                cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";" + str(response) + "ouverture ordre 1' >> LOG/ERROR.error"
                os.system(cmd)
            try:
                print(str(response['result']))
            except:
                bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
                bot.send_message(BOT_CHAT_ID, 'check tes logs, t as une piste (a l ouverture d un ordre 2eme)')
                cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";" + str(response) + "ouverture ordre 2' >> LOG/ERROR.error"
                os.system(cmd)
            try:
                if(response['error']!=[]):
                    cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";l erreur d ouverture d ordre est la suivante;" + str(response['error']) + "ouverture ordre 4' >> LOG/ERROR.error"
                    os.system(cmd)
                if(response['error']==['EOrder:Insufficient funds']):
                    return -1
            except:
                bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
                bot.send_message(BOT_CHAT_ID, 'check tes logs, t as une piste (a l ouverture d un ordre 3eme)')

            ID=""
            try:
                ID=str(response['result']['txid'][0])
            except:
                bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
                bot.send_message(BOT_CHAT_ID, 'check tes logs, t as une piste (a l ouverture d un ordre 4eme)')
                cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";" + str(response) + "ouverture ordre 3 resultat non present dans lordre' >> LOG/ERROR.error"
                os.system(cmd)
            cmd="echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";;"+type_B_S+";"+str(price) +";"+ str(volume)+";;"+ str(ID) +";"+str(response['error'])+"' >> LOG/"+time.strftime('%Y#%m#%d')+".log"
            os.system(cmd)



            return [ID,price,volume]

basic = basics()


with open('bin_key.json') as json_file:
    config = json.load(json_file)
client = Client(config["api"], config["secret"])
#print(basic.get_found(client))
result = basic.new_order(client,"XRPEUR",'buy','limit',"0.2","39")
#result = client.create_order(symbol="XRPEUR", side='buy', type='limit', quantity=40, price="0.2",timeInForce='GTC')
print(result)
