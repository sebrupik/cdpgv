import re

IOS_PO_SUMMARY = "(?P<group>\d+)\s+(?P<po>\S+)\s+(?P<protocol>\S+)\s+(?P<ports>\D.*\s)*"
IOS_PO_SUMMARY_SINGLE_LINE = "(?P<group>\d+)\s+(?P<po>\S+)\s+(?P<protocol>\S+)\s+(?P<ports>(\D\S*[)]\s*)*)"

print("ip domain-name blah.com".split()[2])


cdp_output = """Capability Codes: R - Router, T - Trans Bridge, B - Source Route Bridge
                  S - Switch, H - Host, I - IGMP, r - Repeater, P - Phone, 
                  D - Remote, C - CVTA, M - Two-port Mac Relay 

Device ID        Local Intrfce     Holdtme    Capability  Platform  Port ID
CHAN02-ACCESS-02.BLAH.COM
                 Ten 1/1/2         140              S I   WS-C3850- Ten 1/1/1
CHAN02-ACCESS-02.BLAH.COM
                 Gig 0/0           130              S I   WS-C3850- Gig 2/0/5
SEP1C6A7AE0E321  Gig 2/0/24        158              H P   CTS-CODEC eth0
chan01-3850-access-c
                 Ten 1/1/1         159             R S I  WS-C3850- Ten 2/1/2
CHAN-DESKTOP-43.BLAH.com
                 Gig 6/0/12        132              S I   WS-C3560C Gig 0/1
CHAN-DESKTOP-50.blah.com
                 Gig 3/0/5         167              S I   WS-C3560C Gig 0/1
CHAN-DESKTOP-14.blah.com
                 Gig 5/0/8         143              S I   WS-C3560C Gig 0/1
CHAN-DESKTOP-GB.blah.com
                 Gig 4/0/2         130             R S I  WS-C3560C Gig 0/1
chan02-dist-sw-2(SSI19120A0K)
                 Ten 6/1/4         129             S I C  N5K-C5548 Eth 1/2
chan02-dist-sw-1(SSI19120A1H)
                 Ten 1/1/4         130             S I C  N5K-C5548 Eth 1/2
CHAN02-CI-CROFT-CORE.BLAH.COM
                 Gig 6/0/46        148             R S I  WS-C3750X Fas 0
CHAN-DESKTOP-2.blah.com
                 Gig 1/0/44        130              S I   WS-C2960C Gig 0/1
sebs-desktop-sw  Gig 4/0/1         129             R S I  WS-C3560C Gig 0/14
CHAN-DESKTOP-6.blah.com
                 Gig 6/0/39        171              S I   WS-C2960C Gig 0/1

Total cdp entries displayed : 15
"""

po_output = """Flags:  D - down        P - bundled in port-channel
        I - stand-alone s - suspended
        H - Hot-standby (LACP only)
        R - Layer3      S - Layer2
        U - in use      N - not in use, no aggregation
        f - failed to allocate aggregator

        M - not in use, no aggregation due to minimum links not met
        m - not in use, port not aggregated due to minimum links not met
        u - unsuitable for bundling
        d - default port

        w - waiting to be aggregated
Number of channel-groups in use: 19
Number of aggregators:           19

Group  Port-channel  Protocol    Ports
------+-------------+-----------+-----------------------------------------------
10     Po10(RD)         -        
11     Po11(RU)         -        Gi2/2/1(P)     Gi2/2/2(P)     
12     Po12(RU)         -        Gi1/2/1(P)     Gi1/2/2(P)     
13     Po13(SU)        LACP      Te1/5/5(P)     Te1/6/5(P)     
14     Po14(SU)        LACP      Te2/5/5(P)     Te2/6/5(P)     
15     Po15(SU)        LACP      Gi1/5/1(P)     Gi1/6/1(P)     
16     Po16(SU)        LACP      Gi2/5/1(P)     Gi2/6/1(P)     
17     Po17(SD)        LACP      Gi1/1/45(D)    Gi1/1/46(D)    
18     Po18(SU)        LACP      Te1/3/3(P)     Te1/4/3(P)     
22     Po22(RD)         -        
50     Po50(SU)         -        Te1/4/9(P)     Te2/4/5(D)     Te2/4/9(P)     
60     Po60(SU)        LACP      Gi1/2/15(P)    Gi1/2/16(P)    
100    Po100(SU)       LACP      Te1/3/1(P)     Te2/3/2(P)     
102    Po102(SU)       LACP      Te1/3/9(P)     Te2/3/9(P)     
200    Po200(SU)        -        Te1/3/2(P)     Te2/3/1(P)     
210    Po210(SU)        -        Gi1/2/4(P)     Gi2/2/4(P)     
211    Po211(SU)        -        Te1/3/13(P)    Te2/3/13(P)    
501    Po501(RU)        -        Te1/5/4(P)     Te1/6/4(P)     
502    Po502(RU)        -        Te2/5/4(P)     Te2/6/4(P)"""


def get_po_full_match(input_str):
    port_channels = []

    for match in re.finditer(IOS_PO_SUMMARY_SINGLE_LINE, input_str, re.S):
        match_dict = dict()
        match_dict["group"] = match.group("group")
        match_dict["po"] = match.group("po")
        if match.group("ports"):
            match_dict["ports"] = match.group("ports").split()
        else:
            match_dict["ports"] = []

        port_channels.append(match_dict)

    return port_channels


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


print(build_switch_html_table("BLAH", parse_po_summary_raw(po_output, "IOS")))