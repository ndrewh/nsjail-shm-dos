FROM nsjailcontainer

RUN mkdir /app
WORKDIR /app

COPY app.c .
RUN gcc -o app app.c
COPY start.sh .
COPY jail.cfg .

RUN chmod +x start.sh
CMD ["./start.sh"]
