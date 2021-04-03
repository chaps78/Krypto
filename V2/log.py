import time
import os
import krakenex

def main():

    log_obj=logs()
    log_obj.Set_Entete()
    krakkrak = krakenex.API()
    krakkrak.load_key('kraken.key')

    ID_Ferme="OETSFP-YJXVG-WATI4O"
    result = krakkrak.query_private('QueryOrders', {'txid': ID_Ferme})
    log_obj.Set_Log_Ordre_Ferme(result,ID_Ferme)
    print(result)

#    response = krakkrak.query_private('AddOrder',
#                                   {'pair': "XRPEUR",
#                                    'type': "buy",
#                                    'ordertype': "limit",
#                                    'price': "0.1",
#                                    'volume': "40"})
#    
#    log_obj.Set_Log_Ouverture_Ordre(response,'XRPEUR','buy','limit','0.1','40')
# 
#    print('Le premier')
#    print(response)
#
#    response2 = krakkrak.query_private('CancelOrder', {'txid': response['result']['txid'][0]})
#
#    print(response2)
#
#    log_obj.Set_Log_Annulation_Ordre(response2,response['result']['txid'][0],'buy','XRPEUR','40','0.01')





class logs():

#    def __init__(self):


    #######################################################################
    #  Si le fichier de log du jour n'existe pas, la fonction se charge d'y mettre un entete
    #######################################################################
    def Set_Entete(self):
        file_name=time.strftime('LOG/%Y_%m_%d.log')
        if not os.path.isfile(file_name):
            os.system('echo "Date#Heure;ID Ordre;Pair;Sens;Status;Type;Valeur limite;Volume;Frais;Erreur" > ' +file_name)

    #######################################################################
    #  Imprime dans les logs les informations concernant un nouvel ordre
    #######################################################################
    def Set_Log_Ouverture_Ordre(self,retour,pair,sens,ordertype,price,volume):
        ligne = time.strftime('%Y_%m_%d#%H_%M_%S;')
        ret=0
        try:
            ligne +=retour['result']['txid'][0]+';'
            ligne +=retour['result']['descr']['order'].split(' ')[2]+';'
            ligne +=retour['result']['descr']['order'].split(' ')[0]+';'
            ligne +='Ouvert;'
            ligne +=retour['result']['descr']['order'].split(' ')[4]+';'
            ligne +=retour['result']['descr']['order'].split(' ')[5]+';'
            ligne +=retour['result']['descr']['order'].split(' ')[1]+';;'
            ret=1
        except:
            ligne +=';'+pair+';'+sens+';Ouverture_ERREUR;'+ordertype+';'+price+';'+volume+';;'+str(retour['error'])
            ret=0
        self.Set_Entete()
        file_name=time.strftime('LOG/%Y_%m_%d.log')
        os.system("echo '"+ligne+"' >> "+file_name)
        return ret


    ######################################################################
    # Imprime dans les logs lors de l'annulation d'un ordre
    ######################################################################
    def Set_Log_Annulation_Ordre(self,retour,ID,sens,pair,volume,prix_limite):
        self.Set_Entete()
        ligne = time.strftime('%Y_%m_%d#%H_%M_%S;')
        ret=0
        if retour['error'] == []:
            ligne+=ID+";"+pair+';'+sens+';'+'Annule;limite;'+prix_limite+';'+volume+';;'
            ret=1
        else:
            ligne+=ID+";"+pair+';'+sens+';'+'Annulation_ERREUR;limite;'+prix_limite+';'+volume+';;'+str(retour['error'])
            ret=0
        file_name=time.strftime('LOG/%Y_%m_%d.log')
        os.system("echo '"+ligne+"' >> "+file_name)
        return ret

    ######################################################################
    # Recupere l'ID d'un ordre fermé et recupere les informations corresponantes pour le mettre dans les logs
    ######################################################################
    def Set_Log_Ordre_Ferme(self,retour,ID):
        self.Set_Entete()
        ligne = time.strftime('%Y_%m_%d#%H_%M_%S;')
        ret=0
        if retour['error'] == []:
            ligne+=ID+';'+retour['result'][ID]['descr']['pair']+';'
            ligne+=retour['result'][ID]['descr']['type']+';'
            ligne+=retour['result'][ID]['status']+';'
            ligne+=retour['result'][ID]['descr']['ordertype']+';'
            ligne+=retour['result'][ID]['descr']['price']+';'
            ligne+=retour['result'][ID]['vol']+';'
            ligne+=retour['result'][ID]['fee']+';;'
            ret = 1
        else:
            ligne+=';'+ID+';;;;;;;'+str(retour['error'])
            ret = 0
        print(ligne)
        file_name=time.strftime('LOG/%Y_%m_%d.log')
        os.system("echo '"+ligne+"' >> "+file_name)
        return ret
















if __name__ == '__main__':
    main()


