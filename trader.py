import krakenex
import time
import os
import json
import telebot
import datetime
import importlib

import parameters
import ecart

ECART         = parameters.ECART
MONTANT_ACHAT = parameters.MONTANT_ACHAT
DICO_BET      = parameters.DICO_BET


#Token pour le bot telegram
TELEG_TOKEN = parameters.TELEGRAM_TOKEN
#Id du chat pour le BOT telegram
BOT_CHAT_ID = parameters.TELEGRAM_CHAT_ID


VERSION="1.13"

def main():
    cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";START APPLI;VERSION "+VERSION+"' >> LOG/ERROR.error"
    os.system(cmd)
    trader=tr_bot()
    bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
    bot.send_message(BOT_CHAT_ID, 'RESTART V:'+VERSION)
    try:
        trader.run()
    except Exception as inst:
        cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";CRASH APPLI sorti du thread ce message doit apparaitre; ' >> LOG/ERROR.error"
        os.system(cmd)
        cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";CRASH APPLI sorti du thread et celui ci aussi; "+str(inst).replace("'","")+"' >> LOG/ERROR.error"
        os.system(cmd)
        bot.send_message(BOT_CHAT_ID, 'CRASHHHHHHHHHHHH:')

class tr_bot():

    def __init__(self):
        self.TIME_SLEEP=2

    def run(self):
        kraken = krakenex.API()
        kraken.load_key('kraken.key')
        basic = basics()

        achat={}
        vente={}

        achat = basic.lecture_achat(achat) 
        vente = basic.lecture_vente(vente) 


        #Recuperation des niveaux de vente et d achat
        dico_niv = basic.lecture_niveaux()
        #count_vente = dico_niv["vente"]
        #count_achat = dico_niv["achat"]
        count_vente = 0
        count_achat = 0
        delta_achat_niveau=0
        delta_vente_niveau=0


        prix = basic.latest_price(kraken,"XRPEUR")
       
        ordres_ouverts = kraken.query_private('OpenOrders',{'trades': 'true','start':'1514790000'})
        try:
            #verification de la synchro entre kraken et les listes
            verif_OK = basic.verif(achat,vente,ordres_ouverts)
        except KeyError:
            verif_OK = False
        if verif_OK == False or (achat == {} and vente == {}):
            #supprime l'ensemble des ordres et cree 2 nouveaux ordres pour partir sur de nouvelles bases
            basic.flush(ordres_ouverts,kraken,achat,vente,prix)
            achat = basic.lecture_achat(achat) 
            vente = basic.lecture_vente(vente) 

        

        previous_day = datetime.datetime.today().day

        bas = float(max(achat.keys()))
        haut = float(min(vente.keys()))
        resume={"a":0,"v":0}

        time.sleep(self.TIME_SLEEP)

        while 1:
            passage_haut = False
            passage_bas = False
            #Envoi d informations quotidienne
            if previous_day != datetime.datetime.today().day:
                previous_day = datetime.datetime.today().day
                bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
                bot.send_message(BOT_CHAT_ID, 'NBR Achat : ' + str(resume["a"]) + '\nNBR Vente : ' + str(resume["v"]))

                resume={"a":0,"v":0}
                importlib.reload(parameters)
                DICO_BET = parameters.DICO_BET

            try:
                prix = basic.latest_price(kraken,"XRPEUR")
                time.sleep(2)

                dico_orders={}
                dico_orders[vente[str(haut)]] = {"niveau":count_vente,"ecart":basic.ecart}
                dico_orders[achat[str(bas)]] = {"niveau":count_vente,"ecart":basic.ecart}

                return_status = basic.orders_status(kraken,dico_orders)
                passage_haut = return_status[vente[str(haut)]] == 'closed'
                passage_bas = return_status[achat[str(bas)]] == 'closed'

                if passage_bas: 
                    resume["a"] += 1

                if passage_haut: 
                    resume["v"] += 1

            except KeyboardInterrupt:
                print("ctrl + C")
                break
            except Exception as inst:
                passage_bas=False
                passage_haut=False
                cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";CRASH APPLI dans le while vente: "+str(vente)+";"+"achat"+str(achat)+";prix"+str(prix)+";bas"+str(bas)+";haut"+str(haut)+"' >> LOG/ERROR.error"
                os.system(cmd)
                cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";retour error; "+str(inst).replace("'","")+"' >> LOG/ERROR.error"
                os.system(cmd)

            try:
                if passage_bas:
                    del achat[str(bas)]
                    i=0
                    while bas > ecart.ECART[i]:
                        i += 1
                    if count_achat == 0:

                        bas=ecart.ECART[i-1]
                        count_achat +=1
                        count_vente=0
                        haut=ecart.ECART[i+1]
                        delta_achat_niveau=0
                        delta_vente_niveau=0
                        achat={}
                        vente={}
                        basic.flush_zero(kraken)
                    elif count_achat == 1:
                        bas=ecart.ECART[i-2]
                        count_achat +=1
                        count_vente=0
                        haut=ecart.ECART[i+1]
                        basic.get_bet_achat(bas+basic.ecart)
                        delta_achat_niveau = basic.bet
                        delta_vente_niveau=0
                        achat={}
                        vente={}
                        basic.flush_zero(kraken)
                    else:
                        bas=ecart.ECART[i-3]
                        count_achat +=1
                        count_vente=0
                        delta_vente_niveau=0
                        haut=ecart.ECART[i+1]
                        basic.get_bet_achat(bas+basic.ecart)
                        delta_achat_niveau = basic.bet
                        basic.get_bet_achat(bas+2*basic.ecart)
                        delta_achat_niveau += basic.bet
                        achat={}
                        vente={}
                        basic.flush_zero(kraken)
                    ####attention l'achat existe peut etre deja ####################
                    if not str(bas) in achat.keys():
                        basic.get_bet_achat(bas)
                        buy = basic.new_order(kraken,"XRPEUR","buy","limit",str(bas),str(basic.bet+delta_achat_niveau))
                        achat[str(bas)]=str(buy)
                    basic.get_bet_vente(haut)
                    buy = basic.new_order(kraken,"XRPEUR","sell","limit",str(haut),str(basic.bet))
                    vente[str(haut)]=str(buy)
                    #Enregistrement du niveau achat_vente pour revenir au meme etat en cas de redemarrage
                    basic.ecriture_niveaux(count_achat , count_vente)
                    #Enregistrement des ordres d achat et vente qui viennent d etre passe
                    basic.ecriture_achat_vente(achat,vente)

                except Exception as inst:
                    bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
                    bot.send_message(BOT_CHAT_ID, 'check tes logs, t as une piste (dans le 1er IF)' +str(inst).replace("'",""))
                try:

                if passage_haut:
                    i=0
                    while haut > ecart.ECART[i]:
                        i += 1
                    del vente[str(haut)]
                    if count_vente == 0:
                        haut=ecart.ECART[i+1]
                        bas=ecart.ECART[i-1]
                        count_achat=0
                        count_vente+=1
                        delta_achat_niveau=0
                        delta_vente_niveau=0
                        achat={}
                        vente={}
                        basic.flush_zero(kraken)
                    elif count_vente == 1:
                        delta_achat_niveau=0
                        haut=ecart.ECART[i+2]
                        bas=ecart.ECART[i-1]
                        count_achat=0
                        count_vente+=1
                        basic.get_bet_vente(haut - basic.ecart)
                        delta_vente_niveau = basic.bet
                        achat={}
                        vente={}
                        basic.flush_zero(kraken)
                    else:
                        delta_achat_niveau=0
                        haut=ecart.ECART[i+3]
                        bas=ecart.ECART[i-1]
                        count_achat=0
                        count_vente+=1
                        basic.get_bet_vente(haut - basic.ecart)
                        delta_vente_niveau = basic.bet
                        basic.get_bet_vente(haut - 2*basic.ecart)
                        delta_vente_niveau += basic.bet
                        achat={}
                        vente={}
                        basic.flush_zero(kraken)

                    basic.get_bet_achat(bas)
                    buy = basic.new_order(kraken,"XRPEUR","buy","limit",str(bas),str(basic.bet))
                    achat[str(bas)]=str(buy)
                    ######        Attention la vente existe peut etre deja
                    if not str(haut) in vente.keys():
                        basic.get_bet_vente(haut)
                        buy = basic.new_order(kraken,"XRPEUR","sell","limit",str(haut),str(basic.bet + delta_vente_niveau ))
                        vente[str(haut)]=str(buy)

                    #Enregistrement du niveau achat_vente pour revenir au meme etat en cas de redemarrage
                    basic.ecriture_niveaux(count_achat , count_vente)
                    #Enregistrement des ordres d achat et vente qui viennent d etre passe
                    basic.ecriture_achat_vente(achat,vente)

            except Exception as inst:
                cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";CRASH APPLI WOOOOOOOOOOOOOOOOOO C ICI: ' >> LOG/ERROR.error"
                os.system(cmd)
                bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
                bot.send_message(BOT_CHAT_ID, 'check tes logs, t as une piste (dans le gros IF)' +str(inst).replace("'",""))
                cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+"; Probleme dans les IF"+str(passage_bas)+";"+str(passage_haut)+";"+str(prix)+"' >> LOG/ERROR.error"

            time.sleep(self.TIME_SLEEP)
    
########################################################################################
#                                                                                      #
#                LIBRAIRIE DE FONCTIONS BASIQUE POUR LE TREAD                          #
#                                                                                      #
########################################################################################

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

    def get_found(selk,kraken):
        try:
            response = kraken.query_private('Balance')
            retour = response['result']
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

    def new_order(self,kraken,pair,type_B_S,ordertype,price,volume):
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
            cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";" + str(response) + "ouverture ordre 2' >> LOG/ERROR.error"
            os.system(cmd)
        if(response['error']!=[]):
            cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";l erreur d ouverture d ordre est la suivante;" + str(response['error']) + "ouverture ordre 4' >> LOG/ERROR.error"
            os.system(cmd)
        if(response['error']==['EOrder:Insufficient funds']):
            return -1

        ID=""
        try:
            ID=str(response['result']['txid'][0])
        except:
            cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";" + str(response) + "ouverture ordre 3 resultat non present dans lordre' >> LOG/ERROR.error"
            os.system(cmd)
        cmd="echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";;"+type_B_S+";"+str(price) +";"+ str(volume)+";;"+ str(ID) +";"+str(response['error'])+"' >> LOG/"+time.strftime('%Y#%m#%d')+".log"
        os.system(cmd)



        return ID


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


    def order_status(self, kraken, order_id, niveau, montant, ecart):
        result = kraken.query_private('QueryOrders', {'txid': order_id})
        ret = result['result'][order_id]['status']

        if ret == 'closed':
            volume = result['result'][order_id]['vol_exec']
            prix = result['result'][order_id]['price']
            frais = result['result'][order_id]['fee']
            type_B_S = result['result'][order_id]['descr']['type']

            soldes = self.get_found(kraken)
            euros = str(soldes['ZEUR'])
            xrp = str(soldes['XXRP'])

            
            cmd="echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";"+ret+";"+type_B_S+";"+prix+";"+ volume +";"+frais+";"+ order_id +";"+str(result['error'])+";"+str(montant)+";;"+str(niveau)+";"+str(ecart)+";"+ euros +";"+xrp+";"+"' >> LOG/"+time.strftime('%Y#%m#%d')+".log"
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


    def orders_status(self,kraken, dico_orders):
        #order_id,niveau,montant,ecart):
        list_id_orders = list(dico_orders.keys())
        try:
            ids_order_for_API = str(list_id_orders[0]) + "," + str(list_id_orders[1])
            result = kraken.query_private('QueryOrders', {'txid': ids_order_for_API})
        except Exception as inst:
            cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";error dans call API; "+str(inst).replace("'","")+"' >> LOG/ERROR.error"
            os.system(cmd)
        return_value = {}
        for order_id in list_id_orders:
            try:
                ret = result['result'][order_id]['status']
            except Exception as inst:
                cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";error dans lecture du retour; ERROR: "+str(inst).replace("'","")+"' >> LOG/ERROR.error"
                os.system(cmd)
                cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";error dans lecture du retour; RETOUR API"+str(result).replace("'","")+"' >> LOG/ERROR.error"
                os.system(cmd)
                cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";error dans lecture du retour; KEY"+str(list_id_orders).replace("'","")+"' >> LOG/ERROR.error"
                os.system(cmd)
                time.sleep(2)
            return_value[order_id] = ret
            if ret == 'closed':
                volume = result['result'][order_id]['vol_exec']
                prix = result['result'][order_id]['price']
                frais = result['result'][order_id]['fee']
                type_B_S = result['result'][order_id]['descr']['type']

                soldes = self.get_found(kraken)
                euros = str(soldes['ZEUR'])
                xrp = str(soldes['XXRP'])

                niveau = dico_orders[order_id]["niveau"]
                #montant = dico_orders[order_id]["montant"]
                ecart = dico_orders[order_id]["ecart"]

                cmd="echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";"+ret+";"+type_B_S+";"+prix+";"+ volume +";"+frais+";"+ order_id +";"+str(result['error'])+";"+str(self.bet)+";;"+str(niveau)+";"+str(ecart)+";"+ euros +";"+xrp+";"+"' >> LOG/"+time.strftime('%Y#%m#%d')+".log"
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

    def order_close(self,kraken, order_id):
        result = kraken.query_private('CancelOrder', {'txid': order_id})

        
        #verifie que l'ordre clos a ete execute partiellement et si il a ete partiellement execute, il integre dans les logs le volume execute
        partial_execute = kraken.query_private('QueryOrders', {'txid': order_id})
        if float(partial_execute['result'][order_id]['vol_exec']) == 0:
            cmd="echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";cancel;;;;;"+ order_id +";;;;;;;;' >> LOG/"+time.strftime('%Y#%m#%d')+".log"
            os.system(cmd)
        else:
            volume = partial_execute['result'][order_id]['vol_exec']
            prix = partial_execute['result'][order_id]['price']
            frais = partial_execute['result'][order_id]['fee']
            type_B_S = partial_execute['result'][order_id]['descr']['type']
            cmd="echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";closed;"+type_B_S+";"+prix+";"+ volume +";"+frais+";"+ order_id +";"+str(partial_execute['error'])+"__partialy_closed;;;;;;;"+"' >> LOG/"+time.strftime('%Y#%m#%d')+".log"
            os.system(cmd)

            #Envoi un message sur telegram en cas d ordre partiellement clos
            #bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
            #bot.send_message(BOT_CHAT_ID, 'ORDRE PARTIEL VOLUME : ' + str(volume) + ' PRIX : ' + str(prix))

            #ouvre un ordre au prix du marche pour contrebalancer l ordre partiellement clos, cela permet de conserver le prix d equilibre
            ID_partial = ""
            if type_B_S == "buy":
                ID_partial = self.new_order(kraken,"XRPEUR","sell","market",prix,volume)
            else:
                ID_partial = self.new_order(kraken,"XRPEUR","buy","market",prix,volume)


            time.sleep(2)
            #Appel de la fonction pour effectuer le log de l ordre, l ordre est obligatoirement clos car c est un ordre market qui doit etre execute immediatement
            self.order_status(kraken, ID_partial,"NA",volume,"")
        return result


    #############################################
    #
    # DESCRIPTION:
    #
    # IN:
    #   -
    # OUT:
    #   -
    #
    #############################################

    def latest_price(self,kraken,pair):

        prix = kraken.query_public('Ticker', {'pair': pair})
        prix_cour = float(prix['result']['XXRPZEUR']['b'][0])

        return prix_cour


    #############################################
    #
    # DESCRIPTION:
    #
    # IN:
    #   - XRP Price
    # OUT:
    #   - Montant du bet
    #
    #############################################
    def get_bet_base(self,price):
        keys = list(DICO_BET.keys()) 
        ret_key = 0.0
        for key in keys:
            if key < float(price) and key > ret_key:
                ret_key = key
        self.bet = DICO_BET[ret_key]
        #Envoi un message sur telegram en cas d ordre  clos
        #bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
        #bot.send_message(BOT_CHAT_ID, 'PRIX DU BET PROCHAIN BET : ' + str(self.bet) )

    def get_bet_achat(self,price):
        self.get_bet_base(float(price)+ECART)

    def get_bet_vente(self,price):
        self.get_bet_base(float(price))
        if self.flag_bet_changement != self.bet:
            #Envoi un message sur telegram pour changement de montant du bet
            bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
            bot.send_message(BOT_CHAT_ID, 'CHANGEMENT du bet : ' + str(self.flag_bet_changement) + " vers "+str(self.bet) )
            self.flag_bet_changement = self.bet

    #############################################
    #
    # DESCRIPTION:
    #
    # IN:
    #   -
    # OUT:
    #   -
    #
    #############################################

    def verif(self,achat,vente,response):
        #verification de la synchro entre kraken et les listes
        verif_OK = True

        li_verif=achat.keys()
        for key in li_verif:
            if not achat[key] in response['result']['open'].keys():
                verif_OK=False

        li_verif=vente.keys()
        for key in li_verif:
            if not vente[key] in response['result']['open'].keys():
                verif_OK=False

        if not (len(achat.keys())+len(vente.keys())) == len(response['result']['open'].keys()):
            verif_OK=False

        return verif_OK


    #############################################
    #
    # DESCRIPTION:
    #
    # IN:
    #   -
    # OUT:
    #   -
    #
    #############################################

    def flush(self,ordres_ouverts,kraken_key,achat,vente,prix):
        achat={}
        vente={}
        for el in ordres_ouverts['result']['open'].keys():
            self.order_close(kraken_key,el)
        prix_cour = float(prix)
        #TODO
        #Recuperer le prix du dernier ordre closed
        last_close = float(os.popen("cat LOG/*log|grep closed|tail -n 1").readlines()[0].split(";")[4])
        last_close_equi_tab = 0
        #pour ouvrir des ordres autour du dernier ordre clos
        for el in ecart.ECART:
            if abs(last_close-el) < abs(last_close - last_close_equi_tab):
                last_close_equi_tab = el
        key = ecart.ECART.index(last_close_equi_tab)
        #Recuperation de la valeur ecart la plus proche du dernier closed
        if prix < ecart.ECART[key + 1] and prix > ecart.ECART[key - 1]:
            haut = ecart.ECART[key + 1]
            bas = ecart.ECART[key - 1]
        else:
            i=0
            while ecart.ECART[i]<prix:
                i += 1
            haut = ecart.ECART[i]
            bas = ecart.ECART[i-1]
        self.get_bet_achat(bas)
        buy = self.new_order(kraken_key,"XRPEUR","buy","limit",str(bas),str(self.bet))
        
        achat[str(bas)]=str(buy)

        self.get_bet_vente(haut)
        sell = self.new_order(kraken_key,"XRPEUR","sell","limit",str(haut),str(self.bet))
        vente[str(haut)]=str(sell)
        self.ecriture_achat_vente(achat,vente)


    #############################################
    #
    # DESCRIPTION:
    #
    # IN:
    #   -
    # OUT:
    #   -
    #
    #############################################
    #ferme tout les ordres et initialise les fichiers achat et vente
    def flush_zero(self,kraken_key):
        achat={}
        vente={}
        self.ecriture_achat_vente(achat,vente)
        ordres_ouverts = kraken_key.query_private('OpenOrders',{'trades': 'true','start':'1514790000'})
        for el in ordres_ouverts['result']['open'].keys():
            self.order_close(kraken_key,el)


    #############################################
    #
    # DESCRIPTION:
    #
    # IN:
    #   -
    # OUT:
    #   -
    #
    #############################################

    def lecture_achat(self,achat): 
        try:
            fichier_achat=open("LOG/achat.txt",'r')
            achat_tmp= json.load(fichier_achat)
            fichier_achat.close()
        except:
            pass
        achat=achat_tmp
        return achat

    #############################################
    #
    # DESCRIPTION:
    #
    # IN:
    #   -
    # OUT:
    #   -
    #
    #############################################


    def lecture_vente(self,vente): 
        try:
            fichier_vente=open("LOG/vente.txt",'r')
            vente_tmp= json.load(fichier_vente)
            fichier_vente.close()
        except:
            pass
        vente=vente_tmp
        return vente


    #############################################
    #
    # DESCRIPTION:
    #
    # IN:
    #   -
    # OUT:
    #   -
    #
    #############################################

    def ecriture_achat_vente(self,achat,vente):
        fichier_achat=open("LOG/achat.txt",'w')
        fichier_vente=open("LOG/vente.txt",'w')
        json.dump(achat,fichier_achat)
        json.dump(vente,fichier_vente)
        fichier_achat.close()
        fichier_vente.close()

    #############################################
    #
    # DESCRIPTION:
    #
    # IN:
    #   -
    # OUT:
    #   -
    #
    #############################################
   
# sauvegarde le niveau achat et vente pour revenir au meme point en cas de reboot du script
    def ecriture_niveaux(self , niv_achat , niv_vente):
        fichier_niveaux = open("LOG/niveaux.txt",'w')
        dico_niveaux = {"achat":niv_achat,"vente":niv_vente}
        json.dump(dico_niveaux , fichier_niveaux)
        fichier_niveaux.close()


    #############################################
    #
    # DESCRIPTION:
    #
    # IN:
    #   -
    # OUT:
    #   -
    #
    #############################################

#Recuperation du niveau d achat et de vente suite à un redemarrage
    def lecture_niveaux(self):
        try:
            fichier_niveaux = open("LOG/niveaux.txt",'r')
            dico_niveaux = json.load(fichier_niveaux)
            fichier_niveaux.close()
        except:
            dico_niveaux = {"achat": 0 ,"vente": 0 }
        return dico_niveaux




if __name__ == '__main__':
     main()

