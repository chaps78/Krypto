import telebot
import json




class teleAcces():
    def __init__(self):
        """Lit le token du bot et le chat par défaut dans bin_key.json."""
        with open('bin_key.json') as json_file:
            config = json.load(json_file)

        self.TELEG_TOKEN = config["telegram_token"]
        #Id du chat pour le BOT telegram
        self.BOT_CHAT_ID = config["chat_id"]


    def send_message(self,message,ID_chat=0):
        """Envoie un message Telegram (ID_chat=0 : chat par défaut).

        Ne lève jamais d'exception : une panne de Telegram (timeout, réseau...)
        est seulement affichée, pour ne pas interrompre le bot au milieu d'un
        traitement d'ordre.
        """
        if ID_chat==0:
            ID_chat = self.BOT_CHAT_ID
        try:
            bot = telebot.TeleBot(self.TELEG_TOKEN)
            bot.send_message(ID_chat, message)
        except Exception as inst:
            print("Telegram : envoi impossible : "+str(inst))

def main():
    """Test manuel du module."""
    tele = teleAcces()

if __name__ == '__main__':
     main()