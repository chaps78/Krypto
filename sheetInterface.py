from oauth2client.service_account import ServiceAccountCredentials
import gspread
from sqlInterface import sqlAcces







class sheetAcces():
    def __init__(self):
        """Ouvre le classeur Google Sheets "binance" avec le compte de service cred.json."""
        scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name('cred.json', scope)
        client = gspread.authorize(creds)
        self.sheet = client.open("binance")
        self.sql = sqlAcces()
    
    def update_values(self,symbol):
        """Ecrit la grille (A2 : ID, prix, bet) et les ajouts (D2) dans l'onglet de la stratégie."""
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
        """Ecrit le dernier relevé de la table reste en I3."""
        wsheet = self.sheet.worksheet(symbol)
        reste = self.sql.get_last_reste(symbol)
        reste_2_sheet = [[reste["devise1"],reste["devise2"]]]
        wsheet.update('I3', reste_2_sheet)

    def update_last_filled_ID(self,symbol,ID_client):
        """Ecrit l'ID du dernier palier exécuté en H2."""
        wsheet = self.sheet.worksheet(symbol)
        last_filled = self.sql.get_last_filled(symbol,ID_client)
        ID=[[last_filled["ID_ecart"]]]
        wsheet.update('H2', ID)
    
    def update_all_info(self,symbol,ID_client):
        """Met à jour la grille, les restes et le dernier palier exécuté."""
        self.update_values(symbol)
        self.update_reste(symbol)
        self.update_last_filled_ID(symbol,ID_client)




def main():    
    """Test manuel du module."""
    sheet = sheetAcces()
    sheet.update_all_info("DOGEBTC", 1)

    


if __name__ == '__main__':
     main()