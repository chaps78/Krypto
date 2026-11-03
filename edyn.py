import sqlite3
import copy
import sys

from sqlInterface import sqlAcces
from bininterface import binAcces

class Edyn():
    def __init__(self):
        #self.con = sqlite3.connect("/home/chaps78/binance/bascule/DB.db")
        self.sql = sqlAcces()
        self.con = sqlite3.connect("DB.db")
        self.cur = self.con.cursor()
        self.bin = binAcces()

    def get_base(self,symbol):
        try:
            res = self.cur.execute("SELECT * FROM base WHERE symbol='"+symbol+"'")

        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_orders_status_filter_SQL",str(inst),symbol)
            return inst
        self.con.commit()
        base = {}
        for el in res.fetchall():
            base[el[0]] = self.convert_base_to_dico(el)
        return base
    
    def convert_base_to_dico(self,base):
        dico = {}
        dico["symbol"] = base[1]
        dico["limite"] = base[2]
        return dico
    
    def ajout_poids(self,symbol,base,eid,ratio):
        if symbol == "EURUSDT_Seb3":
            nbr_dilat = 4
        else:
            nbr_dilat = 6
        base_tmp = copy.deepcopy(base)
        #base_tmp={}

        #for el in base:
        #    base_tmp[el]["limite"]=base[el]["limite"]
        #Contraction
        count = 0
        while count < nbr_dilat:
            #haut
            delta = base[eid+count+1]["limite"] - base[eid+count]["limite"]
            base_tmp[eid+count+1]["limite"]=base_tmp[eid+count]["limite"]+delta*ratio
            #bas
            delta = base[eid-count]["limite"] - base[eid-count-1]["limite"]
            base_tmp[eid-count-1]["limite"] = base_tmp[eid-count]["limite"]-delta*ratio
            count +=1
        #Dilatation
        delta_bas_new = base_tmp[eid-nbr_dilat]["limite"]-base_tmp[eid-nbr_dilat-1]["limite"]
        delta_haut_new = base_tmp[eid+nbr_dilat+1]["limite"] - base_tmp[eid+nbr_dilat] ["limite"]

        delta_bas_old = base[eid-nbr_dilat]["limite"]-base[eid-nbr_dilat-1]["limite"]
        delta_haut_old = base[eid+nbr_dilat+1]["limite"] - base[eid+nbr_dilat] ["limite"]

        delta_haut=delta_haut_new-delta_haut_old
        delta_bas=delta_bas_new - delta_bas_old

        count = 0
        while count < nbr_dilat:
            #haut
            delta = base[eid+nbr_dilat+count+1]["limite"] - base[eid+nbr_dilat+count]["limite"]
            base_tmp[eid+nbr_dilat+count+1]["limite"]=base_tmp[eid+nbr_dilat+count]["limite"] + delta + delta_haut/nbr_dilat
            #bas
            #print("symbol : " + symbol)
            #print(str(eid-nbr_dilat-count))
            #print(str(eid-nbr_dilat-count-1))
            #print("nbr_dilat : " + str(nbr_dilat))
            #print("count : " +str(count))
            delta = base[eid-nbr_dilat-count]["limite"] - base[eid-nbr_dilat-count-1]["limite"]
            base_tmp[eid-nbr_dilat-count-1]["limite"]=base_tmp[eid-nbr_dilat-count]["limite"] - delta - delta_bas/nbr_dilat
            count+=1

        return base_tmp

    def get_poids(self,symbol):
        try:
            res = self.cur.execute("SELECT * FROM poids WHERE symbol='"+symbol+"'")

        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_orders_status_filter_SQL",str(inst),symbol)
            return inst
        self.con.commit()
        poids = {}
        result_sql = res.fetchall()
        for el in result_sql:
            tmp = {}
            tmp["symbol"]=el[1]
            tmp["ID"]=el[2]
            if tmp["ID"]!= None:
                poids[el[0]]=tmp

        return poids
    
    def ajout_poid(self,symbol,ID):
        try:
            res = self.cur.execute("SELECT * FROM poids WHERE symbol='"+symbol+"'")

        except sqlite3.IntegrityError as inst:
            self.new_log_error("get_orders_status_filter_SQL",str(inst),symbol)
            return inst
        self.con.commit()
        poids = {}
        result_sql = res.fetchall()
        for el in result_sql:
            if el[2]!=None:
                try:
                    self.cur.execute("UPDATE poids SET EID="+str(el[2])+" WHERE ID="+str(el[0]+1)+" AND symbol='"+symbol+"'")
                except sqlite3.IntegrityError as inst:
                    self.new_log_error("add_to_ajout_SQL",str(inst),symbol)
                    return inst
                self.con.commit()
        self.cur.execute("UPDATE poids SET EID="+str(ID)+" WHERE ID=1 AND symbol='"+symbol+"'")
        self.con.commit()

    def update_e_b(self,symbol,new_grid):
        for el in new_grid:
            symbol_plited = symbol.split("_")[0]
            if symbol_plited == "XRPEUR":
                limite_tmp = int(new_grid[el]["limite"] * 10 ** 4)/10 ** 4
                limite = float('%.4f' % limite_tmp)
            if symbol_plited == "BTCEUR":
                limite_tmp = int(new_grid[el]["limite"] * 10 ** 2)/10 ** 2
                limite = float('%.4f' % limite_tmp)
            if symbol_plited == "EURUSDT":
                limite_tmp = int(new_grid[el]["limite"] * 10 ** 4)/10 ** 4
                limite = float('%.4f' % limite_tmp)
            self.cur.execute("UPDATE ecart_bet SET prix="+str(limite)+" WHERE ID="+str(el)+" AND symbol='"+symbol+"'")
            self.con.commit()

    def update_e_dyn(self,DEVISE,client):
        tmp_last_field = self.sql.get_last_filled(DEVISE,client)
        last_field_ID = tmp_last_field["ID_ecart"]
        self.ajout_poid(DEVISE,last_field_ID)
        base = self.get_base(DEVISE)
        poids = self.get_poids(DEVISE)
        new=base
        for el in poids:
            new = self.ajout_poids(DEVISE,new,poids[len(poids)-el+1]["ID"],0.905)
        self.update_e_b(DEVISE,new)
        open_orders = self.sql.get_orders_status_symbol_filter("NEW",DEVISE,client)
        for el in open_orders:
            self.bin.cancel_order(el["ID"],client)
    
        for el in open_orders:
            symbol_plited = DEVISE.split("_")[0]
            if symbol_plited == "BTCEUR":
                limite = round(new[el["ID_ecart"]]["limite"],2)
            elif symbol_plited == "XRPEUR":
                limite = round(new[el["ID_ecart"]]["limite"],4)
            else:
                limite = round(new[el["ID_ecart"]]["limite"],4)

            self.bin.new_limite_order(DEVISE,el["montant"],limite,el["sens"],el["ID_ecart"],0,client,el["niveau"],1)

    def create_base(self,e_b,symbol):
        for el in e_b:
            self.cur.execute("INSERT INTO base VALUES(?,?,?)",
                                 (el,symbol,e_b[el][0]))
        self.con.commit()

        count = 1
        while count<21:
            self.cur.execute("INSERT INTO poids VALUES(?,?,?)",
                                 (count,symbol,None))
            count +=1
        self.con.commit()

    def get_edyn_list(self):
        res = self.cur.execute("SELECT symbol,client FROM Devises WHERE e_dyn=1")

        self.con.commit()
        result_sql = res.fetchall()
        return result_sql
    
    def exec_edyn(self):
        devises_list = self.get_edyn_list()
        for el in devises_list:
            self.update_e_dyn(el[0],el[1])




def main():
    edyn = Edyn()
    DEVISE='XRPEUR_EDYN'
    if len(sys.argv) == 2:
        a = sys.argv[1]
        if a == "init":
            symbol = input("Quel est le symbol? ")
            e_b = edyn.sql.get_ecart_bet_from_symbol(symbol)
            edyn.create_base(e_b,symbol)
    else:
        edyn.exec_edyn()


if __name__ == '__main__':
     main()
