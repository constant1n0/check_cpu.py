#!/usr/bin/python3
############################################################################
# Original Copyright 2013 George Hansper
# Adapted in 2024 by Dâmaso Constantino [https://github.com/constant1n0]>
# This version has been adapted for Python 3 compatibility.
# 
# This program is released under the GNU General Public License v2,
# which you can find at: http://www.gnu.org/licenses/gpl-2.0.html
#
# The original work was based on check_cpu.py by Kirk Hammond.
# Adaptations include updates for Python 3 syntax, improved file handling,
# and error management.
#
# DISCLAIMER:
# This program is supplied 'as-is', without warranties or guarantees of any kind.
# As this is a script for monitoring and potentially altering system performance,
# you are advised to test thoroughly in your own environment.
############################################################################

Version = "1.7 $Id: 34e1f936687630763264047f56c1bfc9ea9c1dd3 $"

import sys
import getopt
import time

# Nagios return codes
UNKNOWN = 3
OK = 0
WARNING = 1
CRITICAL = 2

usage = """usage: ./check_cpu.py [-w num|--warn=num] [-c|--crit=num] [-W num |--io-warn=num] [-C num|--io-crit=num] [-p num|--period=num]
    -w, --warn     ... generate warning  if total cpu exceeds num (default: 95)
    -c, --crit     ... generate critical if total cpu exceeds num (default: 98)
    -W, --warn-any ... generate warning  if any single cpu exceeds num (default: 98)
    -C, --crit-any ... generate critical if any single cpu exceeds num (default: 100 (off))
    -i, --io-warn  ... generate warning  if any single cpu exceeds num in io_wait (default: 90)
    -I, --io-crit  ... generate critical if any single cpu exceeds num in io_wait (default: 98)
        --io-warn-overall ... generate warning  if overall cpu exceeds num in io_wait (default: 100 (off))
        --io-crit-overall ... generate critical if overall cpu exceeds num in io_wait (default: 100 (off))
    -s, --steal-warn  ... generate warning  if any single cpu exceeds num in steal (default: 30)
    -S, --steal-crit  ... generate critical if any single cpu exceeds num in steal (default: 80)
    -p, --period   ... sample cpu usage over num seconds
    -a, --abs      ... generate performance stats in cpu-ticks (jiffies), as well as percent
    -A, --abs-only ... generate performance stats in cpu-ticks (jiffies), instead of percent
    -V, --version  ... print version

Notes:
    Warning/critical alerts are generated when the threshold is exceeded
    eg -w 95 means alert on 96% and above
    All values are in percent, but no % symbol is required
    A warning/critical will also be generated if any single cpu exceeds a threshold. Specify 100 to disable. eg.
         check_cpu.py -W 100 -C 100 
    'total' includes io_wait and steal (ie. everything except idle)
"""

# Global variables for CPU statistics
cpu_percent = dict()
io_wait_percent = dict()
steal_percent = dict()
cpu_id_list = []
ctxt_per_second = 0
processes_per_second = 0
cpu_stats_t1 = dict()
warn = 95
crit = 98
per_cpu_warn = 98
per_cpu_crit = 100
io_warn = 90
io_crit = 98
io_warn_overall = 100
io_crit_overall = 100
steal_warn = 30
steal_crit = 80
proc_stat_file = '/proc/stat'
sample_period = 1
perfdata_abs = 1

def get_procstat_now():
    global cpu_id_list, proc_stat_file
    cpu_id_list = []
    cpu_stats = dict()
    with open(proc_stat_file, 'r') as procstat:
        procstat_text = procstat.read()
    for line in procstat_text.split("\n"):
        if line.startswith('cpu '):
            parts = line.split()
            cpu_id = parts[0]
            cpu_ticks = parts[1:]
        elif line.startswith('cpu'):
            parts = line.split()
            cpu_id = parts[0]
            cpu_ticks = parts[1:]
        elif line.startswith('ctxt'):
            cpu_stats['ctxt'] = parts[1]
            continue
        elif line.startswith('processes'):
            cpu_stats['processes'] = parts[1]
            continue
        else:
            continue
        cpu_ticks_array = [int(tick) for tick in cpu_ticks]
        while len(cpu_ticks_array) < 10:
            cpu_ticks_array.append(0)
        user, nice, system, idle, io_wait, hw_intr, sw_intr, steal, guest, guest_nice = cpu_ticks_array
        cpu_usage = sum(cpu_ticks_array) - idle
        cpu_total_ticks = sum(cpu_ticks_array)
        cpu_stats[cpu_id] = cpu_usage
        cpu_stats[cpu_id + 'all'] = cpu_total_ticks
        cpu_stats[cpu_id + 'io_wait'] = io_wait
        cpu_stats[cpu_id + 'steal'] = steal
        cpu_id_list.append(cpu_id)
    return cpu_stats

def get_cpu_stats():
    global cpu_id_list, cpu_percent, io_wait_percent, steal_percent, cpu_stats_t1, ctxt_per_second, processes_per_second
    cpu_stats_t0 = get_procstat_now()
    time.sleep(sample_period)
    cpu_stats_t1 = get_procstat_now()
    for cpu_id in cpu_id_list:
        total_t1 = cpu_stats_t1[cpu_id + 'all']
        total_t0 = cpu_stats_t0[cpu_id + 'all']
        delta_total = total_t1 - total_t0
        if delta_total > 0:
            cpu_percent[cpu_id] = (cpu_stats_t1[cpu_id] - cpu_stats_t0[cpu_id]) * 100 / delta_total
            io_wait_percent[cpu_id] = (cpu_stats_t1[cpu_id + 'io_wait'] - cpu_stats_t0[cpu_id + 'io_wait']) * 100 / delta_total
            steal_percent[cpu_id] = (cpu_stats_t1[cpu_id + 'steal'] - cpu_stats_t0[cpu_id + 'steal']) * 100 / delta_total
        else:
            cpu_percent[cpu_id] = 0
            io_wait_percent[cpu_id] = 0
            steal_percent[cpu_id] = 0
    ctxt_per_second = (float(cpu_stats_t1['ctxt']) - float(cpu_stats_t0['ctxt'])) / sample_period
    processes_per_second = (float(cpu_stats_t1['processes']) - float(cpu_stats_t0['processes'])) / sample_period

def performance_data():
    global warn, crit, io_warn, io_crit, cpu_id_list, cpu_percent, io_wait_percent, steal_percent, ctxt_per_second, processes_per_second
    perf_message_array = []
    for cpu_id in cpu_id_list:
        perf_message_array.append(f'{cpu_id}={cpu_percent[cpu_id]}%;{warn};{crit};0;100')
        perf_message_array.append(f'{cpu_id}_iowait={io_wait_percent[cpu_id]}%;{io_warn};{io_crit};0;100')
        perf_message_array.append(f'{cpu_id}_steal={steal_percent[cpu_id]}%;{steal_warn};{steal_crit};0;100')
    return " ".join(perf_message_array)

def check_status():
    global warn, crit, io_warn, io_crit, per_cpu_warn, per_cpu_crit, cpu_id_list, cpu_percent, io_wait_percent, steal_percent
    result = OK
    messages = []
    for cpu_id in cpu_id_list:
        if cpu_percent[cpu_id] >= crit:
            result = CRITICAL
            messages.append(f'CRITICAL: {cpu_id} CPU usage at {cpu_percent[cpu_id]}% exceeds critical threshold of {crit}%')
        elif cpu_percent[cpu_id] >= warn:
            result = WARNING
            messages.append(f'WARNING: {cpu_id} CPU usage at {cpu_percent[cpu_id]}% exceeds warning threshold of {warn}%')
    if not messages:
        messages.append('OK: CPU usage is within normal parameters')
    return result, ' '.join(messages)

def command_line_validate(argv):
    global warn, crit, io_warn, io_crit, sample_period, io_warn_overall, io_crit_overall, per_cpu_warn, per_cpu_crit, steal_warn, steal_crit, perfdata_abs
    try:
        opts, args = getopt.getopt(argv, 'w:c:W:C:i:I:s:S:p:VaA', ['warn=', 'crit=', 'warn-any=', 'crit-any=', 'io-warn=', 'io-crit=', 'io-warn-overall=', 'io-crit-overall=', 'steal-warn=', 'steal-crit=', 'period=', 'version', 'abs', 'abs-only'])
    except getopt.GetoptError:
        print(usage)
        sys.exit(CRITICAL)
    for opt, arg in opts:
        if opt in ('-w', '--warn'):
            warn = int(arg)
        elif opt in ('-c', '--crit'):
            crit = int(arg)
        elif opt in ('-W', '--warn-any'):
            per_cpu_warn = int(arg)
        elif opt in ('-C', '--crit-any'):
            per_cpu_crit = int(arg)
        elif opt in ('-i', '--io-warn'):
            io_warn = int(arg)
        elif opt in ('-I', '--io-crit'):
            io_crit = int(arg)
        elif opt in ('--io-warn-overall'):
            io_warn_overall = int(arg)
        elif opt in ('--io-crit-overall'):
            io_crit_overall = int(arg)
        elif opt in ('-s', '--steal-warn'):
            steal_warn = int(arg)
        elif opt in ('-S', '--steal-crit'):
            steal_crit = int(arg)
        elif opt in ('-p', '--period'):
            sample_period = int(arg)
        elif opt in ('-a', '--abs'):
            perfdata_abs = 3
        elif opt in ('-A', '--abs-only'):
            perfdata_abs = 2
        elif opt in ('-V', '--version'):
            print(Version)
            sys.exit(OK)

def main():
    argv = sys.argv[1:]
    command_line_validate(argv)
    get_cpu_stats()
    perf_message = performance_data()
    exit_code, result_message = check_status()
    print(result_message, '|', perf_message)
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
