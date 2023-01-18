# ZCS 1PH HYD4000 ZSS HPLSW3-27xxx
ZCS Inverter (Sofar) 1PH HYD4000 ZSS HP + LSW-3/LSE SN 27xxx

This utility is derived from following repository:<br>
https://github.com/Nedel124/Sofar_G3_LSW3<br>
I have customized the python code to connect with Zucchetti Inverter ZCS 1PH HYD4000 ZSS HP using an USB Solarman Datalogger LSW3 with SN starting with 7xx.<br>

It will retrieve all significant inverter parameters which will be published via mqtt by means of JSON dictionaries.<br>
The Home Assistant folder contains all entities definitions which are mostly self explained.<br>

The utility is fully customizable by means of the config file where you can specify:<br>

- inverter_ip=192.168.1.xx (is recommended to assign static IP to the data logger)<br>
- inverter_port=8899<br>
- inverter_sn=(serial number of the solarman data logger 27xxx)<br>
- verbose=0 (level of verbosity for debug purposes)<br>
- mqtt_host=192.168.1.xx (mqtt server)<br>
- mqtt_publish=1 (0 means that the mqtt info will not be published)<br>
- mqtt_user= xxxxxxx<br>
- mqtt_pass= xxxxxx<br>

Thanks to @jlopez77 https://github.com/jlopez77<br>
Thanks to @MichaluxPL https://github.com/MichaluxPL<br>
For more information about the originator project please visit:<br>
https://github.com/Nedel124/Sofar_G3_LSW3<br>
Here you can find also Inverter's Register Map<br>

For more information about LSW-3 data logger:<br>
https://www.solarmanpv.com/products/data-logger/stick-logger/<br>
