# jitter-graphs
Generate jitter (cpdv) graphs from pcaps of iperf2 test runs.

For TCP we use the TCP sequence numbers for UDP we use the sequence numbers added by iperf
in its own application layer header.

Default output format is pdf


## Dependencies

## general:

 - python3
 - iperf
 - tcpdump

### cpdv_tsv

 - scapy (python3-scapy on debian/ubuntu or pip3 install scapy)

### cpdv_diagram 

- matplotlib (python3-matplotlib or from pip3)
- numpy (python3-numpy or from pip3)


## Full Example Walkthrough

For this example we create a little iperf2 test run, capture it in a pcap and generate 2 diagrams from it. 
For this you need a `iperf -s` server running on some server (katze.de in this example).

First start tcpdump to listen all the traffic. port 5001 is the iperf2 port. This expression makes sure you only
capture iperf2 traffic from the right host.

`sudo tcpdump -i wlan0 -w tcp_trace.pcap  'port 5001 and host katze.de'`

Now, in another terminal, start the iperf test run. -R reverse from the host to you and with 1Mbit/s.

`iperf -c katze.de -R -b 1M `

After iperf is finished change into the tcpdump terminal and kill tcpdump with Ctrl+c. No you can call `cpdv_tsv.py` on the pcap file.
Here in this example it lies in the parent folder to the pcap, depending where you put it that might be slightly different. This is the computation intense
part, it generates a tsv (tab seperated values) file from the pcap containing the sequence numbers and timings. One .tsv file for every flow it finds 
in the pcap.

`../cpdv_tsv.py tcp tcp_trace.pcap` 

Here it finds two flows: the iperf control flow (cpdv_flow0.tsv) and the payload flow (cpdv_flow1.tsv). 
To get a point cloud diagram of the playloud flow do: 

`../cpdv_diagram.py points cpdv_flow1.tsv`

Now you get the following diagram as pdf:

![A jitter diagram](./example/cpdv_flow1.png)

You can also create Jitter distribution diagrams with: 

`../cpdv_diagram.py distribution -t cpdv_flow1.tsv` 

Which look like this: 

![A jitter distribution diagram](./example/cpdv_dist.png)


## More Examples 
```
cpdv_tsv.py udp  */*.pcap

cpdv_diagram.py distribution -d OTIAS/ LowRTT/ MPTCP/ HTMT/ -l -100 100 -b 20 -c
cpdv_diagram.py distribution -d afmt_noqueue_busy_wait/ llfmt_noqueue_busy_wait/  otias_sock_drop/ srtt_min_busy_wait/

cpdv_diagram.py points cpdv_flow0.tsv
cpdv_diagram.py points -d afmt_noqueue_busy_wait/ llfmt_noqueue_busy_wait/  otias_sock_drop/ srtt_min_busy_wait

cpdv_diagram.py points -h
cpdv_diagram.py distribution -h
```
