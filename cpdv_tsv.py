#! /usr/bin/env python3

from argparse import ArgumentParser
import os.path
from scapy.utils import rdpcap
from scapy.layers.inet import IP, TCP, UDP
from scapy.packet import Raw
import sys


'''
ABOUT THIS SCRIPT:
    the packets from each pcap file are read and grouped into flows (see `get_flow_id()`
    for what counts as a flow). for every flow (in TCP: for every flow with at least one
    packet with a payload, or more specifically, where scapy detected a `Raw` layer) the
    cpdv is calculated and written to a <pcap_file>_<index>.tsv file. the <index> starts
    at 0 for each file. the .tsv format is as follows:
        <sequence number>        <time delta to previous sequence number>
'''


def get_flow_id(packet):
    '''
    get a string that uniquely identifies one flow, i. e. a connection between
    to IP addresses respecting ports and direction, for a given packet.
    example: one flow is from 1.0.0.1:1234 to 11.0.0.2:500, another one is from 11.0.0.2:500 to
    1.0.0.1:1234 and a third one is from 2.0.0.1:4321 to 11.0.0.2:600
    '''
    return f'{packet[IP].src}:{packet[IP].sport}->{packet[IP].dst}:{packet[IP].dport}'


def get_data_tcp(packets):
    '''
    get a dictionary that contains for each found flow a dictionary that maps sequence number
    to arrival time in milliseconds

    parameters:
        - packets: list of TCP packets
    '''
    # this is a layered dict. the first key maps a flow (see `get_flow_id()`) to its
    # sequences dict. the key for this sequences dict maps the sequence number to the
    # arrival time of the packet with that sequence number
    # NOTE: this discards all but the last packet for a given sequence number, e. g.
    # if the packets sent are only ACKs and the sequence number doens't change
    seq_to_arrival_time = dict()
    # has there been at least one packet with payload len > 0 in the flow?
    data_sent = dict()

    for pkt in packets:
        seq_number = pkt[TCP].seq
        if seq_number < 0:
            continue

        flow_id = get_flow_id(pkt)

        if flow_id not in seq_to_arrival_time:
            seq_to_arrival_time[flow_id] = dict()
            data_sent[flow_id] = False

        seq_to_arrival_time[flow_id][seq_number] = pkt.time * 1000

        if pkt.haslayer(Raw):
            data_sent[flow_id] = True

    # ignore flows where no data was sent
    for flow in data_sent:
        if not data_sent[flow]:
            del seq_to_arrival_time[flow]

    return seq_to_arrival_time


def get_data_iperfudp(packets):
    '''
    get a dictionary that contains for each found flow a dictionary that maps sequence number
    to arrival time in milliseconds

    parameters:
        - packets: list of UDP packets
    '''
    # this is a layered dict. the first key maps a flow (see `get_flow_id()`) to its
    # sequences dict. the key for this sequences dict maps the sequence number to the
    # arrival time of the packet with that sequence number
    seq_to_arrival_time = dict()
    for pkt in packets:
        # UDP normally doesn't have sequence numbers, but iperf uses the first four
        # bytes of the payload to store a sequence number
        seq_field_bytestring = pkt.load[0:4]
        seq_number = int.from_bytes(seq_field_bytestring, byteorder='big', signed=True)

        if seq_number < 0:
            continue

        flow_id = get_flow_id(pkt)

        if flow_id not in seq_to_arrival_time:
            seq_to_arrival_time[flow_id] = dict()

        seq_to_arrival_time[flow_id][seq_number] = pkt.time * 1000

    return seq_to_arrival_time


def write_tsv(pcap_filename, mode, verbose):
    '''
    analyze a .pcap file and write .tsv files containing the output from `get_data_tcp()` / `get_data_iperfudp()`
    separately for each flow

    parameters:
        - pcap_filename: name of the .pcap file to analyze
        - mode: string that determines which `get_data_...()` function is used, see the argparse help for more. valid values: 'udp', 'tcp', 'auto'
        - verbose: boolean that determines whether information is written to stdout
    '''
    if verbose:
        print(f'Reading {pcap_filename}... ', end='')
        sys.stdout.flush()  # seems to be necessary here
    packets = rdpcap(pcap_filename)

    if mode == 'udp':
        get_data = get_data_iperfudp
    elif mode =='tcp':
        get_data = get_data_tcp
    elif mode =='auto':
        if packets[0].haslayer(UDP):
            get_data = get_data_iperfudp
        elif packets[0].haslayer(TCP):
            get_data = get_data_tcp
        else:
            raise ValueError('First package is neither UDP nor TCP!')

    # maps the sequence number to the arrival time, see `get_data_tcp()` for more details
    seq_to_arrival_time = get_data(packets)

    if verbose:
        print(f'found the following flows:')
    for flow_number, flow in enumerate(seq_to_arrival_time):
        cur_arrival_times = seq_to_arrival_time[flow]
        # we need at least two packets for calculating deltas
        if len(cur_arrival_times) < 2:
            continue

        if verbose:
            print(f'\t{flow_number}: {flow} - {len(seq_to_arrival_time[flow])} packets')

        # sort by sequence number
        cur_arrival_times = dict(sorted(cur_arrival_times.items(), key=lambda item: item[0]))
        prev_time = None

        # extension_index = pcap_filename.rfind(".")
        # extension_index = len(pcap_filename) if extension_index == -1 else extension_index
        # tsv_filename = f'{pcap_filename[:extension_index]}_{flow_number}.tsv'
        tsv_filename = os.path.join(os.path.dirname(pcap_filename), f'cpdv_flow{flow_number}.tsv')
        with open(tsv_filename, 'w') as f:
            for seq_nr in cur_arrival_times:
                if prev_time is None:
                    prev_time = cur_arrival_times[seq_nr]
                    continue

                delta = cur_arrival_times[seq_nr] - prev_time
                f.write(f'{seq_nr}\t{delta}\n')
                prev_time = cur_arrival_times[seq_nr]


if __name__ == '__main__':
    parser = ArgumentParser(description="Create .tsv files containing packet number and arrival time, sorted by the packets' sequence numbers \
        and split into separate flows, from .pcap files.")
    parser.add_argument('mode', choices=['udp', 'tcp', 'auto'], help='what type of packet to use (`auto` detects and uses the type of the first packet separately for each file, \
        the other two options are for all files)')
    parser.add_argument('pcap_files', metavar='file', type=str, nargs='+', help='a .pcap file to process')
    parser.add_argument('-v', '--verbose', action='store_true', help='print extra information to stdout')
    args = parser.parse_args(sys.argv[1:])  # don't pass script name to argparser
    
    for file in args.pcap_files:
        write_tsv(file, args.mode, args.verbose)