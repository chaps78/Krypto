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
                    retour['EUR']=el["free"]
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

            if ordertype == client.ORDER_TYPE_MARKET:
                response = client.create_order(symbol=pair, 
                                        side=type_B_S, 
                                        type=ordertype, 
                                        quantity=volume)
            else:
                response = client.create_order(symbol=pair, 
                                            side=type_B_S, 
                                            type=ordertype, 
                                            quantity=volume, 
                                            price=price,
                                            timeInForce='GTC')
        except Exception as inst:
            bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
            bot.send_message(BOT_CHAT_ID, 'BIN open order ERROR ')
            cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";ERROR lors de l ouverture de l ordre;" + str(inst).replace("'","") + "' >> LOG/BIN_ERROR.error"
            os.system(cmd)
            print(cmd)
            print("On passe ICI")
            return ""
        try:
            print(str(response['orderId']))
        except Exception as inst:
            bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
            bot.send_message(BOT_CHAT_ID, 'New order problème de recuperation de l ID')
            cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";New order probleme de recuperation de l ID;" + str(response) + ";"+ str(inst).replace("'","")+"' >> LOG/BIN_ERROR.error"
            os.system(cmd)
            return ""

        return response['orderId']


#########################################
#          TODO                         #
#########################################
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


    #############################################################################################################################
    #
    # DESCRIPTION:
    #  recupère l'ID d'un ordre et retourne son status (open ou closed)
    #  si le status est "closed" la fonction écrit dans les log le status de l'ordre avec des infos suplémentaire à l'instat T
    # IN:
    #   -API kraken connetion objet
    #   -ID de l'ordre à vérifier
    #   -niveau (fibo) pour écrire dans les log si l'ordre est à closed
    #   -montant du bet
    #   -ecart = delta entre deux ordres
    # OUT:
    #   -status de l'ordre ("open"/"closed")
    #
    #   -reprot de l'ordre dans les logs si l'ordre est clos
    #
    #############################################################################################################################


    def order_status(self, client, order_id, niveau, montant, ecart):
        #result = kraken.query_private('QueryOrders', {'txid': order_id})
        result = client.get_order(symbol="XRPEUR",orderId=order_id)
        ret = result['status']
        if ret == client.ORDER_STATUS_FILLED:
            volume = result['executedQty']
            prix = result['price']
            frais = result['cummulativeQuoteQty']
            type_B_S = result['side']

            soldes = self.get_found(client)
            euros = str(soldes['EUR'])
            xrp = str(soldes['XRP'])

            cmd="echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";"+ret+";"+type_B_S+";"+prix+";"+ volume +";"+frais+";"+ order_id +";;"+str(montant)+";;"+str(niveau)+";"+str(ecart)+";"+ euros +";"+xrp+";"+"' >> LOG/BIN_"+time.strftime('%Y#%m#%d')+".log"
            os.system(cmd)

        return ret

    #############################################
    #
    # DESCRIPTION: meme comportement que order_status prenant en entrée une liste d'ID
    # Objectif : limiter les appels API
    #
    # IN:
    #   -
    # OUT:
    #   -
    #
    #############################################

    def orders_status(self,client, dico_orders,dico_haleving=[]):
        #order_id,niveau,montant,ecart):
        list_id_orders = list(dico_orders.keys())
        if dico_haleving != []:
            list_id_orders.append(dico_haleving[0])
        try:
            all_orders = client.get_all_orders(symbol="XRPEUR")
            result = {}
            for el in all_orders:
                if str(el["orderId"]) in list_id_orders:
                    print("On rentre")
                    result[str(el["orderId"])] = el
            #ids_order_for_API = str(list_id_orders[0]) + "," + str(list_id_orders[1])
            #result = kraken.query_private('QueryOrders', {'txid': ids_order_for_API})
            print(result)
        except Exception as inst:
            cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";order_status recuperation ordres; "+str(inst).replace("'","")+"' >> LOG/BIN_ERROR.error"
            os.system(cmd)
        return_value = {}
        for order_id in list_id_orders:
            try:
                ret = result[order_id]['status']
            except Exception as inst:
                cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";error dans lecture du retour; ERROR: "+str(inst).replace("'","")+"' >> LOG/BIN_ERROR.error"
                os.system(cmd)
                cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";error dans lecture du retour; RETOUR API"+str(result).replace("'","")+"' >> LOG/BIN_ERROR.error"
                os.system(cmd)
                cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";error dans lecture du retour; KEY"+str(list_id_orders).replace("'","")+"' >> LOG/BIN_ERROR.error"
                os.system(cmd)
                time.sleep(2)
            return_value[order_id] = ret
            if ret == 'FILLED':
                volume = result[order_id]['executedQty']
                prix = result[order_id]['price']
                frais = "NA"
                type_B_S = result[order_id]['side']

                soldes = self.get_found(client)
                euros = str(soldes['EUR'])
                xrp = str(soldes['XRP'])
                try:
                    niveau = dico_orders[order_id]["niveau"]
                    ecart = dico_orders[order_id]["ecart"]
                except:
                    niveau = "NA"
                    ecart = "NA"

                cmd="echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";"+ret+";"+type_B_S+";"+prix+";"+ volume +";"+frais+";"+ order_id +";NA;;;"+str(niveau)+";"+str(ecart)+";"+ euros +";"+xrp+";"+"' >> LOG/BIN_"+time.strftime('%Y#%m#%d')+".log"
                os.system(cmd)
        return return_value


    #####################################################################################################################################
    #
    # DESCRIPTION:
    #   Ferme un ordre donne en se basant sur l ID.
    #   Pour un ordre non exécuté:
    #           indique dans les logs que l ordre est annule
    #   Pour un ordre execute partiellement:
    #           ouvre un ordre market avec le meme volume que l ordre partiel le contrebalancer et garder les memes points de bascule.
    #
    # IN:
    #   -Acces KRAKEN
    #   -ID de l ordre
    # OUT:
    #   -Retour de la requete revoyé par l API
    #   -(enregistrement des donnees dans les log)
    #
    #####################################################################################################################################

    def order_close(self,client, order_id):
        try:
            close=0
            #result = kraken.query_private('CancelOrder', {'txid': order_id})
            result = client.cancel_order(symbol="XRPEUR",orderId=int(order_id))
            close=1

            #Bug régulièrement provoqué par un result vide
            #result={}
            #loop=0
            #while result=={} and loop <10:
                #verifie que l'ordre clos a ete execute partiellement et si il a ete partiellement execute, il integre dans les logs le volume execute
            #    partial_execute = kraken.query_private('QueryOrders', {'txid': order_id})
            #    result=partial_execute['result']
            #    if result=={}:
            #        bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
            #        bot.send_message(BOT_CHAT_ID, 'Je n ai pas de report renvoye c est pas bon')
            #        bot.send_message(BOT_CHAT_ID, 'loop value: '+ str(loop))
            #        time.sleep(5)
            #        loop+=1
            close=2
            print("OUIII 1")
            breakpoint()
            if float(result['executedQty']) == 0.0:
                print("OUIII 2")
                close=3
                cmd="echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";cancel;;;;;"+ str(order_id) +";;;;;;;;' >> LOG/BIN_"+time.strftime('%Y#%m#%d')+".log"
                os.system(cmd)
                close=4
            else:
                print("OUIII 3")
                close=5
                volume = result['executedQty']
                prix = result['price']
                frais = "NA"
                type_B_S = result['side']
                close=6
                cmd="echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";closed;"+type_B_S+";"+prix+";"+ volume +";"+frais+";"+ order_id +";"+str(result['error'])+"__partialy_closed;;;;;;;"+"' >> LOG/BIN_"+time.strftime('%Y#%m#%d')+".log"
                os.system(cmd)
                close=7
                print("OUIII 4")
                #Envoi un message sur telegram en cas d ordre partiellement clos
                #bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
                #bot.send_message(BOT_CHAT_ID, 'ORDRE PARTIEL VOLUME : ' + str(volume) + ' PRIX : ' + str(prix))

                #ouvre un ordre au prix du marche pour contrebalancer l ordre partiellement clos, cela permet de conserver le prix d equilibre
                ID_partial = ""
                close=8
                print("OUIII 5")
                if type_B_S == "buy":
                    ID_partial = self.new_order(client,"XRPEUR","SELL",client.ORDER_TYPE_MARKET,prix,volume)
                else:
                    ID_partial = self.new_order(client,"XRPEUR","BUY",client.ORDER_TYPE_MARKET,prix,volume)
                close=9

                time.sleep(2)
                #Appel de la fonction pour effectuer le log de l ordre, l ordre est obligatoirement clos car c est un ordre market qui doit etre execute immediatement
                self.order_status(client, str(ID_partial),"NA",volume,"")
                close=10
        except:
            bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
            bot.send_message(BOT_CHAT_ID, 'order close ' +str(close))
            bot.send_message(BOT_CHAT_ID,"result request fail : "+str(result))
            bot.send_message(BOT_CHAT_ID,"status de l ordre apres tentative de close : "+str("ferme_ou_pas"))
        return result

basic = basics()


with open('bin_key.json') as json_file:
    config = json.load(json_file)
client = Client(config["api"], config["secret"])
#print(basic.get_found(client))
#breakpoint()
result = basic.new_order(client,"XRPEUR",'buy','limit',"0.2","31")
print(result)
#result = basic.new_order(client,"XRPEUR",'buy',client.ORDER_TYPE_MARKET,"0.2","10")
#result = basic.new_order(client,"XRPEUR",'buy',client.ORDER_TYPE_LIMIT,"0.2","30")
#result = basic.new_order(client,"XRPEUR",'buy',client.ORDER_TYPE_LIMIT,"0.1","55")
#print(result)
#currentOrder = client.get_order(symbol="XRPEUR",orderId=result)
#time.sleep(15)
#basic.order_status(client,"643981514",3,6969,"")
#all_orders = client.get_all_orders(symbol="XRPEUR")
#ordres_dic = {"642318773":"","642325502":""}
#ordres_hal = ["643980570"]
#retour = basic.orders_status(client,ordres_dic,ordres_hal)
breakpoint()
#print(type(result))
#retour = client.cancel_order(symbol="XRPEUR",orderId=result)
retour = basic.order_close(client,result)
print(retour)

