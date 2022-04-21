FROM ubuntu:18.04



RUN   apt-get update \
  && apt-get install -y python3-pip python3-dev\
  && pip3 install krakenex\
  && pip3 install pyTelegramBotAPI



ADD . /app/



    

WORKDIR /app 


CMD python3 trader.py
