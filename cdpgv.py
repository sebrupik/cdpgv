#!/usr/bin/env python3
import graphviz as gv
import json
import netmiko
import re

CDP_FULL_REGEX = "(Device ID: )(?P<device>\S+).*(IP address: )(?P<ip_address>\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}).*" + \
                 "(Platform: )(?P<platform>[^,]*).*(Interface: )(?P<interface>[^,]*)[^:]*.." + \
                 "(?P<interface_outgoing>\S*)(?P<remainder>.*)"
IOS_PO_SUMMARY = "(?P<group>\d+)\s+(?P<po>\S+)\s+(?P<protocol>\S+)\s+(?P<ports>\D.*\s)*"
IOS_PO_SUMMARY_SINGLE_LINE = "(?P<group>\d+)\s+(?P<po>\S+)\s+(?P<protocol>\S+)\s+(?P<ports>(\D\S*[)]\s*)*)"

MAX_RADIUS = 1

""" Takes the CDP interface format and returns a more familar string, eg:
Gig 1/0/1 -> Gi1/0/1
Ten 1/1/1 -> Te1/1/1
"""
def compact_cdp_br_interface(interface_input):
    return interface_input[0:1]+interface_input[4:0]


""" Takes the CDP detail neigbour interface format and returns a more familar string, eg:
GigabitEthernet1/0/1 -> Gi1/0/1
TenGigabitEthernet1/1/1 -> Te1/1/1
"""
def compact_cdp_det_interface(interface_input):
    return interface_input


def get_cdp_full_match(input_str):
    match = re.search(CDP_FULL_REGEX, input_str)
    if match:
        match_dict = dict()
        match_dict["device_id"] = match.group("device").split(".")[0]
        match_dict["ip_address"] = match.group("ip_address")
        match_dict["platform"] = match.group("platform")
        match_dict["interface"] = compact_cdp_det_interface(match.group("interface"))
        match_dict["interface_outgoing"] = compact_cdp_det_interface(match.group("interface_outgoing"))
        match_dict["remainder"] = match.group("remainder")

        if "cisco" or "Cisco" in match_dict["remainder"]:
            match_dict["cisco"] = True
        else:
            match_dict["cisco"] = False

        return match_dict

    return None


def get_po_full_match(input_str):
    port_channels = []

    for match in re.finditer(IOS_PO_SUMMARY_SINGLE_LINE, input_str, re.S):
        match_dict = dict()
        match_dict["group"] = match.group("group")
        match_dict["po"] = match.group("po")
        if match.group("ports"):
            match_dict["ports"] = match.group("ports").split()
        else:
            match_dict["ports"] = None

        port_channels.append(match_dict)

    return port_channels


def parse_cdp_detail_raw(cdp_output_raw):
    cdp_ar = cdp_output_raw.split("-------------------------")
    cdp_entries = []
    for cdp_entry in cdp_ar:
        c = " ".join(cdp_entry.splitlines())
        print(c)
        cdp_dict = get_cdp_full_match(c)
        if cdp_dict is not None:
            cdp_entries.append(cdp_dict)

    return cdp_entries


def parse_po_summary_raw(po_output_raw, os):
    if os == "IOS":
        po_ar = po_output_raw.splitlines()
        index = None
        for i, j in enumerate(po_ar):
            if j.startswith("----"):
                index = i

        if index:
            return get_po_full_match(" ".join(po_ar[index + 1:]))

    return None


def build_switch_html_table(hostname, po_list):
    html = "<TABLE BORDER=\"1\"><TR><TD COLSPAN=\"3\">{0}</TD></TR>".format(hostname)

    for po in po_list:
        first_port = "<TD></TD>" if len(po["ports"]) == 0 else "<TD PORT=\"{0}\">{1}</TD>".format((po["ports"][0])[:-3],
                                                                                                  po["ports"][0])

        html = html + "<TR><TD ROWSPAN=\"{0}\">{1}</TD>{2}<TD ROWSPAN=\"{0}\">{1}</TD></TR>".format(len(po["ports"]),
                                                                                                    po["group"],
                                                                                                    first_port)

        if len(po["ports"]) > 1:
            for port in po["ports"][1:]:
                html = html + "<TR><TD PORT=\"{0}\">{1}</TD></TR>".format(port[:-3], port)

    html = html + "</TABLE>"

    return html


def process_device(device_dict, graph, visited_devices, last_device, radius):
    radius = radius + 1
    print("processing device: {0} {1} {2} / {3}".format(radius, len(visited_devices), device_dict["DEVICE_ID"],
                                                        device_dict["IP_ADDRESS"]))
    visited_devices.append(device_dict["DEVICE_ID"])
    try:
        device_conn = netmiko.ConnectHandler(device_type="cisco_ios",
                                             ip=device_dict["IP_ADDRESS"],
                                             username=device_dict["USERNAME"],
                                             password=device_dict["PASSWORD"],
                                             keepalive=30)

        device_conn.send_command("terminal length 0")
        hostname = device_conn.find_prompt()[:-1]
        cdp_output_raw = device_conn.send_command("show cdp neighbors detail")
        device_conn.send_command("terminal length 30")

        cdp_entries = parse_cdp_detail_raw(cdp_output_raw)

        graph.node(hostname)

        for entry in cdp_entries:
            if entry["cisco"]:
                # if entry["device_id"] not in visited_devices:
                if entry["device_id"] != last_device:
                    graph.edge(hostname, entry["device_id"])
                #    graph.node(entry["device"])

                if radius <= MAX_RADIUS:
                    device_dict["IP_ADDRESS"] = entry["ip_address"]
                    device_dict["DEVICE_ID"] = entry["device_id"]
                    graph, visited_devices = process_device(device_dict, graph, visited_devices, hostname, radius)
                else:
                    graph.node(entry["device_id"])

        device_conn.disconnect()
    except (netmiko.ssh_exception.NetMikoTimeoutException,
            netmiko.ssh_exception.SSHException,
            netmiko.ssh_exception.NetMikoAuthenticationException) as exc:
        print(exc)

    return graph, visited_devices


def just_get_hostname(device_dict):
    device_conn = netmiko.ConnectHandler(device_type="cisco_ios",
                                         ip=device_dict["IP_ADDRESS"],
                                         username=device_dict["USERNAME"],
                                         password=device_dict["PASSWORD"],
                                         keepalive=30)

    device_conn.send_command("terminal length 0")
    hostname = device_conn.find_prompt()
    device_conn.disconnect()

    return hostname[:-1]


def main():
    g1 = gv.Graph(format="svg")
    with open("cdpgv_config.json", "r") as json_file:
        d = json.load(json_file)
        for device in d["DEVICES"]:
            try:
                device["DEVICE_ID"] = just_get_hostname(device)
                graph, visited_devices = process_device(device, g1, [], None, 0)
            except netmiko.ssh_exception.NetMikoTimeoutException as e1:
                print(e1)

        filename = graph.render(filename='./topology')
        print(filename)


if __name__ == "__main__":
    main()
