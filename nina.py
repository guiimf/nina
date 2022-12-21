#!/usr/bin/env python3

import argparse
import urllib3
import warnings
import sys
import socket
import pathlib
import requests
import json
import re
import os
import dns.zone
import dns.resolver
import dns.query
from time import sleep
from prettytable import PrettyTable
from bs4 import BeautifulSoup as bs 
from urllib.parse import urljoin, urlparse

try:
    import concurrent.futures
except ImportError:
    print("[!] Nina needs python 3.4 > ro run!")
    sys.exit()

# Args parsing
def arguments():
    
    a = argparse.ArgumentParser(description="Nina Recon Tool")
    a.add_argument("-d", "--domain", help="Domain to start recon", required=False)
    a.add_argument("-o", "--output", help="Save a directory containing Markdown file with recon report.", required=False, action='store_true')
    a.add_argument("-A", "--all", help="Permorm all options at once, except -s and -o (which can be added manually)", required=False, action='store_true')
    a.add_argument("--whois", help="Perform a Whois lookup.", required=False, action='store_true')
    a.add_argument("-D", "--dns", help="Look for some DNS information", required=False, action='store_true')
    a.add_argument("-a", "--axfr", help="Try a domain zone transfer attack", required=False, action='store_true')
    a.add_argument("-s", "--subdomains", help="Do a search for any subdomain registered", required=False, action='store_true')
    a.add_argument("-t", "--tech", help="Try to discover technologies in the page", required=False, action='store_true')
    a.add_argument("-c", "--cors", help="Try to find CORS misconfigurations", required=False, action='store_true')
    a.add_argument("-b", "--backups", help="Try to find some commom backup files in the page. This option works better with -s enabled.", required=False, action='store_true')
    a.add_argument("-w", "--waf", help="Try to detect WAF on the page.", required=False, action='store_true')
    a.add_argument("--hunt", help="Try to find usefull information about exploiting vectors.", required=False, action='store_true')
    a.add_argument("-r", "--repos", help="Try to discover valid repositories of the domain. This option works better with -s enabled.", action='store_true', required=False)
    a.add_argument("--threads", help="Threads (default 5)", type=int, default=5)
    a.add_argument("-V", "--version", help="Show the version", required=False, action='store_true')
    return a.parse_args()


def banner():
    print("""
    NINA RECON TOOL

              .--~~,__
 :-....,-------`~~'._.'
  `-,,,  ,_      ;'~U' 
   _,-' ,'`-__; '--.
  (_/'~~      ''''(;

      by H41stur
          """)

# Check if domain is a valid domain
def validDomain(domain):
    
    try:
        h = socket.gethostbyname(domain)
    except:
        print(f"\n[!] The domain doesn't respond")
        sys.exit(0)

# DNS information function
def dns_information(domain, store, dirFile):

    print(f"\n[*] Discovering some DNS information from {domain}...\n")
    sleep(0.2)
    registry = []

    mail = ""
    txt = ""
    ns = ""
    try:
        mail = dns.resolver.resolve(domain, 'MX')
    except:
        pass
    if mail:
        print("[+] Mail Servers:")
        for s in mail:
            registry.append(f"Mail Server,{str(s).split(' ')[1]}")
            print(f"\t - {str(s).split(' ')[1]}")

    try:
        txt = dns.resolver.resolve(domain, 'TXT')
    except:
        pass
    if txt:

        reg = []

        print("\n[+] TXT Records:")
        for i in txt:
            i = i.to_text()
            registry.append(f"TXT Records,{i}")
            if "?all" in i or "~all" in i or "spf" in i and "all" not in i:
                reg = i
                vulnerability.append(f"Infra, E-mail Spoofing, Possible, [9.1](https://www.first.org/cvss/calculator/3.1#CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N), TXT Record: {i}")
            print(f"\t - {i}")

        if reg:
            print(f"\n[!] Possible e-mail spoofing vulnerability in TXT record: {reg}")
    
    try:
        ns = dns.resolver.resolve(domain, 'NS')
    except:
        pass
    if ns:
        print("\n[+] Name Servers:")
        for n in ns:
            registry.append(f"Name Server,{str(n)}")
            print(f"\t - {str(n)}")

    if mail or txt or ns:
        if store:
            f = open(dirFile + "/" + domain + ".report.md", "a")
            f.write(f"\n\n## DNS information from {domain}\n\n")
            f.write("|" + " KEY \t\t\t\t| VALUE \t\t\t|\n" + "|" + "-"*47 + "|" + "-"*23 + "|\n")

            for i in registry:
                i = i.split(",")
                f.write(f"|{i[0]}|{i[1]}|\n")

        if store:
            f.close()



# Subdomain discovery function
def subDomain(domain, store, dirFile):

    print(f"\n[*] Discovering subdomains from {domain}...\n")
    sleep(0.1)
    subDoms = []

    # Consulting crt.sh
    try:
        r = requests.get(f"https://crt.sh/?q={domain}&output=json", timeout=20)
        file = json.dumps(json.loads(r.text), indent=4)
        sub_domains = sorted(set(re.findall(r'"common_name": "(.*?)"', file)))
        for sub in sub_domains:
            if sub.endswith(domain) and sub not in subDoms:
                subDoms.append(sub)
    except KeyboardInterrupt:
        sys.exit("[!] Interrupt handler received, exiting...\n")
    except:
        pass

    # Consulting Hackertarget
    try:
        r = requests.get(f"https://api.hackertarget.com/hostsearch/?q={domain}", timeout=20)
        sub_domains = re.findall(f'(.*?),', r.text)
        for sub in sub_domains:
            if sub.endswith(domain) and sub not in subDoms:
                subDoms.append(sub)
    except KeyboardInterrupt:
        sys.exit("[!] Interrupt handler received, exiting...\n")
    except:
        pass

    # Consulting RapidDNS
    try:
        r = requests.get(f"https://rapiddns.io/subdomain/{domain}", timeout=20)
        sub_domains = re.findall(r'target="_blank".*?">(.*?)</a>', r.text)
        for sub in sub_domains:
            if sub.endswith(domain) and sub not in subDoms:
                subDoms.append(sub)
    except KeyboardInterrupt:
        sys.exit("[!] Interrupt handler received, exiting...\n")
    except:
        pass

    # Consulting AlienVault
    try:
        r = requests.get(f"https://otx.alienvault.com/api/v1/indicators/domain/{domain}/passive_dns", timeout=20)
        sub_domains = sorted(set(re.findall(r'"hostname": "(.*?)"', r.text)))
        for sub in sub_domains:
            if sub.endswith(domain) and sub not in subDoms:
                subDoms.append(sub)
    except KeyboardInterrupt:
        sys.exit("[!] Interrupt handler received, exiting...\n")
    except:
        pass

    # Consulting URLScan
    try:
        r = requests.get(f"https://urlscan.io/api/v1/search/?q={domain}", timeout=20)
        sub_domains = sorted(set(re.findall(r'https://(.*?).' + domain, r.text)))
        for sub in sub_domains:
            if sub.endswith(domain) and sub not in subDoms:
                subDoms.append(sub)
    except KeyboardInterrupt:
        sys.exit("[!] Interrupt handler received, exiting...\n")
    except:
        pass

    # Consulting Riddler
    try:
        r = requests.get(f"https://riddler.io/search/exportcsv?q=pld:{domain}", timeout=20)
        sub_domains = re.findall(r'\[.*?\]",.*?,(.*?),\[', r.text)
        for sub in sub_domains:
            if sub.endswith(domain) and sub not in subDoms:
                subDoms.append(sub)
    except KeyboardInterrupt:
        sys.exit("[!] Interrupt handler received, exiting...\n")
    except:
        pass

    # Consulting ThreatMiner
    try:
        r = requests.get(f"https://api.threatminer.org/v2/domain.php?q={domain}&rt=5", timeout=20)
        file = json.loads(r.ontent)
        sub_domains = file['results']
        for sub in sub_domains:
            if sub.endswith(domain) and sub not in subDoms:
                subDoms.append(sub)
    except KeyboardInterrupt:
        sys.exit("[!] Interrupt handler received, exiting...\n")
    except:
        pass


    # open file to write
    if subDoms:
        if store:
            f = open(dirFile + "/" + domain + ".report.md", "a")
            f.write(f"\n\n## Subdomains from {domain}\n\n")
            f.write("|" + " SUBDOMAINS    \t\t\t\t| IP \t\t\t|\n" + "|" + "-"*47 + "|" + "-"*23 + "|\n")

        # interact through list and check the lenght
        table = PrettyTable(["SUBDOMAINS", "ip"])
        for s in subDoms:
            try:
                ip = socket.gethostbyname(s)
            except:
                ip = "Not found!"
            if store:
                f.write(f"| {s} | {ip} |\n")
            table.add_row([s, ip])
            table.align["SUBDOMAINS"] = "l"

        print(table)
        print("\nTotal discovered sudomains: " + str(len(subDoms)))

        if store:
            f.write("\n\n**Total discovered sudomains: " + str(len(subDoms)) + "**")
            f.close()

        return subDoms


# Domain zone transfer function
def zone_transfer(domain, store, dirFile):

    print(f"\n[*] Starting domain zone transfer attack...\n")
    sleep(0.2)
    hosts = []
    ns = []
    nsVuln = []

    # iterating through name servers to attack everyone
    try:
        name_servers = dns.resolver.resolve(domain, 'NS')
        for n in name_servers:
            ip = dns.resolver.resolve(n.target, 'A')
            ns.append(str(n))
            for i in ip:
                try:
                    zone = dns.zone.from_xfr(dns.query.xfr(str(i), domain))
                    for h in zone:
                        hosts.append(h)
                    if zone:
                        nsVuln.append(n)
                except Exception as e:
                    print("[!] NS {} refused zone transfer!\n".format(n))
                    continue
    except:
        print("[!] Unable to try zone transfer")

    if nsVuln:
        for i in nsVuln:
            vulnerability.append(f"Infra, DNS Zone Transfer, Certain, [5.3](https://www.first.org/cvss/calculator/3.1#CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N), Name Server: {i}")

    # open file to write
    if hosts:

        if store:
            f = open(dirFile + "/" + domain + ".report.md", "a")
            f.write(f"\n\n## Zone transfer from {domain}\n\n")
            f.write(f"The domain {domain} has {len(ns)} Name Servers:\n")
            f.write("| Name Servers |\n|--------------|\n")
            for n in ns:
                f.write(f"| {n} |\n")
            f.write("\n\n")
            f.write("|" + " ZONE TRANSFER \t\t\t\t| IP \t\t\t|\n" + "|" + "-"*47 + "|" + "-"*23 + "|\n")

        table = PrettyTable(["ZONE TRANSFER", "IP"])
        for i in hosts:
            if '@' not in i:
                s = str(i) + "." + domain
                try:
                    ip = socket.gethostbyname(s)
                except:
                    ip = "Not found!"

                if store:
                    f.write(f"| {s} | {ip} |\n")
                table.add_row([s, ip])
                table.align["ZONE TRANSFER"] = "l"

        print(table)

        if store:
            f.close()

def find_repos(domain, store, dirFile, subs):
    
    print(f"\n[*] Looking for public repositories...\n")
    sleep(0.2)

    if domain not in subs:
        subs.append(domain)

    git_repo = []
    git = []
    bit = []
    gitlab = []
    for i in subs:
        try:
            URL = f"https://{i}/.git/"
            r = requests.get(URL, verify=False, timeout=10)
            if f"{URL},{str(r.status_code)}" not in git_repo:
                git_repo.append(f"{URL},{str(r.status_code)}")
            print(f"Git directory in {URL} responds with {str(r.status_code)} status code.")
        except:
            pass

    try:
        URL = f"https://bitbucket.org/{domain.split('.')[0]}"
        r = requests.get(URL, verify=False, timeout=20)
        bit.append(f"{URL},{r.status_code}")
        print(f"\nBitbucket repository in {URL} responds with {str(r.status_code)} status code.")
    except:
        pass

    try:
        URL = f"https://github.com/{domain.split('.')[0]}"
        r = requests.get(URL, verify=False, timeout=20)
        if str(r.status_code) == "200":
            git.append(f"{URL},{r.status_code}")
            print(f"\nGithub repository in {URL} responds with {str(r.status_code)} status code.")
    except:
        pass

    try:
        URL = f"https://gitlab.com/{domain.split('.')[0]}"
        r = requests.get(URL, verify=False, timeout=20)
        if str(r.status_code) == "200":
            gitlab.append(f"{URL},{r.status_code}")
            print(f"\nGitlab repository in {URL} responds with {str(r.status_code)} status code.")
    except:
        pass

    if git_repo or bit or git or gitlab:
        if store:
            f = open(dirFile + "/" + domain + ".report.md", "a") 
            f.write(f"\n\n## Public repositories from {domain}\n\n")

            if git_repo:
                f.write("### Git repositories:\n\n")
                f.write("|" + " URL \t\t\t\t| STATUS \t\t\t|\n" + "|" + "-"*47 + "|" + "-"*23 + "|\n")
                for i in git_repo:
                    f.write(f"| {i.split(',')[0]} | {i.split(',')[1]} |\n")
                f.write("\n\n")

            if bit:
                f.write("### Bitbucket repositories:\n\n")
                f.write("|" + " URL \t\t\t\t| STATUS \t\t\t|\n" + "|" + "-"*47 + "|" + "-"*23 + "|\n")
                for i in bit:
                    f.write(f"| {i.split(',')[0]} | {i.split(',')[1]} |\n")
                f.write("\n\n")

            if git:
                f.write("### GitHub repositories:\n\n")
                f.write("|" + " URL \t\t\t\t| STATUS \t\t\t|\n" + "|" + "-"*47 + "|" + "-"*23 + "|\n")
                for i in git:
                    f.write(f"| {i.split(',')[0]} | {i.split(',')[1]} |\n")
                f.write("\n\n")

            if gitlab:
                f.write("### GitLab repositories:\n\n")
                f.write("|" + " URL \t\t\t\t| STATUS \t\t\t|\n" + "|" + "-"*47 + "|" + "-"*23 + "|\n")
                for i in gitlab:
                    f.write(f"| {i.split(',')[0]} | {i.split(',')[1]} |\n")
                f.write("\n\n")

        if store:
            f.close()

# request to detect WAF function
def request_waf(subdomain):

    WAF = []
    try:
        r = requests.get("https://raw.githubusercontent.com/h41stur/nina/main/src/references_recon.json", verify=False, timeout=10)
        wafSignatures = json.loads(r.text)
        wafSignatures = wafSignatures["WAF"]
    except:
        with open(srcPath + "references_recon.json", "r") as file:
            wafSignatures = json.load(file)
            wafSignatures = wafSignatures["WAF"]

    URL = f"https://{subdomain}/../../../../etc/passwd"
    try:
        r = requests.get(URL, verify=False, timeout=10)
        status = str(r.status_code)
        content = r.text
        headers = str(r.headers)
        cookie = str(r.cookies.get_dict())

        if int(status) >= 400:
            wafMatch = [0, None]
            for name, sign in wafSignatures.items():
                score = 0
                contentSign = sign["page"]
                statusSign = sign["code"]
                headersSign = sign["headers"]
                cookieSign = sign["cookie"]
                if contentSign:
                    if re.search(contentSign, content, re.I):
                        score += 1
                if statusSign:
                    if re.search(statusSign, status, re.I):
                        score += 0.5
                if headersSign:
                    if re.search(headersSign, headers, re.I):
                        score += 1
                if cookieSign:
                    if re.search(cookieSign, cookie, re.I):
                        score += 1
                if score > wafMatch[0]:
                    del wafMatch[:]
                    wafMatch.extend([score, name])
 
            if wafMatch[0] != 0:
                print(f"[+] WAF {wafMatch[1]} detected on https://{subdomain}")
                return f"{subdomain},{wafMatch[1]}"
            else:
                print(f"[-] An error has ocurred or unable to enumerate on https://{subdomain}")
                return None
    except KeyboardInterrupt:
        sys.exit("[!] Interrupt handler received, exiting...\n")
    except:
        print(f"[-] URL https://{subdomain} not accessible")
        return None



# detect WAF function
def detect_waf(domain, store, dirFile, subs, srcPath):

    print(f"\n[*] Detecting WAF...\n")
    sleep(0.2)
    if domain not in subs:
        subs.append(domain)
    WAF = []

    try:
        r = requests.get("https://raw.githubusercontent.com/h41stur/nina/main/src/references_recon.json", verify=False, timeout=10)
        wafSignatures = json.loads(r.text)
        wafSignatures = wafSignatures["WAF"]

    except Exception as e:
        with open(srcPath + "references_recon.json", "r") as file:
            wafSignatures = json.load(file)
            wafSignatures = wafSignatures["WAF"]

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=THREADS)
    data = (pool.submit(request_waf, s) for s in subs)
    for resp in concurrent.futures.as_completed(data):
        resp = resp.result()
        if resp is not None and resp not in WAF:
            WAF.append(resp)

    if WAF:
        if store:
            f = open(dirFile + "/" + domain + ".report.md", "a")
            f.write(f"\n\n## WAFs detected on scope {domain}\n\n")
            f.write("|" + " URL \t\t\t\t| WAF \t\t\t|\n" + "|" + "-"*47 + "|" + "-"*23 + "|\n")

            for i in WAF:
                f.write(f"| {i.split(',')[0]} | {i.split(',')[1]} |\n")

        if store:
            f.close()

# Whois lookup function
def whois_lookup(domain, store, dirFile):

    print(f"\n[*] Performing WHOIS Lookup...\n")
    import whois
    sleep(2)
    lookup = []

    try:
        w = whois.whois(domain)
    except:
        w = whois.query(domain)

    try:
        for i in w:
            if i not in lookup:
                lookup.append(f"{i}~{w[i]}")
    except:
        print(f"\nAn error has ocurred or unable to whois {domain}")

    if lookup:

        if store:
            f = open(dirFile + "/" + domain + ".report.md", "a")
            f.write(f"\n\n## Whois lookup from {domain}\n\n")
            f.write("|" + " KEY \t\t\t\t| VALUE \t\t\t|\n" + "|" + "-"*47 + "|" + "-"*23 + "|\n")

        table = PrettyTable(["KEY", "VALUE"])
        for i in lookup:
            s = i.split("~")[0]
            v = i.split("~")[1]

            if store:
                f.write(f"| {s} | {v} |\n")
            table.add_row([s, v])
            table.align = "l"

        print(table)

        if store:
            f.close()

# backups request function
def request_bkp(subdomain):
    
    ext = ["sql.tar","tar","tar.gz","gz","tar.bzip2","sql.bz2","sql.7z","zip","sql.gz","7z"]
    hostname = domain.split(".")[0]
    filenames = [hostname, domain, "backup", "admin", "wordpress"]
    proto = ["http://", "https://"]

    for p in proto:
        for f in filenames:
            for e in ext:
                URL = f"{p}{subdomain}/{f}.{e}"
                try:
                    r = requests.get(URL, verify=False, timeout=4)
                    status = r.status_code
                except KeyboardInterrupt:
                    sys.exit("[!] Interrupt handler received, exiting...\n")
                except:
                    continue
                if status != 400:
                    return f"{URL},{status}"
                else:
                    return None


# search backups function
def search_backups(domain, store, dirFile, subs):

    print(f"\n[*] Searching for backup files...\n")
    sleep(0.2)
    if domain not in subs:
        subs.append(domain)

    bkp = []
    
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=THREADS)
    data = (pool.submit(request_bkp, s) for s in subs)
    for resp in concurrent.futures.as_completed(data):
        resp = resp.result()
        if resp is not None and resp not in bkp:
            bkp.append(resp)

    if bkp:
        
        if store:
            f = open(dirFile + "/" + domain + ".report.md", "a")
            f.write(f"\n\n## Backup files found\n\n")
            f.write("|" + " URL \t\t\t\t| STATUS \t\t\t|\n" + "|" + "-"*47 + "|" + "-"*23 + "|\n")

        table = PrettyTable(["URL", "STATUS"])
        for b in bkp:
            s = b.split(",")[0]
            v = b.split(",")[1]
            if store:
                f.write(f"| {s} | {v} |\n")
            table.add_row([s, v])
            table.align["URL"] = "l"

        print(table)

        if store:
            f.close()

    else:
        print("[-] No backup files found")

# request tech function
def request_tech(subdomain):

    schemas = ["https://", "http://"]
    techs = []

    try:
        from Wappalyzer import Wappalyzer, WebPage
        wapp = Wappalyzer.latest()
        for schema in schemas:
            web = WebPage.new_from_url(f"{schema}{subdomain}", verify=False)
            tech = wapp.analyze_with_versions(web)

            if tech != "{}":
                file = json.loads(json.dumps(tech, sort_keys=True, indent=4))
                print(f"[+] {subdomain}")
                for i in file:
                    try:
                        version = file[i]['versions'][0]
                    except:
                        version = "Version not found!"
                    if f"{subdomain},{i},{version}" not in techs:
                        techs.append(f"{subdomain},{i},{version}")
                    print(f"\t{i} - {version}")
                print("\n")
            else:
                print("[-] No common technologies found")
    except Exception as e:
        print(f"[-] An error has ocurred or unable to enumerate {subdomain}\n")

    if techs:
        return techs
    else:
        return None


# Discover technologies function
def tech(domain, store, dirFile, subs):

    print(f"\n[*] Searching for technologies...\n")
    sleep(0.2)
    if domain not in subs:
        subs.append(domain)
    techsWeb = []
    
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=THREADS)
    data = (pool.submit(request_tech, s) for s in subs)
    for resp in concurrent.futures.as_completed(data):
        resp = resp.result()
        if resp is not None and resp not in techsWeb:
            techsWeb.append(resp)

    if techsWeb:

        if store:
            f = open(dirFile + "/" + domain + ".report.md", "a")
            f.write(f"\n\n## Common technologies found\n\n")
            f.write("|" + " URL \t\t\t\t| TECHNOLOGY \t\t\t| VERSION \t\t\t|\n" + "|" + "-"*47 + "|" + "-"*23 + "|" + "-"*23 + "|\n")
            for tech in techsWeb:
                for i in tech:
                    i = i.split(",")
                    u = i[0]
                    t = i[1]
                    v = i[2]
                    f.write(f"| {u} | {t} | {v} |\n")
            f.close()

def sqli_form(f, errors):

    data = {}

    try:
        # get target URL
        action = f.attrs.get("action").lower()
    except Exception as e:
        print(e)
        action = None

    # get the form method
    method = f.attrs.get("method", "get").lower()

    # get datils from form
    details = []
    for tag in f.find_all("input"):
        in_type = tag.attrs.get("type", "text")
        name = tag.attrs.get("name")
        value = tag.attrs.get("value", "")
        details.append({"type": in_type, "name": name, "value": value})

    # returning values
    data["action"] = action
    data["method"] = method
    data["details"] = details
    
    return data

# request xss function
def request_xss(endpoint, references):

    xss = []
    
    for p in references["XSS"]:
        if re.findall(rf".*{p}.*?", endpoint):
            xss_url = re.findall(rf".*{p}.*?", endpoint)[0] + "XSS"
            if xss_url not in xss:
                xss.append(xss_url)
    if xss:
        for i in xss:
            print(f"[+] Possible XSS vector found in: {i}")
            vulnerability.append(f"WEB, XSS Reflected, Possible, [6.1](https://www.first.org/cvss/calculator/3.1#CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N), URL: {i}")
        return xss
    else:
        return None

# request json function
def request_json(endpoint):

    json_file = []

    if ".json" in endpoint and endpoint not in json_file:
        json_file.append(endpoint)
    if json_file:
        for i in json_file:
            print(f"[+] Json file found in: {i}")
            vulnerability.append(f"WEB, Information Disclosure, Possible, [3.7](https://www.first.org/cvss/calculator/3.1#CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N), URL: {i}")
        return json_file
    else:
        return None

# request open redirect function
def request_or(endpoint, references):

    or_file = []

    for p in references["REDIRECTS"]:
        if re.findall(rf".*{p}.*?", endpoint):
            red_url = re.findall(rf".*{p}.*?", endpoint)[0] + "OPEN-REDIRECT"
            if red_url not in or_file:
                or_file.append(red_url)
    if or_file:
        for i in or_file:
            print(f"[+] Possible open redirect vector found in: {i}")
            vulnerability.append(f"WEB, Information Disclosure, Possible, [4.7](https://www.first.org/cvss/calculator/3.1#CVSS:3.1/AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:N/A:N), URL: {i}")
        return or_file
    else:
        return None

# request SQLi in URL function
def request_sqli_url(endpoint, sql_errors):

    sqli_file = []

    # test on URL
    for p in "\"'":
        if "=" in endpoint:
            endpoint = endpoint.split("=")[0] + f"={p}"
            try:
                r = requests.get(endpoint, timeout=4).text
                for db, errors in sql_errors.items():
                    for error in errors:
                        if re.compile(error).search(r):
                            sqli_file.append(endpoint)
                            vulnerability.append(f"WEB, SQLi - {db}, Possible, [8.6](https://www.first.org/cvss/calculator/3.1#CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:N/A:N, URL: {e})")
                            print(f"Possible SQLi vector in db {db} in: {endpoint}")
                                    
            except:
                pass

# request SQLi in URL function
def request_sqli_forms(subdomain, sql_errors):

    sqli_file = []

    # test on forms
    
    forms = ""

    schemas = ["http://", "https://"]
    for schema in schemas:
        try:
            soup = bs(requests.get(f"{schema}{subdomain}", timeout=4, verify=False).content, "html.parser", from_encoding="iso-8859-1")
            forms = soup.find_all("form")
        except Exception as e:
            continue

        if forms:
            for f in forms:
                details = sqli_form(f, sql_errors)

                for p in "\"'":

                    # body to request
                    body = {}

                    for tag in details["details"]:
                        if tag["value"] or tag["type"] == "hidden":
                            try:
                                body[tag["name"]] = tag["value"] + p
                            except:
                                pass
                        elif tag["type"] != "submit":
                            body[tag["name"]] = f"nina{p}"

                    # join url with action
                    URL = urljoin(f"{schema}{subdomain}", details["action"])
                    if details["method"] == "post":
                        request = f"{URL}, POST"
                        r = requests.post(URL, data=body, verify=False, timeout=4).text
                    elif details["method"] == "get":
                        request = f"{URL}, GET"
                        r = requests.get(URL, params=body, verify=False, timeout=4).text

                    # test for errors
                    for db, errors in sql_errors.items():
                        for error in errors:
                            if re.compile(error).search(r):
                                sqli_file.append("{request[0]}, {request[1]}")
                                vulnerability.append(f"WEB, SQLi - {db}, Possible, [8.6](https://www.first.org/cvss/calculator/3.1#CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:N/A:N, URL: {schema}{subdomain})")
                                print(f"Possible SQLi vector in db {db} in: {subdomain}")

    if sqli_file:
        return sqli_file
    else:
        return None



# hunt information function
def hunt(domain, store, dirFile, subs, srcPath):

    print(f"\n[*] Searching for usefull information...\n")
    sleep(0.2)
    if domain not in subs:
        subs.append(domain)

    # get json references
    try:
        r = requests.get("https://raw.githubusercontent.com/h41stur/nina/main/src/references_recon.json", verify=False, timeout=10)
        references = json.loads(r.text)
    except:
        with open(srcPath + "references_recon.json", "r") as file:
            references = json.load(file)

    sql_errors = {
            "MySQL": (r"SQL syntax.*MySQL", r"Warning.*mysql_.*", r"MySQL Query fail.*", r"SQL syntax.*MariaDB server"),
            "PostgreSQL": (r"PostgreSQL.*ERROR", r"Warning.*\Wpg_.*", r"Warning.*PostgreSQL"),
            "Microsoft SQL Server": (r"OLE DB.* SQL Server", r"(\W|\A)SQL Server.*Driver", r"Warning.*odbc_.*", r"Warning.*mssql_", r"Msg \d+, Level \d+, State \d+", r"Unclosed quotation mark after the character string", r"Microsoft OLE DB Provider for ODBC Drivers"),
            "Microsoft Access": (r"Microsoft Access Driver", r"Access Database Engine", r"Microsoft JET Database Engine", r".*Syntax error.*query expression"),
            "Oracle": (r"\bORA-[0-9][0-9][0-9][0-9]", r"Oracle error", r"Warning.*oci_.*", "Microsoft OLE DB Provider for Oracle"),
            "IBM DB2": (r"CLI Driver.*DB2", r"DB2 SQL error"),
            "SQLite": (r"SQLite/JDBCDriver", r"System.Data.SQLite.SQLiteException"),
            "Informix": (r"Warning.*ibase_.*", r"com.informix.jdbc"),
            "Sybase": (r"Warning.*sybase.*", r"Sybase message")
    }

    endpoints = []
    edp_xss = []
    edp_json = []
    edp_red = []
    edp_sqli = []

    for s in subs:
        # Consulting wayback machine
        try:
            r = requests.get(f"http://web.archive.org/cdx/search/cdx?url=*.{s}/*&output=json&fl=original&collapse=urlkey", timeout=10)
            resp = r.json()
            resp = resp[1:]
            for i in resp:
                if i[0] not in endpoints:
                    endpoints.append(i[0])
        except Exception as e:
            pass

        # Consulting URLScan
        try:
            r = requests.get(f"https://urlscan.io/api/v1/search/?q=domain:{domain}", timeout=10)
            resp = json.loads(r.text)
            resp = resp["results"]
            for i in resp:
                i = i["task"]["url"]
                if i not in endpoints:
                    endpoints.append(i)
        except Exception as e:
            pass

    if url_original not in endpoints:
        endpoints.append(url_original)

    # iterating on endpoints
    if endpoints:

        pool = concurrent.futures.ThreadPoolExecutor(max_workers=THREADS)
        # try to find xss vectors
        print("[*] Searching for XSS vectors...\n")
        data = (pool.submit(request_xss, e, references) for e in endpoints)
        for resp in concurrent.futures.as_completed(data):
            resp = resp.result()
            if resp is not None and resp not in edp_xss:
                edp_xss.append(resp)
        if not edp_xss:
            print("\t[-] No XSS vectors found!")

        # try to find usefull json files
        print("\n[*] Searching for usefull json files...\n")
        data = (pool.submit(request_json, e) for e in endpoints)
        for resp in concurrent.futures.as_completed(data):
            resp = resp.result()
            if resp is not None and resp not in edp_json:
                edp_json.append(resp)
        if not edp_json:
            print("\t[-] No json file found!")

        # try to find open redirects
        print("\n[*] Searching for open redirect vectors...\n")
        data = (pool.submit(request_or, e, references) for e in endpoints)
        for resp in concurrent.futures.as_completed(data):
            resp = resp.result()
            if resp is not None and resp not in edp_red:
                edp_red.append(resp)
        if not edp_red:
            print("\t[-] No open redirect vectors found!")


        # try to find SQLi in URL
        print("\n[*] Searching for SQLi in URLs...\n")
        data = (pool.submit(request_sqli_url, e, sql_errors) for e in endpoints)
        for resp in concurrent.futures.as_completed(data):
            resp = resp.result()
            if resp is not None and resp not in edp_sqli:
                edp_sqli.append(resp)

        # try to find SQLi in forms
        print("\n[*] Searching for SQLi in forms...\n")
        try:
            url_sqli = url_original.split("://")[1]
        except:
            url_sqli = url_original

        subs_sqli = subs

        if url_sqli not in subs_sqli:
            subs_sqli.append(url_sqli)

        data = (pool.submit(request_sqli_forms, s, sql_errors) for s in subs_sqli)
        for resp in concurrent.futures.as_completed(data):
            resp = resp.result()
            if resp is not None and resp not in edp_sqli:
                edp_sqli.append(resp)

        if not edp_sqli:
            print("\t[-] No SQLi vectors found!")


        # preparing report
        if store:
            f = open(dirFile + "/" + domain + ".report.md", "a")
            f.write(f"\n\n## Usefull information\n\n")

            if edp_xss:
                f.write(f"\n\n### Possible XSS vectors\n\n")
                f.write("| URL \t\t\t\t|\n|" + "-"*47 + "|\n")
                for i in edp_xss:
                    f.write(f"| {i} |\n")

            if edp_json:
                f.write(f"\n\n### Json files\n\n")
                f.write("| URL \t\t\t\t|\n|" + "-"*47 + "|\n")
                for i in edp_json:
                    f.write(f"| {i} |")

            if edp_red:
                f.write(f"\n\n### Possible open redirect vectors\n\n")
                f.write("| URL \t\t\t\t|\n|" + "-"*47 + "|\n")
                for i in edp_red:
                    f.write(f"| {i} |")

            if edp_sqli:
                f.write(f"\n\n### Possible SQLi vectors\n\n")
                f.write("| URL \t\t\t\t| METHOD |\n|" + "-"*47 + "|" + "-"*47 + "|\n")
                for i in edp_sqli:
                    i = i.split(",")
                    f.write(f"| {i[0]} | {i[1]} |\n")

            f.close()


    else:
        print("[-] No information found")

# CORS testing function
# Based on Corsy - https://github.com/s0md3v/Corsy
def cors_testing(endpoint, headers):

    try:
        r = requests.get("https://raw.githubusercontent.com/h41stur/nina/main/src/references_recon.json", verify=False, timeout=10)
        CORS_VULN = json.loads(r.text)
        CORS_VULN = CORS_VULN["CORS"]
    except:
        with open(srcPath + "references_recon.json", "r") as file:
            CORS_VULN = json.load(file)
            CORS_VULN = CORS_VULN["CORS"]

    try:
        # origin reflected
        origin = 'https://h41stur.com'
        headers['Origin'] = origin
        header = ''
        r = requests.get(endpoint, headers=headers, verify=False, timeout=5)
        h = r.headers
        for key, value in h.items():
            if key.lower() == 'access-control-allow-origin':
                header = h
            if header:
                acao, acac = header.get('access-control-allow-origin', None), headers.get('access-control-allow-credentials', None)
                if acao and acao == (origin):
                    data = CORS_VULN['origin reflected']
                    data['acao header'] = acao
                    data['acac header'] = acac
                    return {endpoint: data}

        # post-domain wildcard
        origin = 'https://' + domain + '.h41stur.com'
        headers['Origin'] = origin
        header = ''
        r = requests.get(endpoint, headers=headers, verify=False, timeout=5)
        h = r.headers
        for key, value in h.items():
            if key.lower() == 'access-control-allow-origin':
                header = h
            if header:
                acao, acac = header.get('access-control-allow-origin', None), headers.get('access-control-allow-credentials', None)
                if acao and acao == (origin):
                    data = CORS_VULN['post-domain wildcard']
                    data['acao header'] = acao
                    data['acac header'] = acac
                    return {endpoint: data}

        # pre-domain wildcard
        origin = 'https://' + 'h41stur' + domain
        headers['Origin'] = origin
        header = ''
        r = requests.get(endpoint, headers=headers, verify=False, timeout=5)
        h = r.headers
        for key, value in h.items():
            if key.lower() == 'access-control-allow-origin':
                header = h
            if header:
                acao, acac = header.get('access-control-allow-origin', None), headers.get('access-control-allow-credentials', None)
                if acao and acao == (origin):
                    data = CORS_VULN['pre-domain wildcard']
                    data['acao header'] = acao
                    data['acac header'] = acac
                    return {endpoint: data}

        # null origin allowed
        origin = 'null'
        headers['Origin'] = origin
        header = ''
        r = requests.get(endpoint, headers=headers, verify=False, timeout=5)
        h = r.headers
        for key, value in h.items():
            if key.lower() == 'access-control-allow-origin':
                header = h
            if header:
                acao, acac = header.get('access-control-allow-origin', None), headers.get('access-control-allow-credentials', None)
                if acao and acao == (origin):
                    data = CORS_VULN['null origin allowed']
                    data['acao header'] = acao
                    data['acac header'] = acac
                    return {endpoint: data}

        # unrecognized underscore
        origin = 'https://' + domain + '_.h41stur.com'
        headers['Origin'] = origin
        header = ''
        r = requests.get(endpoint, headers=headers, verify=False, timeout=5)
        h = r.headers 
        for key, value in h.items():
            if key.lower() == 'access-control-allow-origin':
                header = h
            if header:
                acao, acac = header.get('access-control-allow-origin', None), headers.get('access-control-allow-credentials', None)
                if acao and acao == (origin):
                    data = CORS_VULN['unrecognized underscore']
                    data['acao header'] = acao
                    data['acac header'] = acac
                    return {endpoint: data}

        # broken parser
        origin = 'https://' + domain + '%60.h41stur.com'
        headers['Origin'] = origin
        header = ''
        r = requests.get(endpoint, headers=headers, verify=False, timeout=5)
        h = r.headers
        for key, value in h.items():
            if key.lower() == 'access-control-allow-origin':
                header = h
            if header:
                acao, acac = header.get('access-control-allow-origin', None), headers.get('access-control-allow-credentials', None)
                if acao and '`.h41stur.com' in acao:
                    data = CORS_VULN['broken parser']
                    data['acao header'] = acao
                    data['acac header'] = acac
                    return {endpoint: data}

        # unescaped regex
        loc = urlparse(endpoint).netloc
        if loc.count(".") > 1:
            origin = 'https://' + loc.replace(".", "x", 1)
            headers['Origin'] = origin
            header = ''
            r = requests.get(endpoint, headers=headers, verify=False, timeout=5)
            h = r.headers
            for key, value in h.items():
                if key.lower() == 'access-control-allow-origin':
                    header = h
                if header:
                    acao, acac = header.get('access-control-allow-origin', None), headers.get('access-control-allow-credentials', None)
                    if acao and acao == (origin):
                        data = CORS_VULN['unescaped regex']
                        data['acao header'] = acao
                        data['acac header'] = acac
                        return {endpoint: data}

        # http origin allowed
        origin = 'http://' + domain
        headers['Origin'] = origin
        header = ''
        r = requests.get(endpoint, headers=headers, verify=False, timeout=5)
        h = r.headers
        for key, value in h.items():
            if key.lower() == 'access-control-allow-origin':
                header = h
            if header:
                acao, acac = header.get('access-control-allow-origin', None), headers.get('access-control-allow-credentials', None)
                if acao and acao.startswith('http://'):
                    data = CORS_VULN['http origin allowed']
                    data['acao header'] = acao
                    data['acac header'] = acac
                    return {endpoint: data}

        # wildcard value and third party allowed
        loc = urlparse(endpoint).netloc
        origin = 'https://' + domain
        headers['Origin'] = origin
        header = ''
        r = requests.get(endpoint, headers=headers, verify=False, timeout=5)
        h = r.headers
        for key, value in h.items():
            if key.lower() == 'access-control-allow-origin':
                header = h
            if header:
                acao, acac = header.get('access-control-allow-origin', None), headers.get('access-control-allow-credentials', None)
                if acao and acao == "*":
                    data = CORS_VULN['wildcard value']
                    data['acao header'] = acao
                    data['acac header'] = acac
                    return {endpoint: data}

                if loc:
                    if urlparse(acao).netloc and urlparse(acao).netloc != loc:
                        data = CORS_VULN['third party allowed']
                        data['acao header'] = acao
                        data['acac header'] = acac
                        return {endpoint: data}

    except requests.exceptions.RequestException as e:
        if 'Failed to establish a new connection' in str(e):
            print(f"[!] URL {endpoint} is unreachable")
        elif 'requests.exceptions.TooManyRedirects:' in str(e):
            print(f"[!] URL {endpoint} has too many redirects")


# CORS misconfiguration function
def cors(domain, store, dirfile, subs, srcPath):

    print(f"\n[*] Searching for CORS misconfiguration...\n")
    sleep(0.2)
    if domain not in subs:
        subs.append(domain)


    headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:70.0) Gecko/20100101 Firefox/70.0',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip',
            'DNT': '1',
            'Connection': 'close',
        }

    endpoints = []
    schemas = ['https://', 'http://']
    scan = []

    for s in subs:

        #### Take a long long time
        # Consulting wayback machine
        #try:
        #    r = requests.get(f"http://web.archive.org/cdx/search/cdx?url=*.{s}/*&output=json&fl=original&collapse=urlkey", timeout=10)
        #    resp = r.json()
        #    resp = resp[1:]
        #    for i in resp:
        #        if i[0] not in endpoints:
        #            endpoints.append(i[0])
        #except:
        #    pass

        # Consulting URLScan
        #try:
        #    r = requests.get(f"https://urlscan.io/api/v1/search/?q=domain:{s}", timeout=10)
        #    resp = json.loads(r.text)
        #    resp = resp["results"]
        #    for i in resp:
        #        i = i["task"]["url"]
        #        if i not in endpoints:
        #            endpoints.append(i)
        #except:
        #    pass

        for schema in schemas:
            u = schema + s
            if u not in endpoints and "*" not in u:
                endpoints.append(u)

        
    # iterating on endpoints
    if endpoints:

        pool = concurrent.futures.ThreadPoolExecutor(max_workers=THREADS)
        data = (pool.submit(cors_testing, endpoint, headers) for endpoint in endpoints)
        for resp in concurrent.futures.as_completed(data):
            resp = resp.result()
            if resp is not None:
                scan.append(resp)

        if scan:
            if store:
                f = open(dirFile + "/" + domain + ".report.md", "a")
                f.write(f"\n\n## CORS misconfigurations\n\n")
                f.close()
            for resp in scan:
                for i in resp:
                    print(f"\n[+] {i}")
                    print(f"\t- Type: {resp[i]['class']}")
                    print(f"\t- Description: {resp[i]['description']}")
                    print(f"\t- Severity: {resp[i]['severity']}")
                    print(f"\t- Exploit: {resp[i]['exploitation']}")
                    print(f"\t- ACAO Header: {resp[i]['acao header']}")
                    print(f"\t- ACAC header: {resp[i]['acac header']}")
                    vulnerability.append(f"WEB, CORS Misconfiguration, Certain, {resp[i]['severity']}, URL: {i}")
                    if store:
                        f = open(dirFile + "/" + domain + ".report.md", "a")
                        f.write(f"\n\n### {i}\n\n")
                        f.write(f"\n\t- Type: {resp[i]['class']}")
                        f.write(f"\n\t- Description: {resp[i]['description']}")
                        f.write(f"\n\t- Severity: {resp[i]['severity']}")
                        f.write(f"\n\t- Exploit: {resp[i]['exploitation']}")
                        f.write(f"\n\t- ACAO Header: {resp[i]['acao header']}")
                        f.write(f"\n\t- ACAC Header: {resp[i]['acac header']}")
                        f.close()

        else:
            print("[-] No CORS misconfiguration found.")

# Program workflow
if __name__ == "__main__":

    banner()
    
    scriptPath = pathlib.Path(__file__).parent.resolve()
    srcPath = str(scriptPath) + "/src/" 
    version = "1.0"

    global vulnerability
    vulnerability = []

    urllib3.disable_warnings()
    warnings.simplefilter("ignore")
    
    parsing = arguments()

    # threads
    global THREADS
    THREADS = parsing.threads

    # show version
    if parsing.version:
        print(f"\nNina Recon Tool version: {version}")
        sys.exit(0)
    
    # working with domain
    global domain
    global url_original
    if not parsing.domain:
        print("\nerror: the following arguments are required: -d/--domain or -h/--help")
        sys.exit(0)
    else:
        domain = parsing.domain
        url_original = domain

    # Cleaning domain input
    if "." not in domain:
        print("\nInvalid domain format, please informe in format: example.com")
        sys.exit(0)
    if domain.startswith("https://"):
        domain = domain.split("https://")[1]
    if domain.startswith("http://"):
        domain = domain.split("http://")[1]

    if "/" in domain:
        domain = domain.split("/")[0]

    # validating domain
    validDomain(domain)

    # check if --ouput is passed
    if parsing.output:
        store = 1
        dirFile = str(scriptPath) + "/" + domain
        try:
            os.mkdir(dirFile)
        except FileExistsError:
            print(f"[-] The directory {dirFile} already exists!")
            #sys.exit(0)
        reportPath = dirFile + "/" + domain + ".report.md"
        if os.path.isfile(reportPath):
            os.remove(reportPath)
            with open(dirFile + "/" + domain + ".report.md", "w") as f:
                f.write(f"# NINA RECON TOOL REPORT FROM {domain.upper()}\n\n")
                f.close()

    else:
        store = 0
        dirFile = ''

    # start scan full
    if parsing.all:
        subs = []
        if parsing.subdomains:
            subs = subDomain(domain, store, dirFile)
        try:
            whois_lookup(domain, store, dirFile)
            dns_information(domain, store, dirFile)
            zone_transfer(domain, store, dirFile)
            cors(domain, store, dirFile, subs, srcPath)
            search_backups(domain, store, dirFile, subs)
            tech(domain, store, dirFile, subs)
            find_repos(domain, store, dirFile, subs)
            detect_waf(domain, store, dirFile, subs, srcPath)
            hunt(domain, store, dirFile, subs, srcPath)
        except KeyboardInterrupt:
            sys.exit("[!] Interrupt handler received, exiting...\n")
        sys.exit(0)


    # start scan single option
    # DNS information
    try:
        if parsing.dns:
            dns_information(domain, store, dirFile)
    except KeyboardInterrupt:
        sys.exit("[!] Interrupt handler received, exiting...\n")

    # subdomain enumeration
    subs = []
    try:
        if parsing.subdomains:
            subs = subDomain(domain, store, dirFile)
    except KeyboardInterrupt:
        sys.exit("[!] Interrupt handler received, exiting...\n")

    # Zone transfer attack
    try:
        if parsing.axfr:
            zone_transfer(domain, store, dirFile)
    except KeyboardInterrupt:
        sys.exit("[!] Interrupt handler received, exiting...\n")

    # find repos
    try:
        if parsing.repos:
            find_repos(domain, store, dirFile, subs)
    except KeyboardInterrupt:
        sys.exit("[!] Interrupt handler received, exiting...\n")

    # detect WAF
    try:
        if parsing.waf:
            detect_waf(domain, store, dirFile, subs, srcPath)
    except KeyboardInterrupt:
        sys.exit("[!] Interrupt handler received, exiting...\n")

    # Perform whois lookup
    try:
        if parsing.whois:
            whois_lookup(domain, store, dirFile)
    except KeyboardInterrupt:
        sys.exit("[!] Interrupt handler received, exiting...\n")

    # search for backups
    try:
        if parsing.backups:
            search_backups(domain, store, dirFile, subs)
    except KeyboardInterrupt:
        sys.exit("[!] Interrupt handler received, exiting...\n")

    # discover technologies
    try:
        if parsing.tech:
            tech(domain, store, dirFile, subs)
    except KeyboardInterrupt:
        sys.exit("[!] Interrupt handler received, exiting...\n")

    # HUNT!
    try:
        if parsing.hunt:
            hunt(domain, store, dirFile, subs, srcPath)
    except KeyboardInterrupt:
        sys.exit("[!] Interrupt handler received, exiting...\n")

    # CORS misconfiguration
    try:
        if parsing.cors:
            cors(domain, store, dirFile, subs, srcPath)
    except KeyboardInterrupt:
        sys.exit("[!] Interrupt handler received, exiting...\n")

    # print vulnerabilities
    if vulnerability:
        web = []
        infra = []
        if store:
            f = open(dirFile + "/" + domain + ".report.md", "a")
            f.write(f"\n\n## Vulnerabilities found\n\n")
            for i in vulnerability:
                i = i.split(",")
                if "WEB" in i[0]:
                    web.append(i)
                if "Infra" in i[0]:
                    infra.append(i)

            if infra:
                f.write(f"\n\n### Infra\n\n")
                f.write("| Vulnerability \t\t\t| Confidence \t\t\t| Endpoint \t\t\t| Severity \t\t\t|\n")
                f.write("|" + "-"*47 + "|" + "-"*47 + "|" + "-"*47 + "|" + "-"*47 + "|\n")

                for i in infra:
                    f.write(f"| {i[1]} | {i[2]} | {i[4]} | {i[3]} |\n")

            if web:
                f.write(f"\n\n### WEB\n\n")
                f.write("| Vulnerability \t\t\t| Confidence \t\t\t| Endpoint \t\t\t| Severity \t\t\t|\n")
                f.write("|" + "-"*47 + "|" + "-"*47 + "|" + "-"*47 + "|" + "-"*47 + "|\n")

                for i in web:
                    f.write(f"| {i[1]} | {i[2]} | {i[4]} | {i[3]} |\n")
            f.close()

    if store:
        print(f"\n\n[+] Report saved on {dirFile}/{domain}.report.md")

