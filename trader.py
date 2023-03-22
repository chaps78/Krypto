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


VERSION="1.17"

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
/bin/bash: N$ : commande introuvable
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

