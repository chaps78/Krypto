import os
#import basics from ../quatre
import datetime

def recap(cripto_total,prix_total,date,euros,xrp,xrp_price):
    BET=float(45)
    DELTA=0.004
    try:
        #print(xrp)
        solde_global=float(xrp.strip('\n'))*float(xrp_price.strip('\n'))+float(euros)
        #TODO
        #Mettre en parametre le delta et le montant du bet
        pt_equilibre= cripto_total*DELTA/BET+float(xrp_price)
        pt_equilibre_del=pt_equilibre/DELTA
        gain_pt_equi=BET*DELTA*pt_equilibre_del*(pt_equilibre_del+1)/2+prix_total-BET*float(xrp_price)*(float(xrp_price)/DELTA+1)/2


    except:
        solde_global="NA"
    if(cripto_total<1e-02 and cripto_total>-1e-02):
        str_print=date+";équilibre;;;" +str(prix_total) +";€;"+euros.strip('\n')+";"+xrp.strip('\n')+";"+xrp_price+";"+str(solde_global)
    elif(cripto_total<0):
        try:
            str_print=date+";vendu;"+str(cripto_total) +"\t;à;" + str(-prix_total/cripto_total) +";Equilibre"+"\t;delta : " + str(float(cripto_total)-float(xrp)) 
        except:
            str_print=date+";vendu;"+str(cripto_total) +"\t;à;" + str(-prix_total/cripto_total) +"\t;€\t;"+euros.strip('\n')+"\t;"+xrp.strip('\n')+";"+xrp_price+"\t;"+str(solde_global)
    elif(cripto_total>0):
        try:
            str_print=date+";acheté;"+str(round(cripto_total,3)) +"\t;à;" + str(round(-prix_total/cripto_total,5))+"\t;Prix;"+xrp_price+";\tEq;"+str(round(pt_equilibre,4))+";\t€ au pt equi;"+str(round(gain_pt_equi,4))+"\t;delta : " + str(round(float(cripto_total)-float(xrp),3))
        except:
            str_print=date+";acheté;"+str(cripto_total) +"\t;à;" + str(-prix_total/cripto_total) +"\t;€\t;"+euros.strip('\n')+"\t;"+xrp.strip('\n')+";"+xrp_price+"\t;"+str(solde_global)
    print(str_print)
    os.system("echo '"+str_print+"' >>Classeur.csv")

def lecture_log(nom_fichier):
    traitement_log=open("/home/chaps78/K/LOG/"+nom_fichier,'r')
    tab_achat=[]
    tab_vente=[]
    achat=0
    vente=0
    montant_achat=0
    montant_vente=0
    fee=0
    solde=""
    dernier_prix=""
    solde_xrp=""

#Parcours du fichier de log
    for ligne in traitement_log:
        tab_tmp = ligne.split(";")
        #Création d'un tableau qui récapitule les achats
        if tab_tmp[2]=="closed" and tab_tmp[3]=="buy":
            tab_achat.append(tab_tmp)
            #Récupération du dernier solde en euro
            try:
                solde=tab_tmp[13]
            except:
                solde=""
            try:
                dernier_prix=tab_tmp[4]
            except:
                dernier_prix=""
            try:
                solde_xrp=tab_tmp[14]
            except:
                solde_xrp=""
        
        #Création d'un tableau qui récapitule les ventes
        if tab_tmp[2]=="closed" and tab_tmp[3]=="sell":
            tab_vente.append(tab_tmp)
            #Récupération du dernier solde en euro
            try:
                solde=tab_tmp[13]
            except:
                solde=""
            try:
                solde_xrp=tab_tmp[14]
            except:
                solde_xrp=""
            try:
                dernier_prix=tab_tmp[4]
            except:
                dernier_prix=""

    for i in tab_achat:
        montant_achat+=float(i[4])*float(i[5])
        fee+=float(i[6])
        achat+=float(i[5])
    for i in tab_vente:
        montant_vente+=float(i[4])*float(i[5])
        fee+=float(i[6])
        vente+=float(i[5])
    montant_final=montant_vente-montant_achat-fee
    crypto_final=achat - vente
    if(crypto_final<0):
        #print(tab_vente[0][0] + ";vente;"+str(-crypto_final)+";"+str(-montant_final/crypto_final))
        os.system("echo '"+(tab_vente[0][0] + ";vente;"+str(-crypto_final)+";"+str(-montant_final/crypto_final))+";"+str(solde.strip('\n'))+";"+str(dernier_prix)+";"+str(solde_xrp.strip('\n'))+"' >> Resume_final.csv")
    if(crypto_final>0):
        #print(tab_achat[0][0] + ";achat;"+str(crypto_final)+";"+str(-montant_final/crypto_final))
        os.system("echo '"+(tab_achat[0][0] + ";achat;"+str(crypto_final)+";"+str(-montant_final/crypto_final))+";"+str(solde.strip('\n'))+";"+str(dernier_prix)+";"+str(solde_xrp.strip('\n'))+"' >>Resume_final.csv")
    #if(crypto_final==0):
        #print(tab_achat[0][0] + ";EQUILIBRE;0;"+str(montant_final))

    traitement_log.close

liste_dir = os.listdir("/home/chaps78/K/LOG")
liste_dir.sort()
#print(str(liste_dir))
os.system("> Resume_final.csv")
for el in liste_dir:
    if ("log" in el) and ("lock" not in el) :
        #print(el)
        lecture_log(el)

total_achat=0.0
total_vente=0.0
cripto_achat=0.0
cripto_vente=0.0
traitement_final=open("Resume_final.csv",'r')

os.system("echo >Classeur.csv")
for ligne in traitement_final:
    #print(ligne)
    tab_tmp = ligne.split(";")
    if tab_tmp[1]=="achat":
        cripto_achat+=float(tab_tmp[2])
        total_achat+=float(tab_tmp[2])*float(tab_tmp[3])
    if tab_tmp[1]=="vente":
        cripto_vente+=float(tab_tmp[2])
        total_vente+=float(tab_tmp[2])*float(tab_tmp[3])
    euros=0
    xrp=0
    xrp_price=0
    try:
        euros=tab_tmp[4]
    except:
        euros=0

    try:
        xrp_price=tab_tmp[5]
    except:
        xrp_price=0

    try:
        xrp=tab_tmp[6]
    except:
        xrp=0

    recap((cripto_achat-cripto_vente),(total_vente-total_achat),tab_tmp[0],euros,xrp,xrp_price)

cripto_total=cripto_achat-cripto_vente
prix_total=total_vente-total_achat


#os.system("echo '"+str_print+"' >>Resume_final.csv")
#os.system("echo '"+ str(datetime.datetime.now()) + str_print + "' >> historique.txt")

traitement_final.close

