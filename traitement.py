import os
#import basics from ../quatre



def lecture_log(nom_fichier):
    traitement_log=open(nom_fichier,'r')
    tab_achat=[]
    tab_vente=[]
    achat=0
    vente=0
    montant_achat=0
    montant_vente=0
    fee=0

    for ligne in traitement_log:

        tab_tmp = ligne.split(";")
        if tab_tmp[2]=="closed" and tab_tmp[3]=="buy":
            tab_achat.append(tab_tmp)
        
        if tab_tmp[2]=="closed" and tab_tmp[3]=="sell":
            tab_vente.append(tab_tmp)
    for i in tab_achat:
        montant_achat+=float(i[4])*float(i[5])
        fee+=float(i[6])
        achat+=float(i[5])
#        print(i)
#    print("montant achat : "+str(montant_achat))
#    print("quantité achetée : " + str(achat))
    for i in tab_vente:
        montant_vente+=float(i[4])*float(i[5])
        fee+=float(i[6])
        vente+=float(i[5])
#        print(i)     
#    print("montant vente : "+str(montant_vente))
#    print("quantité vendu : " + str(vente))
#    print("fee : "+str(fee))
    montant_final=montant_vente-montant_achat-fee
    crypto_final=achat - vente
#    print("montant final : " + str(montant_final))
#    print("cripto acheté : " + str(crypto_final))
#    print("OUIII0" + str(tab_achat))
    if(crypto_final<0):
        print(tab_vente[0][0] + ";vente;"+str(-crypto_final)+";"+str(-montant_final/crypto_final))
        os.system("echo '"+(tab_vente[0][0] + ";vente;"+str(-crypto_final)+";"+str(-montant_final/crypto_final))+"' >> Resume_final.csv")
#    print("OUIII1" + str(tab_vente))
    if(crypto_final>0):
        print(tab_achat[0][0] + ";achat;"+str(crypto_final)+";"+str(-montant_final/crypto_final))
        os.system("echo '"+(tab_achat[0][0] + ";achat;"+str(crypto_final)+";"+str(-montant_final/crypto_final))+"' >>Resume_final.csv")

    traitement_log.close

liste_dir = os.listdir(".")

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

for ligne in traitement_final:

    tab_tmp = ligne.split(";")
    if tab_tmp[1]=="achat":
        cripto_achat+=float(tab_tmp[2])
        total_achat+=float(tab_tmp[2])*float(tab_tmp[3])
    if tab_tmp[1]=="vente":
        cripto_vente+=float(tab_tmp[2])
        total_vente+=float(tab_tmp[2])*float(tab_tmp[3])
cripto_total=cripto_achat-cripto_vente
#print("Cripto total : "+str(cripto_total))
#print("Total achat : " + str(total_achat))
#print("Total vente : " + str(total_vente))
prix_total=total_vente-total_achat
#print("Delta prix achat vente : " + str(prix_total))
#print("Prix par XRP: "+ str(prix_total/cripto_total))
str_prrint=""
if(cripto_total<0):
    str_print="Nous avons vendu "+str(-cripto_total) +" à " + str(-prix_total/cripto_total) +"€"
elif(cripto_total>0):
    str_print="Nous avons acheté "+str(cripto_total) +" à " + str(-prix_total/cripto_total) +"€"
else:
    str_print="Nous sommes à l'équilibre et le benef est de " +str(prix_total) +"€"
print(str_print)
os.system("echo '"+str_print+"' >>Resume_final.csv")


traitement_final.close

