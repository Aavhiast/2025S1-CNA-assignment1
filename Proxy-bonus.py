# ============================== BONUS IMPLEMENTED ====================================
# THIS FILE SuccessfulLLY IMPLEMENTS ALL 3 BONUS QUESTIONS ~~~
# HERE ARE SOME PROCESS EXPLANATIONS:
# 
# ✅ BONUS 1 – HANDLE CACHE EXPIRATION
# Before serving a cached file, we check if it's still valid.
# First we look for "Cache-Control: max-age"
# If not found, we fall back to checking "Expires" header
# If the cache is still fresh, we return it. Otherwise, we fetch a new version.
#
# TEST
# http://httpbin.org/cache/0        → always refetch (max-age = 0)
# http://httpbin.org/cache/10       → cache once, then expire after 10 seconds
# http://httpbin.org/cache/60       → manually waited 60s and re-sent request
# http://httpbin.org/response-headers?Expires=Thu,... → test "Expires" header
#
# Since waiting exactly 10s can be tricky in terminal,
# we restarted the proxy and timed the requests manually for clarity.
#
# ✅ BONUS 2 – HANDLE 301 / 302 REDIRECTION
# If a response is 301 or 302 with a "Location" header, we follow the redirect.
# This continues up to 5 times to avoid infinite loops.
#
# TEST
# http://httpbin.org/redirect-to?url=http://http.badssl.com&status_code=301
# http://httpbin.org/redirect-to?url=http://http.badssl.com&status_code=302
# http://github.com → this returns a 301 to https://github.com (as expected)
#
# ✅ BONUS 3 – HANDLE URLS WITH PORT NUMBERS
# Our proxy now supports URLs like `hostname:port/path`, not just hostname/path.
# We extract the port number if provided and use it when connecting to server.
#
# TEST
# http://http.badssl.com:80
# http://data.iana.org:80/time-zones/data/leap-seconds.list
#
#
# AFTERALL, ALL 3 BONUS WERE TESTED SUCCESSFULLY~~!
# THANKS FOR CHECKING THIS FILE~~
# ===================================================================================

import socket
import sys
import os
import argparse
import re
import time
from email.utils import parsedate_to_datetime  # to parse HTTP date formats

# 1MB BUFFER SIZE – THAT'S HOW MUCH WE READ FROM SOCKETS EACH TIME
BUFFER_SIZE = 1000000

# ==== PARSE COMMAND LINE ARGS ====
# We get our proxy's host and port number from the command line
parser = argparse.ArgumentParser()
parser.add_argument('hostname', help='IP address of the proxy server')
parser.add_argument('port', help='Port number for the proxy server')
args = parser.parse_args()
proxyHost = args.hostname
proxyPort = int(args.port)

# ==== CREATE AND BIND SERVER SOCKET ====
try:
    serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    print('Created socket')
    serverSocket.bind((proxyHost, proxyPort))
    print('Port is bound')
    serverSocket.listen(5)
    print('Listening to socket')
except Exception as e:
    print('Error setting up server:', e)
    sys.exit()

# ==== MAIN SERVER LOOP ====
while True:
    print('Waiting for connection...')
    try:
        clientSocket, clientAddress = serverSocket.accept()
        print('Received a connection')
    except:
        print('Failed to accept connection')
        continue

    try:
        message_bytes = clientSocket.recv(BUFFER_SIZE)
        message = message_bytes.decode('utf-8')
        print('Received request:')
        print('< ' + message)

        requestParts = message.split()
        method = requestParts[0]
        URI = requestParts[1]
        version = requestParts[2]

        print('Method:\t\t' + method)
        print('URI:\t\t' + URI)
        print('Version:\t' + version)
        print('')

        # ========== PARSE THE URI ==========
        URI = re.sub('^(/?)http(s?)://', '', URI, count=1)
        URI = URI.replace('/..', '')  # security
        resourceParts = URI.split('/', 1)

        # BONUS 3: PORT SUPPORT
        if ':' in resourceParts[0]:
            hostname, port = resourceParts[0].split(':')
            port = int(port)
        else:
            hostname = resourceParts[0]
            port = 80

        resource = '/' + resourceParts[1] if len(resourceParts) == 2 else '/'

        print('Requested Resource:\t' + resource)

        # ========== CACHE LOCATION SETUP ==========
        cacheLocation = './' + hostname + resource
        if cacheLocation.endswith('/'):
            cacheLocation += 'default'
        print('Cache location:\t\t' + cacheLocation)

        # ========== BONUS 1: CACHE EXPIRATION CHECK ==========
        if os.path.exists(cacheLocation):
            with open(cacheLocation, 'r', encoding='ISO-8859-1') as f:
                cacheData = f.readlines()

            isExpired = False
            for line in cacheData:
                if line.lower().startswith("cache-control") and "max-age" in line.lower():
                    match = re.search(r'max-age=(\d+)', line)
                    if match:
                        max_age = int(match.group(1))
                        cache_time = os.path.getmtime(cacheLocation)
                        if time.time() - cache_time > max_age:
                            print("CACHE EXPIRED (max-age)")
                            isExpired = True
                    break
                elif line.lower().startswith("expires"):
                    try:
                        expires_time = parsedate_to_datetime(line.split(":", 1)[1].strip()).timestamp()
                        if time.time() > expires_time:
                            print("CACHE EXPIRED (Expires header)")
                            isExpired = True
                    except:
                        pass
                    break

            if not isExpired:
                print("CACHE HIT! LOADING FROM CACHE")
                response = ''.join(cacheData).encode('ISO-8859-1')
                clientSocket.sendall(response)
                clientSocket.shutdown(socket.SHUT_WR)
                clientSocket.close()
                print("Client served and connection closed.")
                continue

        # ========== CONNECT TO ORIGIN SERVER ==========
        max_redirects = 5
        redirected = 0

        while redirected < max_redirects:
            originServerSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                address = socket.gethostbyname(hostname)
                originServerSocket.connect((address, port))

                originServerRequest = f"GET {resource} HTTP/1.1"
                originServerRequestHeader = f"Host: {hostname}"
                request = originServerRequest + '\r\n' + originServerRequestHeader + '\r\n\r\n'
                originServerSocket.sendall(request.encode())

                response = b''
                while True:
                    chunk = originServerSocket.recv(BUFFER_SIZE)
                    if not chunk:
                        break
                    response += chunk

                print("========== RAW RESPONSE BYTES ==========")
                print(response[:200])
                print("========================================")

                response_str = response.decode('ISO-8859-1', errors='ignore')
                headers = response_str.split('\r\n\r\n')[0]
                print("========== RAW RESPONSE HEADER ==========")
                print(headers)
                print("=========================================")

                if "HTTP/1.1 301" in response_str or "HTTP/1.1 302" in response_str:
                    print("Redirection detected!")
                    match = re.search(r"Location: (.+?)\r\n", response_str, re.IGNORECASE)
                    if match:
                        new_url = match.group(1).strip()
                        print("Redirecting to:", new_url)
                        URI = re.sub('^http(s?)://', '', new_url)
                        URI = URI.replace('/..', '')
                        resourceParts = URI.split('/', 1)
                        if ':' in resourceParts[0]:
                            hostname, port = resourceParts[0].split(':')
                            port = int(port)
                        else:
                            hostname = resourceParts[0]
                            port = 80
                        resource = '/' + resourceParts[1] if len(resourceParts) == 2 else '/'
                        originServerSocket.close()
                        redirected += 1
                        continue
                break
            except Exception as e:
                print("Failed to connect or follow redirect:", str(e))
                break

        # ========== SEND TO CLIENT ==========
        clientSocket.sendall(response)

        # ========== SAVE TO CACHE ==========
        cacheDir, file = os.path.split(cacheLocation)
        if not os.path.exists(cacheDir):
            os.makedirs(cacheDir)
        with open(cacheLocation, 'wb') as f:
            f.write(response)

        originServerSocket.close()
        clientSocket.shutdown(socket.SHUT_WR)
        clientSocket.close()
        print("Client served and connection closed.")

    except Exception as e:
        print("Error handling client request:", str(e))
        clientSocket.close()
