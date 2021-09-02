import krakenex
import time
import os
from threading import Thread
from random import randint
import socket
import parameters
import json



ECART = parameters.ECART
MONTANT_ACHAT = parameters.MONTANT_ACHAT
MONTANT_VENTE = parameters.MONTANT_VENTE
PSEUDO_FIBO = parameters.PSEUDO_FIBO

def main():

    thread=eval(ECART)
    thread.run()

class eval(Thread):

    def __init__(self,ecart):
        Thread.__init__(self)
        self.ecart=ecart
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
 
            #print("achat.txt : \n"+str(achat))
            #print("vente.txt : \n"+str(vente))

            #verification de la synchro entre kraken et les listes
            verif_OK = basic.verif(achat,vente,ordres_ouverts)
        except KeyError:
            print("ERROR key")
            verif_OK = False
        if verif_OK == False or (achat == {} and vente == {}):
            #supprime l'ensemble des ordres et créé 2 nouveaux ordres pour partir sur de nouvelles bases
            basic.flush(ordres_ouverts,kraken,achat,vente,prix)
            achat = basic.lecture_achat(achat) 
            vente = basic.lecture_vente(vente) 

        



        bas = float(max(achat.keys()))
        haut = float(min(vente.keys()))
        print("BAS  : "+ str(bas))
        print("HAUT : "+ str(haut))

        time.sleep(self.TIME_SLEEP)
        delta_achat_desh=0
        delta_vente_desh=0
        flag_achat_desh=-1
        flag_vente_desh=-1

        while 1:
            passage_haut = False
            passage_bas = False
            try:
                prix = basic.latest_price(kraken,"XRPEUR")
                time.sleep(1)
                #if permettant de gérer si un achat n'a pas eu suffisement de fonds
                if(vente[str(haut)] == "-1"):
                    if prix > haut:
                        print("Les caisses sont vides pour une vente mais on se lance quand même")
                        passage_haut = True
                        flag_achat_desh=10
                else:
                    #Cas nominal
                    passage_haut = basic.order_status(kraken,vente[str(haut)],count_vente,MONTANT_ACHAT,PSEUDO_FIBO,ECART)=='closed'
                    if flag_vente_desh>-1:
                        flag_vente-=1
                time.sleep(1)
                #if permettant de gérer si une vente n'a pas eu suffisement de fonds
                if(achat[str(bas)] == "-1"):
                    if prix < bas:
                        print("Les caisses sont vides pour un achat mais on se lance quand même")
                        passage_bas = True
                        flag_vente_desh=10
                else:
                    #Cas nominal
                    passage_bas = basic.order_status(kraken,achat[str(bas)],count_achat,MONTANT_ACHAT,PSEUDO_FIBO,ECART)=='closed'
                    if flag_achat_desh>-1:
                        flag_achat-=1
            except KeyboardInterrupt:
                print("ctrl + C")
                break
            except:
                passage_bas=False
                passage_haut=False
                print("On relance la machine 2 "+time.strftime(' %H:%M:%S'))
                print("bas : "+str(bas))
                print("haut : "+str(haut))
            if flag_achat_desh>0:
                delta_achat_desh=5
            else:
                delat_achat_desh=0
            if flag_vente_desh>0:
                delta_vente_desh=5
            else:
                delat_vente_desh=0

#            prix_cour = float(prix['result']['XXRPZEUR']['b'][0])

            if passage_bas:
                print(str(time.strftime('%Y#%m#%d;%H:%M:%S')))
#                print("delta achat desh : "+str(delta_achat_desh))
#                print("delta vente desh : "+str(delta_vente_desh))
                del achat[str(bas)]
                if count_achat == 0:
                    bas=round(bas-self.ecart,3)
                    count_achat +=1
                    count_vente=0
                    haut=round(bas+2*self.ecart,3)
                    delta_achat_niveau=PSEUDO_FIBO
                    delta_vente_niveau=0
                    achat={}
                    vente={}
                    basic.flush_zero(kraken)
                    print("Niveau 1")
                elif count_achat == 1:
                    bas=round(bas-self.ecart,3)
                    count_achat +=1
                    count_vente=0
                    haut=round(bas+2*self.ecart,3)
                    delta_achat_niveau=PSEUDO_FIBO*2
                    delta_vente_niveau=0
                    achat={}
                    vente={}
                    basic.flush_zero(kraken)
                    print("Niveau 2")
                elif count_achat == 2:
                    bas=round(bas-2*self.ecart,3)
                    count_achat +=1
                    count_vente=0
                    haut=round(bas+3*self.ecart,3)
                    delta_achat_niveau=PSEUDO_FIBO*3
                    delta_vente_niveau=0
                    achat={}
                    vente={}
                    basic.flush_zero(kraken)
                    print("Niveau 3")
                elif count_achat == 3:
                    bas=round(bas-2*self.ecart,3)
                    count_achat +=1
                    count_vente=0
                    haut=round(bas+3*self.ecart,3)
                    delta_achat_niveau=PSEUDO_FIBO*4
                    delta_vente_niveau=0
                    achat={}
                    vente={}
                    basic.flush_zero(kraken)
                    print("Niveau 4")
                else:
                    bas=round(bas-3*self.ecart,3)
                    count_achat +=1
                    count_vente=0
                    haut=round(bas+4*self.ecart,3)
                    delta_achat_niveau=PSEUDO_FIBO*5
                    achat={}
                    vente={}
                    basic.flush_zero(kraken)
                    print("Niveau 5")
                ####attention l'achat existe peut etre deja ####################
                if not str(bas) in achat.keys():
                    buy = basic.new_order(kraken,"XRPEUR","buy","limit",str(bas),str(MONTANT_ACHAT+delta_achat_niveau + delta_achat_desh))
                    #print(str(buy))
                    achat[str(bas)]=str(buy)
                else:
                    print("l'achat est deja dans le dictionnaire")
                buy = basic.new_order(kraken,"XRPEUR","sell","limit",str(haut),str(MONTANT_VENTE + delta_vente_desh))
                #print(str(buy))
                vente[str(haut)]=str(buy)
                

                print("ACHAT "+str(bas)+" /// "+str(haut) + " b : "+str(prix)+"  //echelon  "+str(self.ecart))

                #Enregistrement du niveau achat_vente pour revenir au meme etat en cas de redemarrage
                basic.ecriture_niveaux(count_achat , count_vente)
                #Enregistrement des ordres d achat et vente qui viennent d etre passe
                basic.ecriture_achat_vente(achat,vente)

#                cmd="echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";ACHAT;1;"+str(bas)+";"+str(haut)+";"+str(prix['result']['XXRPZEUR']['b'][0]) + "' >> "+str(self.ecart)+".csv"
#                os.system(cmd)


            if passage_haut:
                print(str(time.strftime('%Y#%m#%d;%H:%M:%S')))
#                print("delta achat desh : "+str(delta_achat_desh))
#                print("delta vente desh : "+str(delta_vente_desh))
                del vente[str(haut)]
                if count_vente == 0:
                    haut=round(haut+self.ecart,3)
                    bas=round(haut-2*self.ecart,3)
                    count_achat=0
                    count_vente+=1
                    delta_achat_niveau=0
                    delta_vente_niveau=PSEUDO_FIBO
                    achat={}
                    vente={}
                    basic.flush_zero(kraken)
                    print("Niveau 1")
                elif count_vente == 1:
                    haut=round(haut+self.ecart,3)
                    bas=round(haut-2*self.ecart,3)
                    count_achat=0
                    count_vente+=1
                    delta_achat_niveau=0
                    delta_vente_niveau=PSEUDO_FIBO*2
                    achat={}
                    vente={}
                    basic.flush_zero(kraken)
                    print("Niveau 2")
                elif count_vente == 2:
                    haut=round(haut+2*self.ecart,3)
                    bas=round(haut-3*self.ecart,3)
                    count_achat=0
                    count_vente+=1
                    delta_achat_niveau=0
                    delta_vente_niveau=PSEUDO_FIBO*3
                    achat={}
                    vente={}
                    basic.flush_zero(kraken)
                    print("Niveau 3")
                elif count_vente == 3:
                    haut=round(haut+2*self.ecart,3)
                    bas=round(haut-3*self.ecart,3)
                    count_achat=0
                    count_vente+=1
                    delta_achat_niveau=0
                    delta_vente_niveau=PSEUDO_FIBO*4
                    achat={}
                    vente={}
                    basic.flush_zero(kraken)
                    print("Niveau 4")
                else:
                    haut=round(haut+3*self.ecart,3)
                    bas=round(haut-4*self.ecart,3)
                    count_achat=0
                    count_vente+=1
                    delta_achat_niveau=0
                    delta_vente_niveau=PSEUDO_FIBO*5
                    achat={}
                    vente={}
                    basic.flush_zero(kraken)
                    print("Niveau 5")
                buy = basic.new_order(kraken,"XRPEUR","buy","limit",str(bas),str(MONTANT_ACHAT + delta_achat_desh))
                #print(str(buy))
                achat[str(bas)]=str(buy)
                ######        Attention la vente existe peut etre deja
                if not str(haut) in vente.keys():
                    buy = basic.new_order(kraken,"XRPEUR","sell","limit",str(haut),str(MONTANT_VENTE + delta_vente_niveau + delta_vente_desh))
                    #try:
                        #print(str(buy))
                    #except:
                        #print(str(buy))
                    vente[str(haut)]=str(buy)
                else:
                    print("La vente est deja dans le dictionnaire")
                print("VENTE "+str(bas)+" /// "+str(haut)+" b : "+str(prix)+"  //echelon  "+str(self.ecart) )


                #Enregistrement du niveau achat_vente pour revenir au meme etat en cas de redemarrage
                basic.ecriture_niveaux(count_achat , count_vente)
                #Enregistrement des ordres d achat et vente qui viennent d etre passe
                basic.ecriture_achat_vente(achat,vente)


            time.sleep(self.TIME_SLEEP)
    


class basics():

    def __init__(self):
        self.PRIX=0.7
        self.tendance=0

    def get_found(selk,kraken,devise):
        try:
            response = kraken.query_private('Balance')
            retour = response['result'][devise]
        except:
            retour = "ça pas marche"
        return retour

    def new_order(self,kraken,pair,type_B_S,ordertype,price,volume):
        try:
            response = kraken.query_private('AddOrder',
                                            {'pair': pair,
                                             'type': type_B_S,
                                             'ordertype': ordertype,
                                             'price': price,
                                             'volume': volume})
                                             # `ordertype`, `price`, `price2` are valid
                                             #'close[ordertype]': 'limit',
                                             #'close[price]': '0.75',
                                             # these will be ignored!
                                             #'close[pair]': 'XRPEUR',
                                             #'close[type]': 'sell',
                                             #'close[volume]': '100'})
        except:
            print("PROBLEME D'OUVERTURE D'ORDRE")
            cmd = "echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";"i + str(response) + "' >> LOG/ERROR.log"
            os.system(cmd)
        try:
            print(str(response['result']))
        except:
            print("Erreur (surement une evolution trop brutale) : \n" + str(response['error']))
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
        cmd="echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";;"+type_B_S+";"+str(price) +";"+ str(volume)+";;"+ str(ID) +";"+str(response['error'])+"' >> LOG/"+time.strftime('%Y#%m#%d')+".log"
        os.system(cmd)
        return ID

    def order_status(self,kraken, order_id,niveau,montant,fibo,ecart):
        result = kraken.query_private('QueryOrders', {'txid': order_id})
        ret = result['result'][order_id]['status']

        if ret == 'closed':
            volume = result['result'][order_id]['vol_exec']
            prix = result['result'][order_id]['price']
            frais = result['result'][order_id]['fee']
            type_B_S = result['result'][order_id]['descr']['type']
            print("\n")
#            print(str(result))

#ECART = parameters.ECART
#MONTANT_ACHAT = parameters.MONTANT_ACHAT
#MONTANT_VENTE = parameters.MONTANT_VENTE
#PSEUDO_FIBO = parameters.PSEUDO_FIBO
            euros = str(self.get_found(kraken,'ZEUR'))
            xrp = str(self.get_found(kraken,'XXRP'))
            cmd="echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";"+ret+";"+type_B_S+";"+prix+";"+ volume +";"+frais+";"+ order_id +";"+str(result['error'])+";"+str(montant)+";"+str(fibo)+";"+str(niveau)+";"+str(ecart)+";"+ euros +";"+xrp+";"+"' >> LOG/"+time.strftime('%Y#%m#%d')+".log"
            os.system(cmd)
        
        return ret

    def order_close(self,kraken, order_id):
        result = kraken.query_private('CancelOrder', {'txid': order_id})
        return result

    def latest_price(self,kraken,pair):

        prix = kraken.query_public('Ticker', {'pair': pair})
        prix_cour = float(prix['result']['XXRPZEUR']['b'][0])
        return prix_cour

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


    def flush(self,ordres_ouverts,kraken_key,achat,vente,prix):
        achat={}
        vente={}
        for el in ordres_ouverts['result']['open'].keys():
            self.order_close(kraken_key,el)
        prix_cour = float(prix)
        bas=round(prix_cour - prix_cour%ECART,3)
        haut=round(bas + ECART,3)
        buy = self.new_order(kraken_key,"XRPEUR","buy","limit",str(bas),MONTANT_ACHAT)
        print(str(buy))
        
        achat[str(bas)]=str(buy)

        sell = self.new_order(kraken_key,"XRPEUR","sell","limit",str(haut),MONTANT_VENTE)
        print(str(sell))
        vente[str(haut)]=str(sell)
        self.ecriture_achat_vente(achat,vente)

    #ferme tout les ordres et initialise les fichiers achat et vente
    def flush_zero(self,kraken_key):
        achat={}
        vente={}
        self.ecriture_achat_vente(achat,vente)
        ordres_ouverts = kraken_key.query_private('OpenOrders',{'trades': 'true','start':'1514790000'})
        for el in ordres_ouverts['result']['open'].keys():
            self.order_close(kraken_key,el)


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


    def ecriture_achat_vente(self,achat,vente):
        fichier_achat=open("LOG/achat.txt",'w')
        fichier_vente=open("LOG/vente.txt",'w')
        json.dump(achat,fichier_achat)
        json.dump(vente,fichier_vente)
        fichier_achat.close()
        fichier_vente.close()
   
# sauvegarde le niveau achat et vente pour revenir au meme point en cas de reboot du script
    def ecriture_niveaux(self , niv_achat , niv_vente):
        fichier_niveaux = open("LOG/niveaux.txt",'w')
        dico_niveaux = {"achat":niv_achat,"vente":niv_vente}
        json.dump(dico_niveaux , fichier_niveaux)
        fichier_niveaux.close()


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

