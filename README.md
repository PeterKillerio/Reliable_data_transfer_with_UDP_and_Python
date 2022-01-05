# CTU_KDS_reliable_udp_file_transfer

By Peter Basár and Matěj Kopecký 5.1.2022

Semestral work for KDS class, python implementation of reliable file transfer in python.

Current settings require that netderper is live on machine running state_sender_application.py

(a) state_sender_application <-> (b) NetDerper <-> (c) state_receiver_application

|       Application      |       a       | b |       c       |
|:----------------------:|:-------------:|:-:|:-------------:|
|       Machine IP       | 192.168.30.30 | - | 192.168.30.15 |
|   Send data target IP  |   127.0.0.1   | - | 192.168.30.30 |
|  Send data target port |      5040     | - |      5006     |
|  Receive data from IP  |   127.0.0.1   | - |   127.0.0.1   |
| Receive data from port |      5009     | - |      5005     |

NetDerper recieves data from application (a) on port 5040 and IP {127.0.0.1} and sends it to application (c) on port 5005 and IP {192.168.30.15}.
NetDerper does this also the other way around, receives data ~ACK~ from application (c) on port 5006 on IP {127.0.0.1} and sends it to application (a) on port 5009 and IP {127.0.0.1}.  