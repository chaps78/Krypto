from oauth2client.service_account import ServiceAccountCredentials
import gspread
from sqlInterface import sqlAcces







class sheetAcces():
    def __init__(self):
        scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('cred.json', scope)
        client = gspread.authorize(creds)
        self.sheet = client.open("binance")
        self.sql = sqlAcces()
    
    def update_values(self,symbol):
        ecart = self.sql.get_ecart_bet_from_symbol(symbol)
        wsheet = self.sheet.worksheet(symbol)
        keys = ecart.keys()
        ecart_tab=[]
        for key in keys:
            ecart_tab.append([key,ecart[key][0],ecart[key][1]])
        wsheet.update('A2', ecart_tab)
        ajouts = self.sql.get_ajout(symbol)
        ajout_to_sheet = []
        for ajout in ajouts:
            ajout_to_sheet.append([ajout[2]])
        wsheet.update('D2', ajout_to_sheet)
    
    def update_reste(self,symbol):
        wsheet = self.sheet.worksheet(symbol)
        reste = self.sql.get_last_reste(symbol)
        reste_2_sheet = [[reste["devise1"],reste["devise2"]]]
        wsheet.update('I3', reste_2_sheet)

    def update_last_filled_ID(self,symbol):
        wsheet = self.sheet.worksheet(symbol)
        last_filled = self.sql.get_last_filled(symbol)
        ID=[[last_filled["ID_ecart"]]]
        wsheet.update('H2', ID)
    
    def update_all_info(self,symbol):
        self.update_values(symbol)
        self.update_reste(symbol)
        self.update_last_filled_ID(symbol)




def main():    
    sheet = sheetAcces()
    #sheet.update_values("XRPEUR")
    #sheet.update_reste("XRPEUR")
    #sheet.update_last_filled_ID("XRPEUR")
    sheet.update_all_info("DOGEBTC")

    


if __name__ == '__main__':
     main()