import krakenex
import time
import os
from random import randint
import socket
import json





def main():

    kraken = krakenex.API()
    kraken.load_key('kraken.key')
    basic = basics()

    print("Fonction à lancer :")
    print("\t1 : achat_limite(pair,prix,volume)")
    selection=input()
    if selection=="1":
        selection1 = input("pair (XRPEUR): ")
        selection2 = input("prix : ")
        selection3 = input("volume : ")
        retour = basic.achat_limite(kraken,str(selection1),str(selection2),str(selection3))
        print(str(retour))

    


class basics():

    def achat_limite(self,kraken,pair,price,volume):
        try:
            response = kraken.query_private('AddOrder',
                                            {'pair': pair,
                                             'type': 'buy',
                                             'ordertype': 'limit',
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
            print("mettre dansles log un probleme")
        return response

    def achat_marche(self,kraken,pair,volume):
        try:
            response = kraken.query_private('AddOrder',
                                            {'pair': pair,
                                             'type': 'buy',
                                             'ordertype': 'market',
                                             'price': '0',
                                             'volume': volume})
                                             # `ordertype`, `price`, `price2` are valid
                                             #'close[ordertype]': 'limit',
                                             #'close[price]': '0.75',
                                             # these will be ignored!
                                             #'close[pair]': 'XRPEUR',
                                             #'close[type]': 'sell',
                                             #'close[volume]': '100'})
        except:
            print("mettre dansles log un probleme")
        return response

    def vente_limite(self,kraken,pair,price,volume):
        try:
            response = kraken.query_private('AddOrder',
                                            {'pair': pair,
                                             'type': 'sell',
                                             'ordertype': 'limit',
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
            print("mettre dansles log un probleme")
        return response


    def order_status(self,kraken, order_id):
        result = kraken.query_private('QueryOrders', {'txid': order_id})
        ret = result['result'][order_id]['status']

        if ret == 'closed':
            volume = result['result'][order_id]['vol_exec']
            prix = result['result'][order_id]['price']
            frais = result['result'][order_id]['fee']
            type_B_S = result['result'][order_id]['descr']['type']
            print("\n")
#            print(str(result))
            cmd="echo '"+time.strftime('%Y#%m#%d;%H:%M:%S')+";"+ret+";"+type_B_S+";"+prix+";"+ volume +";"+frais+";"+ order_id +";"+str(result['error'])+"' >> LOG/"+time.strftime('%Y#%m#%d')+".log"
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
            fichier_achat=open("achat.txt",'r')
            achat_tmp= json.load(fichier_achat)
            fichier_achat.close()
        except:
            pass
        achat=achat_tmp
        print("achat.txt : \n"+str(achat))
        return achat


    def lecture_vente(self,vente): 
        try:
            fichier_vente=open("vente.txt",'r')
            vente_tmp= json.load(fichier_vente)
            fichier_vente.close()
        except:
            pass
        vente=vente_tmp
        print("vente.txt : \n"+str(vente))
        return vente


    def ecriture_achat_vente(self,achat,vente):
        fichier_achat=open("achat.txt",'w')
        fichier_vente=open("vente.txt",'w')
        json.dump(achat,fichier_achat)
        json.dump(vente,fichier_vente)
        fichier_achat.close()
        fichier_vente.close()
    




if __name__ == '__main__':
     main()

