import krakenex
import time
import os
import json
import telebot
import datetime
import importlib

import bet
import parameters
import ecart
import haleving

ECART         = parameters.ECART
MONTANT_ACHAT = parameters.MONTANT_ACHAT
#TO REMOVE
DICO_BET      = parameters.DICO_BET
#################
BET_TAB = bet.BET

#Token pour le bot telegram
TELEG_TOKEN = parameters.TELEGRAM_TOKEN
#Id du chat pour le BOT telegram
BOT_CHAT_ID = parameters.TELEGRAM_CHAT_ID
HAL_ACHAT_TAB = [0.6,0.8,1.0,1.2,1.4,1.6,1.8,2.0,2.2,2.4,2.6]
HAL_VENTE_TAB = [0.9,1.1,1.3,1.5,1.7,1.9,2.1,2.3,2.5,2.7,2.9]
ORDRES_HAL_OPEN = haleving.H_ORDER


VERSION="3.0"

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
        Ack1=False



                #ouvrir un stop loss
        return_status={}

        while 1:
            passage_haut = False
            passage_bas = False
            #Envoi d informations quotidienne
            last_ben_line = basic.benef_last_line_get_benef()

            ##############################################################
            #                      HALEVING gestion                      #
            ##############################################################
            montant_haleving_vente=172.5
            if ORDRES_HAL_OPEN["ACHAT"] == [] and ORDRES_HAL_OPEN["VENTE"] == []:
                if ORDRES_HAL_OPEN["POSITION"] == 0:
                    if prix > HAL_VENTE_TAB[0] + 0.05:
                        sell_SL = basic.new_order_haleving(kraken,"XRPEUR","sell","stop-loss",str(HAL_VENTE_TAB[0]),str(montant_haleving_vente))
                        ORDRES_HAL_OPEN["VENTE"] = sell_SL
                        ORDRES_HAL_OPEN["POSITION"] = 1
                        basic.ecriture_haleving_file(ORDRES_HAL_OPEN)
                elif ORDRES_HAL_OPEN["POSITION"] == 11:
                    if prix < HAL_ACHAT_TAB[10] - 0.05:
                        buy_SL = basic.new_order_haleving(kraken,"XRPEUR","buy","stop-loss",str(HAL_ACHAT_TAB[10]),str(172.5))
                        ORDRES_HAL_OPEN["ACHAT"] = buy_SL
                        ORDRES_HAL_OPEN["POSITION"] = 10
                        basic.ecriture_haleving_file(ORDRES_HAL_OPEN)
                elif prix > HAL_VENTE_TAB[ORDRES_HAL_OPEN["POSITION"]] + 0.05:
                    ORDRES_HAL_OPEN["POSITION"] += 1
                    sell_SL = basic.new_order_haleving(kraken,"XRPEUR","sell","stop-loss",str(HAL_VENTE_TAB[ORDRES_HAL_OPEN["POSITION"]]),str(172.5))
                    ORDRES_HAL_OPEN["VENTE"] = sell_SL

                    basic.ecriture_haleving_file(ORDRES_HAL_OPEN)
                elif prix < HAL_ACHAT_TAB[ORDRES_HAL_OPEN["POSITION"]-1]:
                    buy_SL = basic.new_order_haleving(kraken,"XRPEUR","buy","stop-loss",str(HAL_ACHAT_TAB[ORDRES_HAL_OPEN["POSITION"]-1]),str(172.5))
                    ORDRES_HAL_OPEN["ACHAT"] = buy_SL
                    ORDRES_HAL_OPEN["POSITION"] -= 1
                    basic.ecriture_haleving_file(ORDRES_HAL_OPEN)
            if ORDRES_HAL_OPEN["VENTE"] != []:
                try:
                    if return_status[ORDRES_HAL_OPEN["VENTE"][0]] == "closed":
                        basic.haleving_bet_modification("VENTE",ORDRES_HAL_OPEN["ACHAT"][1],ORDRES_HAL_OPEN["ACHAT"][2])
                        ORDRES_HAL_OPEN["VENTE"]=[]
                        basic.ecriture_haleving_file(ORDRES_HAL_OPEN)
                except:
                    bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
                    bot.send_message(BOT_CHAT_ID, 'probleme de recuperation du status VENTE')
                if prix > HAL_OPEN["VENTE"][1] + 0.1 and prix > HAL_VENTE_TAB[ORDRES_HAL_OPEN["POSITION"]] + 0.05:
                    kraken.query_private('CancelOrder', {'txid': HAL_OPEN["VENTE"][0]})
                    sell_SL = basic.new_order_haleving(kraken,"XRPEUR","sell","stop-loss",str(HAL_VENTE_TAB[ORDRES_HAL_OPEN["POSITION"]]),str(172.5 + HAL_OPEN["VENTE"][2]))
                    ORDRES_HAL_OPEN["POSITION"] += 1
                    ORDRES_HAL_OPEN["VENTE"] = sell_SL
                    basic.ecriture_haleving_file(ORDRES_HAL_OPEN)
                if prix > HAL_OPEN["VENTE"][1] + 0.1:
                    kraken.query_private('CancelOrder', {'txid': HAL_OPEN["VENTE"][0]})
                    sell_SL = basic.new_order_haleving(kraken,"XRPEUR","sell","stop-loss",str(float(ORDRES_HAL_OPEN["VENTE"][1])+0.05),str(HAL_OPEN["VENTE"][2]))
                    ORDRES_HAL_OPEN["VENTE"] = sell_SL
                    basic.ecriture_haleving_file(ORDRES_HAL_OPEN)
            if ORDRES_HAL_OPEN["ACHAT"] != []:
                try:
                    if return_status[ORDRES_HAL_OPEN["ACHAT"][0]] == "closed":
                        basic.haleving_bet_modification("ACHAT",ORDRES_HAL_OPEN["ACHAT"][1],ORDRES_HAL_OPEN["ACHAT"][2])
                        ORDRES_HAL_OPEN["ACHAT"]=[]
                        basic.ecriture_haleving_file(ORDRES_HAL_OPEN)
                except:
                    bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
                    bot.send_message(BOT_CHAT_ID, 'probleme de recuperation du status ACHAT')
                if prix < HAL_OPEN["ACHAT"][1] - 0.1 and prix < HAL_VENTE_TAB[ORDRES_HAL_OPEN["POSITION"]-1] - 0.05:
                    kraken.query_private('CancelOrder', {'txid': HAL_OPEN["ACHAT"][0]})
                    buy_SL = basic.new_order_haleving(kraken,"XRPEUR","buy","stop-loss",str(HAL_ACHAT_TAB[ORDRES_HAL_OPEN["POSITION"]-1]),str(172.5+ HAL_OPEN["ACHAT"][2]))
                    ORDRES_HAL_OPEN["POSITION"] -= 1
                    ORDRES_HAL_OPEN["ACHAT"] = buy_SL
                    basic.ecriture_haleving_file(ORDRES_HAL_OPEN)
                if prix < HAL_OPEN["ACHAT"][1] - 0.1:
                    kraken.query_private('CancelOrder', {'txid': HAL_OPEN["ACHAT"][0]})
                    buy_SL = basic.new_order_haleving(kraken,"XRPEUR","buy","stop-loss",str(float(ORDRES_HAL_OPEN["ACHAT"][1])-0.05),str(HAL_OPEN["VENTE"][2]))
                    ORDRES_HAL_OPEN["ACHAT"] = buy_SL
                    basic.ecriture_haleving_file(ORDRES_HAL_OPEN)











            if "trait" in last_ben_line:
                local = float(last_ben_line[4])
                up_invest = float(last_ben_line[5])
                last_close = float(os.popen("cat LOG/*log|grep closed|tail -n 1").readlines()[0].split(";")[4])
            #    last_close = float(os.system("cat LOG/*log|grep closed|tail -n 1").readlines()[0].split(";")[4])
                prev_dif = abs(last_close-ecart.ECART[0])
                for el in ecart.ECART:
                    if abs(last_close - el) < prev_dif:
                        prev_dif=abs(last_close - el)
                        prev_el = el
                key_last_close= ecart.ECART.index(prev_el)
                Ack1=True
                cmd = "echo 'ACK1;local "+str(local)+" up "+str(up_invest)+" last_close "+str(last_close)+" indice "+str(key_last_close)+"' >> benef.log"
                os.system(cmd)

                bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
                bot.send_message(BOT_CHAT_ID, 'Last close : '+ str(last_close)+'\nLocal : '+ str(local) + '\nUP : '+ str(up_invest))

                BET_TAB[key_last_close-2]=BET_TAB[key_last_close-2]+(local/5)/last_close
                BET_TAB[key_last_close-1]=BET_TAB[key_last_close-1]+(local/5)/last_close
                BET_TAB[key_last_close]=BET_TAB[key_last_close]+(local/5)/last_close
                BET_TAB[key_last_close+1]=BET_TAB[key_last_close+1]+(local/5)/last_close
                BET_TAB[key_last_close+2]=BET_TAB[key_last_close+2]+(local/5)/last_close


                prem_step = 259
                largeur = 5
                for i in range(largeur):
                    BET_TAB[prem_step+i]=BET_TAB[prem_step+i]+(up_invest/largeur)/last_close
                cmd = "echo 'BET = "+str(BET_TAB)+"' > bet.py"

                count_achat = 0
                count_vente = 0

                os.system(cmd)
                basic.flush_zero(kraken,ORDRES_HAL_OPEN)
                achat={}
                vente={}

                haut=ecart.ECART[key_last_close+1]
                bas=ecart.ECART[key_last_close-1]
                basic.get_bet_achat(ecart.ECART[key_last_close-1])

                buy = basic.new_order(kraken,"XRPEUR","buy","limit",str(bas),str(basic.bet + up_invest/last_close + 2*local/5/last_close))  #### TODO montant du bet a regler
                achat[str(ecart.ECART[key_last_close-1])]=str(buy)
                    #basic.get_bet_achat(bas)
                    #buy = basic.new_order(kraken,"XRPEUR","buy","limit",str(bas),str(basic.bet+delta_achat_niveau))

                basic.get_bet_vente(ecart.ECART[key_last_close+1])
                buy = basic.new_order(kraken,"XRPEUR","sell","limit",str(haut),str(basic.bet - up_invest/last_close - 2*local/5/last_close)) #### TODO montant du bet a regler

                vente[str(ecart.ECART[key_last_close+1])]=str(buy)
                basic.ecriture_achat_vente(achat,vente)



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
                if HAL_OPEN["ACHAT"] == [] and HAL_OPEN["VENTE"] == []:
                    return_status = basic.orders_status(kraken,dico_orders)
                elif HAL_OPEN["ACHAT"] != []:
                    return_status = basic.orders_status(kraken,dico_orders,HAL_OPEN["ACHAT"])
                elif HAL_OPEN["VENTE"] != []:
                    return_status = basic.orders_status(kraken,dico_orders,HAL_OPEN["VENTE"])

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
                last_ben_line = basic.benef_last_line_get_benef()


                if (passage_bas or passage_haut) and "ACK1" in last_ben_line:
                    cmd = "echo 'ACK2;' >> benef.log"
                    os.system(cmd)
                if (passage_bas and not passage_haut) and "ACK2" in last_ben_line:
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
                        basic.flush_zero(kraken,ORDRES_HAL_OPEN)
                    elif count_achat == 1:
                        bas=ecart.ECART[i-2]
                        count_achat +=1
                        count_vente=0
                        haut=ecart.ECART[i+1]
                        basic.get_bet_achat(ecart.ECART[i-1])
                        delta_achat_niveau = basic.bet
                        delta_vente_niveau=0
                        achat={}
                        vente={}
                        basic.flush_zero(kraken,ORDRES_HAL_OPEN)
                    else:
                        bas=ecart.ECART[i-3]
                        count_achat +=1
                        count_vente=0
                        delta_vente_niveau=0
                        haut=ecart.ECART[i+1]
                        basic.get_bet_achat(ecart.ECART[i-1])
                        delta_achat_niveau = basic.bet
                        basic.get_bet_achat(ecart.ECART[i-2])
                        delta_achat_niveau += basic.bet
                        achat={}
                        vente={}
                        basic.flush_zero(kraken,ORDRES_HAL_OPEN)
                    ####attention l'achat existe peut etre deja ####################
                    #TODO Verifier si ce IF est bien necessaire
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
                if (passage_haut and not passage_bas) and "ACK2" in last_ben_line:
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
                        basic.flush_zero(kraken,ORDRES_HAL_OPEN)
                    elif count_vente == 1:
                        delta_achat_niveau=0
                        haut=ecart.ECART[i+2]
                        bas=ecart.ECART[i-1]
                        count_achat=0
                        count_vente+=1
                        basic.get_bet_vente(ecart.ECART[i+1])
                        delta_vente_niveau = basic.bet
                        achat={}
                        vente={}
                        basic.flush_zero(kraken,ORDRES_HAL_OPEN)
                    else:
                        delta_achat_niveau=0
                        haut=ecart.ECART[i+3]
                        bas=ecart.ECART[i-1]
                        count_achat=0
                        count_vente+=1
                        basic.get_bet_vente(ecart.ECART[i+1])
                        delta_vente_niveau = basic.bet
                        basic.get_bet_vente(ecart.ECART[i+2])
                        delta_vente_niveau += basic.bet
                        achat={}
                        vente={}
                        basic.flush_zero(kraken,ORDRES_HAL_OPEN)
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
            try:
                #Cas particulier: si une vente et achat sont clos en même temps
                if (passage_haut and passage_bas) and "ACK2" in last_ben_line:
                    bot.send_message(BOT_CHAT_ID, 'Achat et vente at the same time \nPOINT d attention particulier!!!')
                    i_bas=0
                    while bas > ecart.ECART[i_bas]:
                        i_bas += 1
                    i_haut=0
                    while haut > ecart.ECART[i_haut]:
                        i_haut += 1
                    bas=ecart.ECART[i_bas-1]
                    haut=ecart.ECART[i_haut+1]

                    if count_vente<2 and count_achat <2:
                        basic.get_bet_achat(ecart.ECART[i_bas+1])
                        delta_achat_niveau=basic.bet
                        basic.get_bet_vente(ecart.ECART[i_bas+1])
                        delta_vente_niveau=basic.bet
                    elif count_vente == 2 and count_achat < 2:
                        #Achat
                        basic.get_bet_achat(ecart.ECART[i_bas+1])
                        delta_achat_niveau=basic.bet
                        basic.get_bet_achat(ecart.ECART[i_bas+2])
                        delta_achat_niveau+=basic.bet
                        #Vente
                        basic.get_bet_vente(ecart.ECART[i_bas+1])
                        delta_vente_niveau=basic.bet
                    elif count_vente > 2 and count_achat < 2:
                        #Achat
                        basic.get_bet_achat(ecart.ECART[i_bas+1])
                        delta_achat_niveau=basic.bet
                        basic.get_bet_achat(ecart.ECART[i_bas+2])
                        delta_achat_niveau+=basic.bet
                        basic.get_bet_achat(ecart.ECART[i_bas+3])
                        delta_achat_niveau+=basic.bet
                        #Vente
                        basic.get_bet_vente(ecart.ECART[i_bas+1])
                        delta_vente_niveau=basic.bet
                    elif count_vente < 2 and count_achat == 2:
                        #Achat
                        basic.get_bet_achat(ecart.ECART[i_bas+1])
                        delta_achat_niveau=basic.bet
                        #Vente
                        basic.get_bet_vente(ecart.ECART[i_bas+1])
                        delta_vente_niveau=basic.bet
                        basic.get_bet_vente(ecart.ECART[i_bas+2])
                        delta_vente_niveau+=basic.bet
                    elif count_vente < 2 and count_achat > 2:
                        #Achat
                        basic.get_bet_achat(ecart.ECART[i_bas+1])
                        delta_achat_niveau=basic.bet
                        #Vente
                        basic.get_bet_vente(ecart.ECART[i_bas+1])
                        delta_vente_niveau=basic.bet
                        basic.get_bet_vente(ecart.ECART[i_bas+2])
                        delta_vente_niveau+=basic.bet
                        basic.get_bet_vente(ecart.ECART[i_bas+3])
                        delta_vente_niveau+=basic.bet
                    else:
                        bot.send_message(BOT_CHAT_ID, 'On ne devrait pas arriver jusqu ici')

                    count_vente = 0
                    count_achat = 0

                    buy = basic.new_order(kraken,"XRPEUR","buy","limit",str(bas),str(basic.bet+delta_achat_niveau))
                    achat[str(bas)]=str(buy)
                    sell = basic.new_order(kraken,"XRPEUR","sell","limit",str(haut),str(basic.bet+delta_vente_niveau ))
                    vente[str(haut)]=str(sell)
                    basic.ecriture_niveaux(count_achat=0 , count_vente=0)
                    basic.ecriture_achat_vente(achat,vente)
            except Exception as inst:
                cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";CRASH APPLI WAAAAAAAAAAAAAAAAAAAAAA C ICI: ' >> LOG/ERROR.error"
                os.system(cmd)
                bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
                bot.send_message(BOT_CHAT_ID, 'check tes logs, t as une piste (dans le gros IF avec la double fermeture)')

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


    def orders_status(self,kraken, dico_orders,dico_haleving=[]):
        #order_id,niveau,montant,ecart):
        list_id_orders = list(dico_orders.keys())
        if dico_haleving != []:
            list_id_orders.append(dico_haleving[0])
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
        try:
            close=0
            result = kraken.query_private('CancelOrder', {'txid': order_id})
            close=1

            #Bug régulièrement provoqué par un result vide
            result={}
            loop=0
            while result=={} and loop <10:
                #verifie que l'ordre clos a ete execute partiellement et si il a ete partiellement execute, il integre dans les logs le volume execute
                partial_execute = kraken.query_private('QueryOrders', {'txid': order_id})
                result=partial_execute['result']
                if result=={}:
                    bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
                    bot.send_message(BOT_CHAT_ID, 'Je n ai pas de report renvoye c est pas bon')
                    bot.send_message(BOT_CHAT_ID, 'loop value: '+ str(loop))
                    time.sleep(5)
                    loop+=1
            close=2
            if float(partial_execute['result'][order_id]['vol_exec']) == 0:
                close=3
                cmd="echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";cancel;;;;;"+ order_id +";;;;;;;;' >> LOG/"+time.strftime('%Y#%m#%d')+".log"
                os.system(cmd)
                close=4
            else:
                close=5
                volume = partial_execute['result'][order_id]['vol_exec']
                prix = partial_execute['result'][order_id]['price']
                frais = partial_execute['result'][order_id]['fee']
                type_B_S = partial_execute['result'][order_id]['descr']['type']
                close=6
                cmd="echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";closed;"+type_B_S+";"+prix+";"+ volume +";"+frais+";"+ order_id +";"+str(partial_execute['error'])+"__partialy_closed;;;;;;;"+"' >> LOG/"+time.strftime('%Y#%m#%d')+".log"
                os.system(cmd)
                close=7
                #Envoi un message sur telegram en cas d ordre partiellement clos
                #bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
                #bot.send_message(BOT_CHAT_ID, 'ORDRE PARTIEL VOLUME : ' + str(volume) + ' PRIX : ' + str(prix))

                #ouvre un ordre au prix du marche pour contrebalancer l ordre partiellement clos, cela permet de conserver le prix d equilibre
                ID_partial = ""
                close=8
                if type_B_S == "buy":
                    ID_partial = self.new_order(kraken,"XRPEUR","sell","market",prix,volume)
                else:
                    ID_partial = self.new_order(kraken,"XRPEUR","buy","market",prix,volume)
                close=9

                time.sleep(2)
                #Appel de la fonction pour effectuer le log de l ordre, l ordre est obligatoirement clos car c est un ordre market qui doit etre execute immediatement
                self.order_status(kraken, ID_partial,"NA",volume,"")
                close=10
        except:
            bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
            bot.send_message(BOT_CHAT_ID, 'order close ' +str(close))
            bot.send_message(BOT_CHAT_ID,"result request fail : "+str(partial_execute))
            time.sleep(10)
            ferme_ou_pas = kraken.query_private('QueryOrders', {'txid': order_id})
            bot.send_message(BOT_CHAT_ID,"status de l ordre apres tentative de close : "+str(ferme_ou_pas))
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
        key_ecart= ecart.ECART.index(price)
        #self.get_bet_base(ecart.ECART[key_ecart + 1])
        self.bet = BET_TAB[key_ecart + 1]
        if self.flag_bet_changement != self.bet:
            self.flag_bet_changement = self.bet

    def get_bet_vente(self,price):
        key_ecart= ecart.ECART.index(price)
        #self.get_bet_base(float(price))
        self.bet = BET_TAB[key_ecart]
        if self.flag_bet_changement != self.bet:
            #Envoi un message sur telegram pour changement de montant du bet
            bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
            #bot.send_message(BOT_CHAT_ID, 'CHANGEMENT du bet : ' + str(self.flag_bet_changement) + " vers "+str(self.bet) )
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
            if ordres_ouverts['result']['open'][el]['descr']['pair']=='XRPEUR':
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
    def flush_zero(self,kraken_key,haleving_tab):
        count=0
        try:
            count=1
            achat={}
            vente={}
            self.ecriture_achat_vente(achat,vente)
            count=2
            ordres_ouverts = kraken_key.query_private('OpenOrders',{'trades': 'true','start':'1514790000'})
            count=3
        except:
            bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
            bot.send_message(BOT_CHAT_ID, 'Problème dans le flunch count : ' +str(count))
        #bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
        #bot.send_message(BOT_CHAT_ID, 'result of query : '+ str(ordres_ouverts['result']))
        for el in ordres_ouverts['result']['open'].keys():
            if ordres_ouverts['result']['open'][el]['descr']['pair']=='XRPEUR':
                bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
                bot.send_message(BOT_CHAT_ID, 'On entre dans le flush : ' +str(haleving_tab))
                if haleving_tab["ACHAT"] != [] and haleving_tab["VENTE"] != []:
                    bot.send_message(BOT_CHAT_ID, 'On ne passe pas ici')
                    if el !=  haleving_tab["ACHAT"][0] and el !=  haleving_tab["VENTE"][0]:
                        self.order_close(kraken_key,el)
                elif haleving_tab["ACHAT"] == [] and haleving_tab["VENTE"] != []:
                    bot.send_message(BOT_CHAT_ID, 'On ne passe pas ici non plus')
                    if el !=  haleving_tab["VENTE"][0]:
                        self.order_close(kraken_key,el)
                elif haleving_tab["ACHAT"] != [] and haleving_tab["VENTE"] == []:
                    bot.send_message(BOT_CHAT_ID, 'La non plus')
                    if el !=  haleving_tab["ACHAT"][0]:
                        self.order_close(kraken_key,el)
                elif haleving_tab["ACHAT"] == [] and haleving_tab["VENTE"] == []:
                    bot.send_message(BOT_CHAT_ID, 'Par contre on devrait passer ici')
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

    def benef_last_line_get_benef(self):
        return os.popen("cat benef.log|tail -n 1").readlines()[0].split(";")

    def ecriture_haleving_file(self, h_order):
        cmd = "echo 'BET_TAB = "+str(h_order)+"' > haleving.py"
        os.system(cmd)


    def ecriture_haleving_file(self,h_order):
        cmd = 'echo "H_ORDER = '+str(h_order)+'" > haleving.py'
        os.system(cmd)

    def haleving_bet_modification(self,sens,prix,montant):
        prem_step_reserve = 533
        largeur_reserve = 23
        largeur_euros_reserve = 40
        montant_euro = float(prix) * float(montant)
        somme_reserve_basse = 3.022
        if sens == "VENTE":
            for i in range(largeur_reserve):
                BET_TAB[prem_step_reserve+i]=BET_TAB[prem_step_reserve+i]-(float(montant)/float(largeur_reserve))
            for i in range(largeur_euros_reserve):
                BET_TAB[i]=BET_TAB[i]+(montant_euro/somme_reserve_basse)
        if sens == "ACHAT":
            for i in range(largeur_reserve):
                BET_TAB[prem_step_reserve+i]=BET_TAB[prem_step_reserve+i]+(float(montant)/float(largeur_reserve))
            for i in range(largeur_euros_reserve):
                BET_TAB[i]=BET_TAB[i]-(montant_euro/somme_reserve_basse)


        cmd = "echo 'BET = "+str(BET_TAB)+"' > bet.py"






if __name__ == '__main__':
     main()
