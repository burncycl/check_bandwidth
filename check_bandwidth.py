#!/usr/bin/env python3

# 2018/09 BuRnCycL 
# Check uses /proc/dev/net to measure bandwidth on Linux systems.
# Outputs metrics using dynamic units (i.e. byte rate achieved). However, alert threshold and graphing units are statically configured. Works in conjunction with NRPE.
# Referenced: https://github.com/samyboy/check_iftraffic_nrpe.py , but desired metrics output. Didn't want to modify this codebase. Wrote my own.
# Dependency on Python3

import os, shutil, sys, argparse
from time import time


class BandwidthMonitoring:
    def __init__(self, INTERFACE=None, UNITS=None, LIMIT_THRESHOLD=None, WARNING_THRESHOLD=None, CRITICAL_THRESHOLD=None):
        # Declare variables, not war.
        self.wanted_interface_stats = INTERFACE
        self.units = UNITS
        self.limit_threshold = LIMIT_THRESHOLD
        self.warning_threshold = (float(WARNING_THRESHOLD) * float(LIMIT_THRESHOLD) / float(100)) # Convert percent to a comparable value.
        self.critical_threshold = (float(CRITICAL_THRESHOLD) * float(LIMIT_THRESHOLD) / float(100)) # Convert percent to a comparable value.
        self.current_stats_file = '/proc/net/dev' # Hard-coded location of current interface stats.
        self.reference_stats_file = '/var/tmp/traffic_stats.dat' # Hard-coded location of reference interface stats.

        # Function calls.
        self.bandwidth_check()


    # Parses /proc/net/dev styled data.
    def parse_stats(self, stats_file):
        interfaces = {} # Setup empty dictionary to be populated with interfaces key, values.

        try:
            f = open(stats_file, 'r')
            lines = f.readlines()
            f.close()

        except Exception as e:
            print('ERROR - Unable to open statistics file - {}'.format(e))
            self.create_new_reference_file() # The file may need to be deleted and recreated.
            sys.exit(1)

        # Retrive titles.
        titles = lines[1]
        _, rx_titles, tx_titles = titles.split('|')

        # Transform titles into list.
        rx_titles = list(['rx_' + a for a in rx_titles.split()])
        tx_titles = list(['tx_' + a for a in tx_titles.split()])

        # Append titles together.
        titles = rx_titles + tx_titles

        # Gather values.
        for line in lines[2:]:
            if line.find(':') < 0: continue
            # Get interface name
            if_name, data = line.split(':')
            if_name = if_name.strip()
            # Get values.
            values = [int(x) for x in data.split()]
            # Bring titles and values together to make interface data.
            if_data = dict(list(zip(titles, values)))
            interfaces[if_name] = if_data

        if self.wanted_interface_stats == None:
            available_interfaces = []
            for interface in interfaces:
                available_interfaces.append(interface)
            flat_available_interfaces = ', '.join(available_interfaces)
            print('ERROR - No interface specified. Available Interfaces: {}'.format(flat_available_interfaces))
            sys.exit(1)
        else:
            # Debugging
            #print(interfaces) # Output all interfaces.
            #print(interfaces[self.wanted_interface_stats]) # Output our wanted interface.
            return(interfaces[self.wanted_interface_stats])


    # Convert bytes and bits per second.
    def convert_bytes(self, num): # Static converter for alerts and graphing.
        if self.units == 'Bps':
            return('%.2f' % (num))

        if self.units == 'bps':
            return('%.2f' % (num * 8))

        multiple_unit = self.units[0]
        data_unit = self.units[1:]

        if data_unit == 'bps':
            num *= 8

        for single_unit in ['k', 'M', 'G', 'T']:
            num = num / 1000
            if single_unit == multiple_unit:
                return('%.2f' % (num))
        raise Exception('Cannot parse {}'.format(self.units))


    # Dynamic bytes converter for check text output.
    def dynamic_bytes_formatter(self, num):
        for unit in ['Bps','kBps','MBps','GBps','TBps','PBps','EBps','ZBps']:
            if abs(num) < 1024.0:
                return('%3.1f%s' % (num, unit))
            num /= 1024.0
        return('%.1f%s' % (num, 'YBps'))


    # Create new reference file.
    def create_new_reference_file(self):
        try:
            if os.path.exists(self.reference_stats_file):
                os.remove(self.reference_stats_file)
                shutil.copyfile(self.current_stats_file, self.reference_stats_file)
            else:
                shutil.copyfile(self.current_stats_file, self.reference_stats_file) # Technically addressed by First Run handler.

        # Handle reference file exceptions.
        except Exception as e:
            print('ERROR - Creating reference stats file - {}'.format(e))
            sys.exit(1)


    # Main Bandwidth check function.
    def bandwidth_check(self):
        try:
            # Handle first run.
            if not os.path.exists(self.reference_stats_file):
                shutil.copyfile(self.current_stats_file, self.reference_stats_file)
                print('UNKNOWN - First Run. Generating reference statistics.')
                sys.exit(3)

            else: # Collect tranmission meteric samples.
                # First Sample.
                first_sample = self.parse_stats(self.reference_stats_file)
                # Determine file format to parse.
                if 'rx_bytes' in first_sample:
                    receive_bytes = 'rx_bytes'
                    transmission_bytes = 'tx_bytes'
                elif 'rx_Receive' in first_sample:
                    receive_bytes = 'rx_Receive'
                    transmission_bytes = 'tx_Transmit'
                else:
                    print('ERROR - Problem parsing {} file.'.format(self.reference_stats_file))
                    sys.exit(1)

                # Assign first_sample stats to variables.
                first_sample_received = first_sample[receive_bytes]
                first_sample_transmitted = first_sample[transmission_bytes]
                first_sample_total = int(first_sample_received) + int(first_sample_transmitted)

                # Second Sample.
                second_sample = self.parse_stats(self.current_stats_file)
                # Determine file format to parse.
                if 'rx_bytes' in second_sample:
                    receive_bytes = 'rx_bytes'
                    transmission_bytes = 'tx_bytes'
                elif 'rx_Receive' in second_sample:
                    receive_bytes = 'rx_Receive'
                    transmission_bytes = 'tx_Transmit'
                else:
                    print('ERROR - Problem parsing {} file.'.format(self.current_stats_file))
                    sys.exit(1)

                # Assign second_sample stats to variables.
                second_sample_received = second_sample[receive_bytes]
                second_sample_transmitted = second_sample[transmission_bytes]
                second_sample_total = int(second_sample_received) + int(second_sample_transmitted)

                # Calcuate transmission speed from samples.
                totals_subtracted =  int(second_sample_total) - int(first_sample_total)
                received_subtracted = int(second_sample_received) - int(first_sample_received)
                transmitted_subtracted = int(second_sample_transmitted) - int(first_sample_transmitted)

                # Get reference_stat_file modification time, and use in our bandwidth speed calculation.
                file_epoch_mtime = int((os.path.getmtime(self.reference_stats_file)))
                current_epoch_time = int(time())
                time_diff = current_epoch_time - file_epoch_mtime # In seconds. Used to calcuate bandwidth.

                # Calculate bandwidth speed. # This will pass results to the dynamic size formatter function.
                total_speed = totals_subtracted / time_diff
                receive_speed = received_subtracted / time_diff
                transmit_speed = transmitted_subtracted / time_diff

                # Handle check results.
                if float(self.convert_bytes(receive_speed)) >= float(self.critical_threshold) or float(self.convert_bytes(transmit_speed)) >= float(self.critical_threshold):
                    print('CRITICAL - Bandwidth Threshold: {}{} - rx: {}, tx: {} - Total: {} | in-{}={}{};;;; out-{}={}{};;;;'.format(self.critical_threshold, self.units, self.dynamic_bytes_formatter(receive_speed), self.dynamic_bytes_formatter(transmit_speed),
                                                                                                                              self.dynamic_bytes_formatter(total_speed), self.wanted_interface_stats, self.convert_bytes(receive_speed), self.units,
                                                                                                                              self.wanted_interface_stats, self.convert_bytes(transmit_speed), self.units))
                    self.create_new_reference_file()
                    sys.exit(2)
                elif float(self.convert_bytes(receive_speed)) >= float(self.warning_threshold) or float(self.convert_bytes(transmit_speed)) >= float(self.warning_threshold):
                    print('WARNING - Bandwidth Threshold: {}{} - rx: {}, tx: {} - Total: {} | in-{}={}{};;;; out-{}={}{};;;;'.format(self.critical_threshold, self.units, self.dynamic_bytes_formatter(receive_speed), self.dynamic_bytes_formatter(transmit_speed),
                                                                                                                             self.dynamic_bytes_formatter(total_speed), self.wanted_interface_stats, self.convert_bytes(receive_speed), self.units,
                                                                                                                             self.wanted_interface_stats, self.convert_bytes(transmit_speed), self.units))
                    self.create_new_reference_file()
                    sys.exit(1)
                else:
                    print('OK - Bandwidth - rx: {}, tx: {} - Total: {} | in-{}={}{};;;; out-{}={}{};;;;'.format(self.dynamic_bytes_formatter(receive_speed), self.dynamic_bytes_formatter(transmit_speed), self.dynamic_bytes_formatter(total_speed),
                                                                                                                self.wanted_interface_stats, self.convert_bytes(receive_speed), self.units, self.wanted_interface_stats, self.convert_bytes(transmit_speed), self.units))
                    self.create_new_reference_file()
                    sys.exit(0)


        # Handle check results failure.
        except Exception as e:
            print('ERROR - Check failure - {}'.format(e))
            sys.exit(1)



def readme():
    print('''
Check measures bandwidth. Outputs metrics using dynamic units (i.e. byte rate achieved). However, alert threshold and graphing units are statically configured. Works in conjunction with NRPE.

    Usage:
        -i    Interface to Monitor.
        -u    Units for Alert threhold and Graphing. Available Units: Bps, kBps, MBps, GBps, TBps, bps, kbps, Mbps, Gbps, Tbps
        -l    Maximum bandwidth limit threshold. Warning & Critical are calculated as percentages of this value.
        -w    Warning percent threshold for bandwidth. (default : 85)
        -c    Critical percent threshold for bandwidth. (default : 95)

    Command Example:
    python3 check_bandwidth.py -i eth0 -u kBps -l 2000 -w 85 -c 95 # This will monitor eth0. Outputting graphs in kilobytes. Setting a limit of 2000 kilobytes per second (or 2 Megabytes per second). Warning upon 85% and Critical upon 95% of 2 Megabytes.
    ''')
    sys.exit(1)


if __name__ == '__main__':
    ## Arguments
    units = ['Bps', 'kBps', 'MBps', 'GBps', 'TBps', 'bps', 'kbps', 'Mbps', 'Gbps', 'Tbps']
    parser = argparse.ArgumentParser()
    parser.add_argument('-readme','--readme', help='Display Readme/Help.', action='store_true')
    parser.add_argument('-i', '--interface', help='Interface to monitor.')
    parser.add_argument('-u', '--units', choices=units, help='Units for Alert threshold and Graphing. (e.g. kBps for kilobytes persecond)')
    parser.add_argument('-l', '--limit', help='Sets Maximum bandwidth limit. Warning and Critical thresholds are calcuated as percentages of this value.')
    parser.add_argument('-w', help='Sets Warning threshold as a percent of maximum bandwidth limit. Default: 85', default=85)
    parser.add_argument('-c', help='Sets Critical threshold as a percentage of maximum bandwidth limit. Default: 95', default=95)
    args = parser.parse_args()

    ## Command line argument handlers
    if args.readme:
        readme()

    elif args.units and args.limit and args.w and args.c is not None:
        BandwidthMonitoring(INTERFACE=args.interface, UNITS=args.units, LIMIT_THRESHOLD=args.limit, WARNING_THRESHOLD=args.w, CRITICAL_THRESHOLD=args.c)
    else:
        print('README: python3 check_bandwidth.py -readme')

