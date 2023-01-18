# ZCS 1PH HYD4000 ZSS HPLSW3-7x
ZCS Inverter (Sofar) 1PH HYD4000 ZSS HP + LSW-3/LSE SN 7xxx
This utility is derived from following repository:
https://github.com/Nedel124/Sofar_G3_LSW3
I have customized the python code to connect with Zucchetti Inverter ZCS 1PH HYD4000 ZSS HP using an USB Solarman Datalogger LSW3 with SN starting with 7xx.

It will retrieve all significant inverter parameters which will be published via mqtt by means of JSON dictionaries.
The Home Assistant folder contains all entities definitions which are mostly self explained.

The utility is fully customizable by means of the config file where you can specify:

inverter_ip=192.168.1.xx (is recommended to assign static IP to the data logger)
inverter_port=8899
inverter_sn=(serial number of the solarman data logger 7xxx)
verbose=0 (level of verbosity for debug purposes)
mqtt_host=192.168.1.xx (mqtt server)
mqtt_publish=1 (0 means that the mqtt info will not be published)
mqtt_user= xxxxxxx
mqtt_pass= xxxxxx

For more information about the originator project please visit:
https://github.com/Nedel124/Sofar_G3_LSW3
Here you can find also Inverter's Register Map

For more information about LSW-3 data logger:
https://www.solarmanpv.com/products/data-logger/stick-logger/
