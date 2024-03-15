import os
import datetime
from oauth2client.service_account import ServiceAccountCredentials
import gspread
import sys
import time
import telebot

sys.path.append('/home/chaps78/K')
import ecart
import parameters
import bet

DICO_BET = parameters.DICO_BET
BOT_CHAT_ID = parameters.TELEGRAM_CHAT_ID


def get_last_benef_line():
    last_traitement = os.popen("cat /home/chaps78/K/benef.log|grep trait|tail -n 1").readlines()[0].split(";")
    return last_traitement

def get_last_line():
    last_traitement = os.popen("cat /home/chaps78/K/benef.log|tail -n 1").readlines()[0].split(";")
    return last_traitement

def lecture_last_log():
    last_close = os.popen("cat /home/chaps78/K/LOG/*log|grep closed|tail -n 1").readlines()[0].split(";")
    return last_close

def convert_list_2_dico(liste):
    dico = {}
    dico['sens']=liste[3]
    dico['euros'] = liste[13]
    dico['XRP'] = liste[14]
    dico['prix'] = liste[4]
    return dico

def get_key_list(ecarts,value):
    i=0
    for el in ecarts:
        if abs(float(el) - float(value)) < 0.0001:
            return i
        i +=1

def get_bet_base(price):
    price_tab=0.0
    flag_min=100.0
    for i in ecart.ECART:
        if flag_min > abs(price-i):
            price_tab=i
            flag_min  = abs(price-i)

    return bet.BET[ecart.ECART.index(price_tab)]

def get_bet_achat(price,ec):
    return get_bet_base(float(price)+float(ec))

def get_bet_vente(price):
    return get_bet_base(float(price))

def limite_basse(dico,indice_buy):
    euros = float(dico['euros'])
    xrp = float(dico['XRP'])
    tab_achat=[]
    while indice_buy > 0:
        euros = euros - ecart.ECART[indice_buy]*get_bet_achat(ecart.ECART[indice_buy],ecart.ECART[indice_buy]-ecart.ECART[indice_buy-1])
        xrp = xrp + get_bet_achat(ecart.ECART[indice_buy],ecart.ECART[indice_buy]-ecart.ECART[indice_buy-1])
        tab_achat.append([float(euros) , float(xrp)])
        indice_buy = indice_buy - 1
    tab_achat.reverse()
    #for el in tab_achat:
    #    print(str(el)+" haaaaaa")
    print(tab_achat[0])
    return tab_achat
    #print(tab_achat.reverse())

    #print("BAS:\t" + str(euros).replace(".",",")+";"+str(xrp).replace(".",","))

def limite_haute(dico,indice_sell):
    euros = float(dico['euros'])
    xrp = float(dico['XRP'])
    tab_vente = []
    while indice_sell < 600:
        euros = euros + ecart.ECART[indice_sell]*get_bet_vente(ecart.ECART[indice_sell])
        #print(str(ecart.ECART[indice_buy]))
        xrp = xrp - get_bet_vente(ecart.ECART[indice_sell])
        tab_vente.append([float(euros) , float(xrp)])
        indice_sell = indice_sell + 1
    print("\n\n")

    #for el in tab_vente:
    #    print(el)
    print(tab_vente[len(tab_vente)-1])
    return tab_vente
    #print("HAUT:\t" + str(euros).replace(".",",")+";"+str(xrp).replace(".",","))



last = lecture_last_log()
dico = convert_list_2_dico(last)
indice_prix = get_key_list(ecart.ECART,float(dico['prix']))
print(dico)
try:
    indice_buy = indice_prix - 1
    indice_sell = indice_prix + 1
except:
    print("Indice ERROR: "+ str(indice_prix))


KPI_tab = limite_basse(dico,indice_buy)
KPI_tab.append([float(dico['euros']),""])
tab_tmp = limite_haute(dico,indice_sell)
for el in tab_tmp:
    KPI_tab.append(el)


scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
creds = ServiceAccountCredentials.from_json_keyfile_name('/home/chaps78/K/LOG/cred.json', scope)
client = gspread.authorize(creds)

sheet = client.open("calculs des bet variables")

wsheet = sheet.worksheet('KPI')
wsheet.update('H3', KPI_tab)




print("euros: "+ str(type(KPI_tab[0][0])))
XRP_reste = KPI_tab[len(KPI_tab)-1][1]


#print(time.strftime('%Y#%m#%d;%H:%M:%S;')+str(KPI_tab[0][0]))
last_trait = get_last_benef_line()
#KPI_tab[0][0]=10.0
print("euros: "+ str(KPI_tab[0][0]))

print(last_trait)
#last_trait_tab = last_trait.split(";")
print("benef perso : "+str(last_trait[7]))
total_benef = float(last_trait[7])
gain = KPI_tab[0][0] - float(last_trait[7])
print("gain : " + str(gain))
print("XRP reste : " + str(XRP_reste))
#trait;DATE;time;benef;%local;%up_invest;%perso;somme_perso;somme_total;XRP_delte
bot = telebot.TeleBot(parameters.TELEGRAM_TOKEN)
bot.send_message(BOT_CHAT_ID, 'Ecart XRP : ' + str(round(XRP_reste,2)) +'\ngain : ' + str(round(gain,2)))
arg = ""
try:
    arg = sys.argv[1]
except:
    arg = ""
#############################################
#       Parametres d investissement         #
#############################################
limite=5
# Somme doit faire 1
local=0.7
up = 0.2
perso = 0.1
# Somme doit faire 1
up_limite = 0.6
perso_limite = 0.4
##############################################
last_line = get_last_line()
if "ACK2" in last_line:
    print("ya ACK2")
else:
    print("ya PAS de ACK2 : " + str(last_line))

if gain>0 and abs(XRP_reste) <= 15 and "ACK2" in last_line:
    if gain<=limite:
        if gain < 3 and total_benef > 1:
            gain = gain + 1
            total_benef = total_benef - 1

            cmd= "echo '"+time.strftime('trait;%d#%m#%Y;%H:%M:%S;')+str(gain)+";"+str(local*gain)+";"+str(up*gain)+";"+str(perso*gain)+";"+str(total_benef + perso*gain)+";-1;' >> /home/chaps78/K/benef.log"
        else:
            cmd= "echo '"+time.strftime('trait;%d#%m#%Y;%H:%M:%S;')+str(gain)+";"+str(local*gain)+";"+str(up*gain)+";"+str(perso*gain)+";"+str(total_benef + perso*gain)+";;' >> /home/chaps78/K/benef.log"
    else:
        cmd= "echo '"+time.strftime('trait;%d#%m#%Y;%H:%M:%S;')+str(gain)+";"+str(local*limite)+";"+str(up*limite+(gain-limite)*up_limite)+";"+str(perso*limite+(gain-limite)*perso_limite)+";"+str(total_benef+perso*limite+(gain-limite)*perso_limite)+";;' >> /home/chaps78/K/benef.log"
    if arg == "no":
        print("pas d impression")
    else:
        os.system(cmd)
else:
    if gain <=0:
        print("pas d impression car pas de gain")
    if abs(XRP_reste) > 15:
        print("pas d impression car ecart de XRP trop important > 15")
    if not "ACK2" in last_line:
        print("pas d impression car pas de ACK2")
