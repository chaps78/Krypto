import krakenex
import time
import os
import parameters
import json
import telebot


ECART = parameters.ECART
MONTANT_ACHAT = parameters.MONTANT_ACHAT
MONTANT_VENTE = parameters.MONTANT_VENTE
FIBO          = MONTANT_VENTE

#Token pour le bot telegram
TELEG_TOKEN = parameters.TELEGRAM_TOKEN
#Id du chat pour le BOT telegram
BOT_CHAT_ID = parameters.TELEGRAM_CHAT_ID



VERSION="1.6"

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
        print("entree dans le thread")
        kraken = krakenex.API()
        kraken.load_key('kraken.key')
        basic = basics()

        achat={}
        vente={}

        achat = basic.lecture_achat(achat) 
        vente = basic.lecture_vente(vente) 


        #Recuperation des niveaux de vente et d achat
        dico_niv = basic.lecture_niveaux()
        count_vente = dico_niv["vente"]
        count_achat = dico_niv["achat"]
        delta_achat_niveau=0
        delta_vente_niveau=0


        try:
            prix = basic.latest_price(kraken,"XRPEUR")
        except:
            print("On relance la machine 1 "+time.strftime(' %H:%M:%S'))

       
        ordres_ouverts = kraken.query_private('OpenOrders',{'trades': 'true','start':'1514790000'})
        try:
            print(str(ordres_ouverts['result']['open'].keys()))
 
            #verification de la synchro entre kraken et les listes
            verif_OK = basic.verif(achat,vente,ordres_ouverts)
        except KeyError:
            print("ERROR key")
            verif_OK = False
        if verif_OK == False or (achat == {} and vente == {}):
            #supprime l'ensemble des ordres et cree 2 nouveaux ordres pour partir sur de nouvelles bases
            basic.flush(ordres_ouverts,kraken,achat,vente,prix)
            achat = basic.lecture_achat(achat) 
            vente = basic.lecture_vente(vente) 

        



        bas = float(max(achat.keys()))
        haut = float(min(vente.keys()))
        print("BAS  : "+ str(bas))
        print("HAUT : "+ str(haut))

        time.sleep(self.TIME_SLEEP)

        while 1:
            passage_haut = False
            passage_bas = False
            try:
                prix = basic.latest_price(kraken,"XRPEUR")
                time.sleep(2)
                niveau = dico_orders[order_id]["niveau"]
                montant = dico_orders[order_id]["montant"]
                ecart = dico_orders[order_id]["ecart"]


                dico_orders = {vente[str(haut)]:{"niveau":count_vente,"montant":MONTANT_ACHAT,"ecart":basic.ecart}}
                dico_orders = {achat[str(bas)]:{"niveau":count_vente,"montant":MONTANT_ACHAT,"ecart":basic.ecart}}

                return_status = basic.orders_status(kraken,dico_orders)
                passage_haut = return_status[vente[str(haut)]] == 'closed'
                passage_bas = return_status[achat[str(bas)]] == 'closed'


            except KeyboardInterrupt:
                print("ctrl + C")
                break
            except:
                passage_bas=False
                passage_haut=False
                cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";CRASH APPLI dans le while vente c est ici le probleme: ' >> LOG/ERROR.error"
                os.system(cmd)
                cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";CRASH APPLI dans le while vente: "+str(vente)+";"+"achat"+str(achat)+";prix"+str(prix)+";bas"+str(bas)+";haut"+str(haut)+"' >> LOG/ERROR.error"
                os.system(cmd)

            try:
                if passage_bas:
                    print(str(time.strftime('%Y#%m#%d;%H:%M:%S')))
                    del achat[str(bas)]
                    if count_achat == 0:
                        bas=round(bas-basic.ecart,4)
                        count_achat +=1
                        count_vente=0
                        haut=round(bas+2*basic.ecart,4)
                        delta_achat_niveau=0
                        delta_vente_niveau=0
                        achat={}
                        vente={}
                        basic.flush_zero(kraken)
                        print("Niveau 1")
                    elif count_achat == 1:
                        bas=round(bas-2*basic.ecart,4)
                        count_achat +=1
                        count_vente=0
                        haut=round(bas+3*basic.ecart,4)
                        delta_achat_niveau=FIBO
                        delta_vente_niveau=0
                        achat={}
                        vente={}
                        basic.flush_zero(kraken)
                        print("Niveau 2")
                    else:
                        bas=round(bas-3*basic.ecart,4)
                        count_achat +=1
                        count_vente=0
                        haut=round(bas+4*basic.ecart,4)
                        delta_achat_niveau=2*FIBO
                        achat={}
                        vente={}
                        basic.flush_zero(kraken)
                        print("Niveau 3")
                    ####attention l'achat existe peut etre deja ####################
                    if not str(bas) in achat.keys():
                        buy = basic.new_order(kraken,"XRPEUR","buy","limit",str(bas),str(MONTANT_ACHAT+delta_achat_niveau))
                        #print(str(buy))
                        achat[str(bas)]=str(buy)
                    else:
                        print("l'achat est deja dans le dictionnaire")
                    buy = basic.new_order(kraken,"XRPEUR","sell","limit",str(haut),str(MONTANT_VENTE ))
                    #print(str(buy))
                    vente[str(haut)]=str(buy)
                

                    #Enregistrement du niveau achat_vente pour revenir au meme etat en cas de redemarrage
                    basic.ecriture_niveaux(count_achat , count_vente)
                    #Enregistrement des ordres d achat et vente qui viennent d etre passe
                    basic.ecriture_achat_vente(achat,vente)



                if passage_haut:
                    print(str(time.strftime('%Y#%m#%d;%H:%M:%S')))
                    del vente[str(haut)]
                    if count_vente == 0:
                        haut=round(haut+basic.ecart,4)
                        bas=round(haut-2*basic.ecart,4)
                        count_achat=0
                        count_vente+=1
                        delta_achat_niveau=0
                        delta_vente_niveau=0
                        achat={}
                        vente={}
                        basic.flush_zero(kraken)
                        print("Niveau 1")
                    elif count_vente == 1:
                        haut=round(haut+2*basic.ecart,4)
                        bas=round(haut-3*basic.ecart,4)
                        count_achat=0
                        count_vente+=1
                        delta_achat_niveau=0
                        delta_vente_niveau=FIBO
                        achat={}
                        vente={}
                        basic.flush_zero(kraken)
                        print("Niveau 2")
                    else:
                        haut=round(haut+3*basic.ecart,4)
                        bas=round(haut-4*basic.ecart,4)
                        count_achat=0
                        count_vente+=1
                        delta_achat_niveau=0
                        delta_vente_niveau=2*FIBO
                        achat={}
                        vente={}
                        basic.flush_zero(kraken)
                        print("Niveau 3")
                    buy = basic.new_order(kraken,"XRPEUR","buy","limit",str(bas),str(MONTANT_ACHAT ))
                    #print(str(buy))
                    achat[str(bas)]=str(buy)




                    ######        Attention la vente existe peut etre deja
                    if not str(haut) in vente.keys():
                        buy = basic.new_order(kraken,"XRPEUR","sell","limit",str(haut),str(MONTANT_VENTE + delta_vente_niveau ))
                        vente[str(haut)]=str(buy)


                    #Enregistrement du niveau achat_vente pour revenir au meme etat en cas de redemarrage
                    basic.ecriture_niveaux(count_achat , count_vente)
                    #Enregistrement des ordres d achat et vente qui viennent d etre passe
                    basic.ecriture_achat_vente(achat,vente)

            except:
                cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";" + str(response) + "Probleme dans les IF"+str(passage_bas)+";"+str(passage_haut)+";"+str(prix)+"' >> LOG/ERROR.error"

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
            print("PROBLEME D'OUVERTURE D'ORDRE")
            cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";" + str(response) + "ouverture ordre 1' >> LOG/ERROR.error"
            os.system(cmd)
        try:
            print(str(response['result']))
        except:
            print("Erreur (surement une evolution trop brutale) : \n" + str(response['error']))
            cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";" + str(response) + "ouverture ordre 2' >> LOG/ERROR.error"
            os.system(cmd)
        if(response['error']!=[]):
            cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";l erreur d ouverture d ordre est la suivante;" + str(response['error']) + "ouverture ordre 4' >> LOG/ERROR.error"
            os.system(cmd)
        if(response['error']==['EOrder:Insufficient funds']):
            print("pas assez d'argent pour " + type_B_S)
            return -1

        ID=""
        try:
            ID=str(response['result']['txid'][0])
            if len(response['result']['txid'])>1:
                print("Plusieurs Ordres ouvert !!!!!!!!!!!!!!!!!!!!!!!")
                print(str(response['result']['txid'][0]))
        except:
            print("resultat non present dans lordre")
            print("Erreur (surement une evolution trop brutale) : \n" + str(response['error']))
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
        result = kraken.query_private('QueryOrders', {'txid': list_id_orders})
        return_value = {}
        for order_id in list_id_orders:
            ret = result['result'][order_id]['status']
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
                montant = dico_orders[order_id]["montant"]
                ecart = dico_orders[order_id]["ecart"]

                cmd="echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";"+ret+";"+type_B_S+";"+prix+";"+ volume +";"+frais+";"+ order_id +";"+str(result['error'])+";"+str(montant)+";;"+str(niveau)+";"+str(ecart)+";"+ euros +";"+xrp+";"+"' >> LOG/"+time.strftime('%Y#%m#%d')+".log"
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
            bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
            bot.send_message(BOT_CHAT_ID, 'ORDRE PARTIEL VOLUME : ' + str(volume) + ' PRIX : ' + str(prix))

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
                print("Probleme de synchro : " + achat[key])
                verif_OK=False

        li_verif=vente.keys()
        for key in li_verif:
            if not vente[key] in response['result']['open'].keys():
                print("Probleme de synchro : " + vente[key])
                verif_OK=False

        if not (len(achat.keys())+len(vente.keys())) == len(response['result']['open'].keys()):
            verif_OK=False

        if verif_OK:
            print("Bonne synchro entre KRAKEN et mes listes")
        else:
            print("!!!!!MAUVAISE SYNCHRO KRAKEN ET PYTHON!!!!!")
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
        bas=round(prix_cour - prix_cour%self.ecart,3)
        haut=round(bas + self.ecart,3)
        buy = self.new_order(kraken_key,"XRPEUR","buy","limit",str(bas),MONTANT_ACHAT)
        print(str(buy))
        
        achat[str(bas)]=str(buy)

        sell = self.new_order(kraken_key,"XRPEUR","sell","limit",str(haut),MONTANT_VENTE)
        print(str(sell))
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
        print("LOG/achat.txt : \n"+str(achat))
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
        print("LOG/vente.txt : \n"+str(vente))
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
