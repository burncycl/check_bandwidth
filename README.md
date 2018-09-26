# 2018/09 BuRnCycL 

Python3 Nagios+NRPE script to check bandwidth on Linux machine. 

Check uses /proc/dev/net to measure bandwidth on Linux systems. 

Outputs metrics using dynamic units (i.e. byte rate achieved). However, alert threshold and graphing units are statically configured. Works in conjunction with NRPE. 

Referenced: https://github.com/samyboy/check_iftraffic_nrpe.py , but desired metrics output. Didn't want to modify this codebase. Wrote my own. 

Dependency on Python3.

Command example:
```
python3 check_bandwidth.py -i eth0 -u kBps -l 2000 -w 85 -c 95 
```
This will monitor eth0. Outputting graphs in kilobytes. Setting a limit of 2000 kilobytes per second (or 2 Megabytes per second). Warning upon 85% and Critical upon 95% of 2 Megabytes.


/etc/nagios/nrpe.cfg example (used Centos 7 box with Python3.6 installed):
```
command[check_bandwidth]=/usr/bin/python3.6 {{ nagios_nrpe_server_plugins_dir }}/check_bandwidth.py -i eth0 -u kBps -l 2000 -w 90 -c 95
```
