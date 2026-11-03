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
                if prix > ORDRES_HAL_OPEN["VENTE"][1] + 0.1 and prix > HAL_VENTE_TAB[ORDRES_HAL_OPEN["POSITION"]] + 0.05:
                    kraken.query_private('CancelOrder', {'txid': ORDRES_HAL_OPEN["VENTE"][0]})
                    sell_SL = basic.new_order_haleving(kraken,"XRPEUR","sell","stop-loss",str(HAL_VENTE_TAB[ORDRES_HAL_OPEN["POSITION"]]),str(172.5 + ORDRES_HAL_OPEN["VENTE"][2]))
                    ORDRES_HAL_OPEN["POSITION"] += 1
                    ORDRES_HAL_OPEN["VENTE"] = sell_SL
                    basic.ecriture_haleving_file(ORDRES_HAL_OPEN)
                if prix > ORDRES_HAL_OPEN["VENTE"][1] + 0.1:
                    kraken.query_private('CancelOrder', {'txid': ORDRES_HAL_OPEN["VENTE"][0]})
                    sell_SL = basic.new_order_haleving(kraken,"XRPEUR","sell","stop-loss",str(float(ORDRES_HAL_OPEN["VENTE"][1])+0.05),str(ORDRES_HAL_OPEN["VENTE"][2]))
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
                if prix < ORDRES_HAL_OPEN["ACHAT"][1] - 0.1 and prix < HAL_VENTE_TAB[ORDRES_HAL_OPEN["POSITION"]-1] - 0.05:
                    kraken.query_private('CancelOrder', {'txid': ORDRES_HAL_OPEN["ACHAT"][0]})
                    buy_SL = basic.new_order_haleving(kraken,"XRPEUR","buy","stop-loss",str(HAL_ACHAT_TAB[ORDRES_HAL_OPEN["POSITION"]-1]),str(172.5+ ORDRES_HAL_OPEN["ACHAT"][2]))
                    ORDRES_HAL_OPEN["POSITION"] -= 1
                    ORDRES_HAL_OPEN["ACHAT"] = buy_SL
                    basic.ecriture_haleving_file(ORDRES_HAL_OPEN)
                if prix < ORDRES_HAL_OPEN["ACHAT"][1] - 0.1:
                    kraken.query_private('CancelOrder', {'txid': ORDRES_HAL_OPEN["ACHAT"][0]})
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


                prem_step = 185
                largeur = 3
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

            try:
                prix = basic.latest_price(kraken,"XRPEUR")
                time.sleep(2)

                dico_orders={}
                dico_orders[vente[str(haut)]] = {"niveau":count_vente,"ecart":basic.ecart}
                dico_orders[achat[str(bas)]] = {"niveau":count_vente,"ecart":basic.ecart}
                if ORDRES_HAL_OPEN["ACHAT"] == [] and ORDRES_HAL_OPEN["VENTE"] == []:
                    return_status = basic.orders_status(kraken,dico_orders)
                elif ORDRES_HAL_OPEN["ACHAT"] != []:
                    return_status = basic.orders_status(kraken,dico_orders,ORDRES_HAL_OPEN["ACHAT"])
                elif ORDRES_HAL_OPEN["VENTE"] != []:
                    return_status = basic.orders_status(kraken,dico_orders,ORDRES_HAL_OPEN["VENTE"])


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









if __name__ == '__main__':
     main()
