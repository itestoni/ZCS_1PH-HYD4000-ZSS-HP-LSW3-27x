#!/usr/bin/python3

import sys
import socket
import binascii
import re
import libscrc
import json
import os
import configparser
import paho.mqtt.client as mqtt
import time
import datetime


def padhex(s):
    return '0x' + s[2:].zfill(4)

def hex_zfill(intval):
    hexvalue=hex(intval)
    return '0x' + str(hexvalue)[2:].zfill(4)

# Converti da signed a decimale
# Se il numero è già positivo non lo converte
def convertI16(responsereg):
  signed = int(str(responsereg),16) 
  if (signed > 2**15): signed = signed - 2**16
  return signed

def convertI32(responsereg):
  signed = int(str(responsereg),16) 
  if (signed > 2**31): signed = signed - 2**32
  return signed

os.chdir(os.path.dirname(sys.argv[0]))

# CONFIG
configParser = configparser.RawConfigParser()
configFilePath = r'./config.cfg'
configParser.read(configFilePath)

inverter_ip=configParser.get('SofarInverter', 'inverter_ip')
inverter_port=int(configParser.get('SofarInverter', 'inverter_port'))
inverter_sn=int(configParser.get('SofarInverter', 'inverter_sn'))
verbose=configParser.get('SofarInverter', 'verbose')
mqtt_publish=int(configParser.get('SofarInverter', 'mqtt_publish'))
mqtt_user = configParser.get('SofarInverter', 'mqtt_user')
mqtt_pass = configParser.get('SofarInverter', 'mqtt_pass')
mqtt_host= configParser.get('SofarInverter', 'mqtt_host')

now = datetime.datetime.now()
mqtt_last_reading = now.strftime("%Y-%m-%d %H:%M:%S")

# END CONFIG
#loop = ['0x0480', '0x04BC', '0x0580','0x05B3', '0x680', '0x069B']
loop = ['0x0684', '0x069B','0x0604', '0x060A','0x0484','0x04AF','0x0504','0x0521','0x05C4','0x05C4','0x0584','0x0589']
dict_battery = {}
dict_energy = {}
dict_on_grid_output = {}
dict_off_grid_output = {}
dict_pv_input = {}

reglen = 16





while loop:
    
    pfin=int(loop.pop(-1),0)
    pini=int(loop.pop(-1),0)


    # Data logger frame begin
    start = binascii.unhexlify('A5') # Logger Start code
    length=binascii.unhexlify('1700') # Logger frame DataLength
    controlcode= binascii.unhexlify('1045') # Logger ControlCode
    serial=binascii.unhexlify('0000') # Serial
    datafield = binascii.unhexlify('020000000000000000000000000000') # com.igen.localmode.dy.instruction.send.SendDataField
    # Modbus request begin
    pos_ini=str(hex_zfill(pini)[2:])
    pos_fin=str(hex_zfill(pfin-pini+1)[2:])
    if verbose=="1": print('\n\n\npfin = ' + str(pfin) + "\npini = " + str(pini))
    if verbose=="1": print('Pos ini = ' + pos_ini + "\nPos fin = " + pos_fin)

    businessfield= binascii.unhexlify('0003' + pos_ini + pos_fin) # Modbus data to count crc
    if verbose=="1": print('Modbus request: 0103 ' + pos_ini + " " + pos_fin +" "+str(padhex(hex(libscrc.modbus(businessfield)))[4:6])+str(padhex(hex(libscrc.modbus(businessfield)))[2:4]))
    crc=binascii.unhexlify(str(padhex(hex(libscrc.modbus(businessfield)))[4:6])+str(padhex(hex(libscrc.modbus(businessfield)))[2:4])) # CRC16modbus
    # Modbus request end
    checksum=binascii.unhexlify('00') #checksum F2
    endCode = binascii.unhexlify('15')# Logger End code
    inverter_sn2 = bytearray.fromhex(hex(inverter_sn)[8:10] + hex(inverter_sn)[6:8] + hex(inverter_sn)[4:6] + hex(inverter_sn)[2:4])
    frame = bytearray(start + length + controlcode + serial + inverter_sn2 + datafield + businessfield + crc + checksum + endCode)
    if verbose=="1":
        print("Hex string to send: A5 1700 1045 0000 " + hex(inverter_sn)[8:10] + hex(inverter_sn)[6:8] + hex(inverter_sn)[4:6] + hex(inverter_sn)[2:4] + " 020000000000000000000000000000 " + "0104" + pos_ini + pos_fin + str(hex(libscrc.modbus(businessfield))[3:5]) + str(hex(libscrc.modbus(businessfield))[2:3].zfill(2)) + " 00 15")
    if verbose=="1": print("Data sent: ", frame);
    # Data logger frame end

    checksum = 0
    frame_bytes = bytearray(frame)
    for i in range(1, len(frame_bytes) - 2, 1):
        checksum += frame_bytes[i] & 255
    frame_bytes[len(frame_bytes) - 2] = int((checksum & 255))

    # OPEN SOCKET
    for res in socket.getaddrinfo(inverter_ip, inverter_port, socket.AF_INET, socket.SOCK_STREAM):
                     family, socktype, proto, canonname, sockadress = res
                     try:
                      clientSocket= socket.socket(family,socktype,proto);
                      clientSocket.settimeout(15);
                      clientSocket.connect(sockadress);
                     except socket.error as msg:
                      print("Could not open socket - inverter/logger turned off");
                      if prometheus=="1": prometheus_file.close();
                      sys.exit(1)

    # SEND DATA
    clientSocket.sendall(frame_bytes);

    ok=False;
    while (not ok):
     try:
      data = clientSocket.recv(1024);
      ok=True
      try:
       data
      except:
       print("No data - Exit")
       sys.exit(1) #Exit, no data
     except socket.timeout as msg:
      print("Connection timeout - inverter and/or gateway is off");
      sys.exit(1) #Exit

    # PARSE RESPONSE (start position 56, end position 60)
    if verbose=="1": print("Data received: ", data);
    i=pfin-pini # Number of registers
    a=0 # Loop counter
    response=str(''.join(hex(ord(chr(x)))[2:].zfill(2) for x in bytearray(data))) #+'  '+re.sub('[^\x20-\x7f]', '', '')));
    if verbose=="1":
        hexstr=str(' '.join(hex(ord(chr(x)))[2:].zfill(2) for x in bytearray(data)))
        print("Hex string received:\n" + hexstr.upper())

#    print(pini)


    while a<=i:

     hexpos=str("0x") + str(hex(a+pini)[2:].zfill(4)).upper()
     if(int(hexpos, 16) > 1664): reglen = 32

     p1=56+(a*4)

     if(reglen == 16): p2=60+(a*4)
     else: p2=64+(a*4)


     responsereg=response[p1:p2]

     if(reglen == 16):
       signed = convertI16(responsereg)
     else:
       signed = convertI32(responsereg)
#       if verbose=="3": print(hexpos, responsereg, signed, str(int(signed)*0.01))

     if verbose=="1": print(p1, p2, responsereg)

#     if(str(hexpos) == "0x0684"): print(p1, p2, responsereg)
#     if(str(hexpos) == "0x0685"): print(p1, p2, responsereg)



     if verbose=="1": print("Register:",hexpos+" , value: hex:" +str(responsereg) + "; dec:"+str(int(signed)*0.01));

# Battery tutto ok
     if(str(hexpos) == "0x0604"):
       if verbose=="2": print("Battery: COMPLETO\n"+"* "+"Voltage_Bat1:\t"+str(int(signed)*0.1) + "V") # TENSIONE BATTERIA OK
       dict_battery ['Voltage_Bat1'] = str(int(signed)*0.1) 

     if(str(hexpos) == "0x0605"):
       if verbose=="2": print("* "+"Current_Bat1:\t"+str(int(signed)*0.01) + "A") # CORRENTE BATTERIA OK
       dict_battery ['Current_Bat1'] = str(int(signed)*0.01) 

     if(str(hexpos) == "0x0606"):
       if verbose=="2": print("* "+"Power_Bat1:\t"+str(int(signed)*0.01) + "kW") # POTENZA BATTERIA OK
       dict_battery ['Power_Bat1'] = str(int(signed)*0.01) 

     if(str(hexpos) == "0x0607"):
       if verbose=="2": print("* "+"Temperature_Env_Bat1:\t"+str(int(signed)*1) + "C") # TEMPERATURA BATTERIA OK
       dict_battery [ 'Temperature_Env_Bat1'] = str(int(signed)*1) 

     if(str(hexpos) == "0x0608"):
       if verbose=="2": print("* "+"SOC_Env_Bat1:\t"+str(int(signed)*1) + "%") # SOC BATTERIA OK
       dict_battery ['SOC_Env_Bat1'] = str(int(signed)*1) 

     if(str(hexpos) == "0x0609"):
       if verbose=="2": print("* "+"SOH_Bat1:\t"+str(int(signed)*1) + "%") # SOH BATTERIA OK
       dict_battery ['SOH_Bat1'] = str(int(signed)*1) 

     if(str(hexpos) == "0x060A"):
       if verbose=="2": print("* "+"ChargeCycle_Bat1:\t"+str(int(signed)*1) + "Cycle\n") # CICLI BATTERIA OK
       dict_battery ['ChargeCycle_Bat1'] = str(int(signed)*1)

##############################################################
# Energy
     if(str(hexpos) == "0x0685" or str(hexpos) == "0x0684"):
       if verbose=="2": print("Energy:\n* PV_Generation_Today:\t"+str(int(signed)*0.01) + "kWh") # POTENZA GENERATA OGGI OK
       dict_energy ['PV_Generation_Today'] = str(int(signed)*0.01) 

     if(str(hexpos) == "0x0687" or str(hexpos) == "0x0686"):
       if verbose=="2": print("* "+"PV_Generation_Total:\t"+str(int(signed)*0.1) + "kWh "+ responsereg)  # POTENZA GENERATA TOTALE OK
       dict_energy ['PV_Generation_Total'] = str(int(signed)*0.1)

     if(str(hexpos) == "0x0689" or str(hexpos) == "0x0688"):
       if verbose=="2": print("* "+"Load_Consumption_Today:\t"+str(int(signed)*0.01) + "kWh") 
       dict_energy ['Load_Consumption_Today'] = str(int(signed)*0.01)

     if(str(hexpos) == "0x068A"):
       if verbose=="2": print("* "+"Load_Consumption_Total:\t"+str(int(signed)*0.1) + "kWh") 
       dict_energy ['Load_Consumption_Total'] = str(int(signed)*0.1)

     if(str(hexpos) == "0x068D" or str(hexpos) == "0x068C"):
       if verbose=="2": print("* "+"Energy_Purchase_Today:\t"+str(int(signed)*0.01) + "kWh") # PRELIEVO DA RETE OK
       dict_energy ['Energy_Purchase_Today'] = str(int(signed)*0.01)

     if(str(hexpos) == "0x068E"):
       if verbose=="2": print("* "+"Energy_Purchase_Total:\t"+str(int(signed)*0.1) + "kWh") 
       dict_energy ['Energy_Purchase_Total'] = str(int(signed)*0.1)

     if(str(hexpos) == "0x0691" or str(hexpos) == "0x0690"):
       if verbose=="2": print("* "+"Energy_Selling_Today:\t"+str(int(signed)*0.01) + "kWh") 
       dict_energy ['Energy_Selling_Today'] = str(int(signed)*0.01)

     if(str(hexpos) == "0x0693" or str(hexpos) == "0x0692"):
       if verbose=="2": print("* "+"Energy_Selling_Total:\t"+str(int(signed)*0.01) + "kWh") 
       dict_energy ['Energy_Selling_Total'] = str(int(signed)*0.01)

     if(str(hexpos) == "0x0695" or str(hexpos) == "0x0694"):
       if verbose=="2": print("* "+"Bat_Charge_Today:\t"+str(int(signed)*0.01) + "kWh") # IMMISSIONE IN BATTERIA OK
       dict_energy ['Bat_Charge_Today'] = str(int(signed)*0.01) 

     if(str(hexpos) == "0x0696"):
       if verbose=="2": print("* "+"Bat_Charge_Total:\t"+str(int(signed)*0.1) + "kWh") 
       dict_energy ['Bat_Charge_Total'] = str(int(signed)*0.1) 

     if(str(hexpos) == "0x0699" or str(hexpos) == "0x0698"):
       if verbose=="2": print("* "+"Bat_Discharge_Today:\t"+str(int(signed)*0.01) + "kWh") # PRELIEVO DA BATTERIA OK
       dict_energy ['Bat_Discharge_Today'] = str(int(signed)*0.01) 

     if(str(hexpos) == "0x069A"):
       if verbose=="2": print("* "+"Bat_Discharge_Total:\t"+str(int(signed)*0.1) + "kWh\n") 
       dict_energy ['Bat_Discharge_Total'] = str(int(signed)*0.1) 

# ON GRID OUTPUT
     if(str(hexpos) == "0x0484"):
       if verbose=="2": print("\nON GRID OUTPUT:\n* Frequency_Grid:\t"+str(int(signed)*0.01) + "Hz") 
       dict_on_grid_output ['Frequency_Grid'] = str(int(signed)*0.01) 

     if(str(hexpos) == "0x0485"):
       if verbose=="2": print("* "+"ActivePower_Output_Total:\t"+str(int(signed)*0.01) + "kW") 
       dict_on_grid_output ['ActivePower_Output_Total'] = str(int(signed)*0.01) 

     if(str(hexpos) == "0x0486"):
       if verbose=="2": print("ReactivePower_Output_Total:\t"+str(int(signed)*0.01) + "kW") 
     if(str(hexpos) == "0x0487"):
       if verbose=="2": print("ApparentPower_Output_Total:\t"+str(int(signed)*0.01) + "kW") 

     if(str(hexpos) == "0x0488"):
       if verbose=="2": print("* "+"ActivePower_PCC_Total:\t"+str(int(signed)*0.01) + "kW") 
       dict_on_grid_output ['ActivePower_PCC_Total'] = str(int(signed)*0.01) 

     if(str(hexpos) == "0x0489"):
       if verbose=="2": print("ReactivePower_PCC_Total:\t"+str(int(signed)*0.01) + "kW") 
     if(str(hexpos) == "0x048A"):
       if verbose=="2": print("ApparentPower_PCC_Total:\t"+str(int(signed)*0.01) + "kW") 

     if(str(hexpos) == "0x048D"):
       if verbose=="2": print("* "+"Voltage_Phase_R:\t"+str(int(signed)*0.1) + "V") 
       dict_on_grid_output ['Voltage_Phase_R'] = str(int(signed)*0.1) 

     if(str(hexpos) == "0x048E"):
       if verbose=="2": print("Current_Output_R:\t"+str(int(signed)*0.01) + "A") 
       dict_on_grid_output ['Current_Output_R'] = str(int(signed)*0.01) 

     if(str(hexpos) == "0x048F"):
       if verbose=="2": print("ActivePower_Output_R:\t"+str(int(signed)*0.01) + "kW") 
     if(str(hexpos) == "0x0490"):
       if verbose=="2":  print("ReactivePower_Output_R:\t"+str(int(signed)*0.01) + "kW") 
     if(str(hexpos) == "0x0491"):
       if verbose=="2":  print("PowerFactor_Output_R:\t"+str(int(signed)*0.001) + "p.u.") 
     if(str(hexpos) == "0x0492"):
       if verbose=="2": print("* "+"Current_PCC_R:\t"+str(int(signed)*0.01) + "A") # CORRENTE SONDA TC OK
       dict_on_grid_output ['Current_PCC_R'] = str(int(signed)*0.01) 

     if(str(hexpos) == "0x0493"):
       if verbose=="2": print("ActivePower_PCC_R:\t"+str(int(signed)*0.01) + "kW") 

     if verbose=="2": 
       if(str(hexpos) == "0x0494"): print("ReactivePower_PCC_R:\t"+str(int(signed)*0.01) + "kW") 
       if(str(hexpos) == "0x0495"): print("PowerFactor_PCC_R:\t"+str(int(signed)*0.001) + "p.u") 

       if(str(hexpos) == "0x0498"): print("Voltage_Phase_S:\t"+str(int(signed)*0.1) + "V") 
       if(str(hexpos) == "0x0499"): print("Current_Phase_S:\t"+str(int(signed)*0.01) + "A") 
       if(str(hexpos) == "0x049A"): print("ActivePower_Output_S:\t"+str(int(signed)*0.01) + "kW") 
       if(str(hexpos) == "0x049B"): print("ReactivePower_Output_S:\t"+str(int(signed)*0.01) + "kW") 
       if(str(hexpos) == "0x049C"): print("PowerFactor_Output_S:\t"+str(int(signed)*0.001) + "p.u.") 
       if(str(hexpos) == "0x049D"): print("Current_PCC_S:\t"+str(int(signed)*0.01) + "A") 
       if(str(hexpos) == "0x049E"): print("ActivePower_PCC_S:\t"+str(int(signed)*0.01) + "kW") 
       if(str(hexpos) == "0x049F"): print("ReactivePower_PCC_S:\t"+str(int(signed)*0.01) + "kW") 
       if(str(hexpos) == "0x04A0"): print("PowerFactor_PCC_S:\t"+str(int(signed)*0.001) + "p.u") 

       if(str(hexpos) == "0x04A3"): print("Voltage_Phase_T:\t"+str(int(signed)*0.1) + "V") 
       if(str(hexpos) == "0x04A4"): print("Current_Phase_T:\t"+str(int(signed)*0.01) + "A") 
       if(str(hexpos) == "0x04A5"): print("ActivePower_Output_T:\t"+str(int(signed)*0.01) + "kW") 
       if(str(hexpos) == "0x04A6"): print("ReactivePower_Output_T:\t"+str(int(signed)*0.01) + "kW") 
       if(str(hexpos) == "0x04A7"): print("PowerFactor_Output_T:\t"+str(int(signed)*0.001) + "p.u.") 
       if(str(hexpos) == "0x04A8"): print("Current_PCC_T:\t"+str(int(signed)*0.01) + "A") 
       if(str(hexpos) == "0x04A9"): print("ActivePower_PCC_T:\t"+str(int(signed)*0.01) + "kW") 
       if(str(hexpos) == "0x04AA"): print("ReactivePower_PCC_T:\t"+str(int(signed)*0.01) + "kW") 
       if(str(hexpos) == "0x04AB"): print("PowerFactor_PCC_T:\t"+str(int(signed)*0.001) + "p.u") 

       if(str(hexpos) == "0x04AE"): print("ActivePower_PV_Ext:\t"+str(int(signed)*0.01) + "kW") 

     if(str(hexpos) == "0x04AF"):
       if verbose=="2": print("* "+"ActivePower_Load_Sys:\t"+str(int(signed)*0.01) + "kW\n") # POTENZA SONDA TC OK
       dict_on_grid_output ['ActivePower_Load_Sys'] = str(int(signed)*0.01) 


# OFF GRID OUTPUT
     if(str(hexpos) == "0x0504"):
       if verbose=="2": print("OFF GRID OUTPUT:\n* ActivePower_Load_Total:\t"+str(int(signed)*0.01) + "kW") 
       dict_off_grid_output ['ActivePower_Load_Total'] = str(int(signed)*0.01) 

     if(str(hexpos) == "0x0505"):
       if verbose=="2": print("ReactivePower_Load_Total:\t"+str(int(signed)*0.01) + "kW") 

     if(str(hexpos) == "0x0506"):
       if verbose=="2": print("ApparentPower_Load_Total:\t"+str(int(signed)*0.01) + "kW") 

     if(str(hexpos) == "0x0507"):
       if verbose=="2": print("* "+"Frequency_Output:\t"+str(int(signed)*0.01) + "Hz") 
       dict_off_grid_output ['Frequency_Output'] = str(int(signed)*0.01) 

     if(str(hexpos) == "0x050A"):
       if verbose=="2": print("Voltage_Output_R:\t"+str(int(signed)*0.1) + "V") 
#       dict_off_grid_output ['Voltage_Output_R'] = str(int(signed)*0.01) 

     if(str(hexpos) == "0x050B"):
       if verbose=="2": print("Current_Load_R:\t"+str(int(signed)*0.01) + "A") 
#       dict_off_grid_output ['Current_Load_R'] = str(int(signed)*0.01) 


# LOGGA VALORI INTERVALLO 
     if(int(hexpos, 16) > int("0x050B", 16) and int(hexpos, 16) < int("0x0520", 16)):
      if verbose=="2": print(str(hexpos) + "\t<<<>>>\t"+str(int(signed)*1) + " ???") 

# PV TUTTO OK
     if(str(hexpos) == "0x0584"):
       if verbose=="2": print("PV COMPLETO:\n* Voltage_PV1:\t"+str(int(signed)*0.1) + "V") # TENSIONE STRINGA 1 OK
       dict_pv_input ['Voltage_PV1'] = str(int(signed)*0.1)
     if(str(hexpos) == "0x0585"):
       if verbose=="2": print("* "+"Current_PV1:\t"+str(int(signed)*0.01) + "A") # CORRENTE STRINGA 1 OK
       dict_pv_input ['Current_PV1'] = str(int(signed)*0.01)

     if(str(hexpos) == "0x0586"):
       if verbose=="2": print("* "+"Power_PV1:\t"+str(int(signed)*0.01) + "kW") # POTENZA STRINGA 1 OK
       dict_pv_input ['Power_PV1'] = str(int(signed)*0.01)

     if(str(hexpos) == "0x0587"):
       if verbose=="2": print("* "+"Voltage_PV2:\t"+str(int(signed)*0.1) + "V") # TENSIONE STRINGA 2 OK
       dict_pv_input ['Voltage_PV2'] = str(int(signed)*0.1)

     if(str(hexpos) == "0x0588"):
       if verbose=="2": print("* "+"Current_PV2:\t"+str(int(signed)*0.01) + "A") # CORRENTE STRINGA 2 OK
       dict_pv_input ['Current_PV2'] = str(int(signed)*0.01)

     if(str(hexpos) == "0x0589"):
       if verbose=="2": print("* "+"Power_PV2:\t"+str(int(signed)*0.01) + "kW") # POTENZA STRINGA 2 OK
       dict_pv_input ['Power_PV2'] = str(int(signed)*0.01)

     if(str(hexpos) == "0x05C4"):
       if verbose=="2": print("* "+"Power_PV_Total:\t"+str(int(signed)*0.1) + "kW\n") # POTENZA TOTALE OK
       dict_pv_input ['Power_PV_Total'] = str(int(signed)*0.1)

# La sezione Energy Statistics (0x0680 - 0x069B) ha registri da 32 bit
     if(reglen == 32):
       a+=2
     else: a+=1


dict_msg = ["home/zcs_azzurro/battery",dict_battery]
dict_msg = ["home/zcs_azzurro/energy",dict_energy]
dict_msg = ["home/zcs_azzurro/on_grid_output",dict_on_grid_output]
dict_msg = ["home/zcs_azzurro/off_grid_output",dict_off_grid_output]
dict_msg = ["home/zcs_azzurro/pv_input",dict_pv_input]


# This is the Publisher

if (mqtt_publish > 0):

  client = mqtt.Client()
  client.username_pw_set(mqtt_user, mqtt_pass)
  client.connect(mqtt_host,1883,60)

  result =  client.publish("home/zcs_azzurro/battery/attributes", json.dumps(dict_battery), qos=0, retain=True)
  time.sleep(1)
  result =  client.publish("home/zcs_azzurro/battery/state", 1, qos=0, retain=True)
  time.sleep(.1)
  result =  client.publish("home/zcs_azzurro/energy/attributes",  json.dumps(dict_energy), qos=0, retain=True)
  time.sleep(1)
  result =  client.publish("home/zcs_azzurro/energy/state", 1, qos=0, retain=True)
  time.sleep(.1)
  result =  client.publish("home/zcs_azzurro/on_grid_output/attributes",  json.dumps(dict_on_grid_output), qos=0, retain=True)
  time.sleep(1)
  result =  client.publish("home/zcs_azzurro/on_grid_output/state", 1, qos=0, retain=True)
  time.sleep(.1)
  result =  client.publish("home/zcs_azzurro/off_grid_output/attributes",  json.dumps(dict_off_grid_output), qos=0, retain=True)
  time.sleep(1)
  result =  client.publish("home/zcs_azzurro/off_grid_output/state", 1, qos=0, retain=True)
  time.sleep(.1)
  result =  client.publish("home/zcs_azzurro/pv_input/attributes",  json.dumps(dict_pv_input), qos=0, retain=True)
  time.sleep(1)
  result =  client.publish("home/zcs_azzurro/pv_input/state", 1, qos=0, retain=True)
  time.sleep(.1)
  result =  client.publish("home/zcs_azzurro/last_reading", mqtt_last_reading, qos=0, retain=True)
  time.sleep(.1)

  client.disconnect();

#print("json_battery = "+json.dumps(dict_battery))
#print("json_energy = "+json.dumps(dict_energy))
#print("json_on_grid_output = "+json.dumps(dict_on_grid_output))
#print("json_off_grid_output = "+json.dumps(dict_off_grid_output))
#print("json_pv_input = "+json.dumps(dict_pv_input))
#print("last_reading = "+mqtt_last_reading)

