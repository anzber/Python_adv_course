#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import re
import gzip
from collections import namedtuple
import datetime
from string import Template
import time
import logging
import json
from shutil import copyfile
import argparse

# log_format ui_short '$remote_addr $remote_user  $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
#                     '$request_time';


lineformat_named = re.compile(r'''(?P<remote_addr>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) (?P<remote_user>\S+)  (?P<http_x_real_ip>\S+) \[(?P<time_local>.*?)\] "(\bGET |POST \b)?(?P<request>.*?)" (?P<status>\S+) (?P<body_bytes_sent>\S+) "(?P<http_referer>.*?)" "(?P<http_user_agent>.*?)" "(?P<http_x_forwarded_for>.*?)" "(?P<http_X_REQUEST_ID>.*?)" "(?P<http_X_RB_USER>.*?)" (?P<request_time>\d{0,}\.\d{1,}|\d{1,}\.\d{0,}|d{1,})''')

config = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "LOG_DIR": "./log",
    "FORCE": False
}


def median(nums: list):
    l = len(nums)
    if l % 2 == 1:
        return nums[l//2]
    else:
        return sum(nums[l//2-1:l//2+1])/2


def configure_logging(log_file_name):
    logging.basicConfig(filename=log_file_name, format='[%(asctime)s] %(levelname).1s %(message)s', datefmt='%Y.%m.%d %H:%M:%S', level=logging.DEBUG)
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))


def get_latest_log(log_dir):
    regex = re.compile('^nginx-access-ui\.log-(\d{8})(\.gz)?$')
    LogFile = namedtuple('LogFile', 'name date ext')
    maxdate = 0
    max_filename = ''
    max_file_ext = ''
    for f in os.listdir(log_dir):
        res = regex.findall(f)
        if len(res) > 0:
            res = res[0]
            curdate = int(res[0])
            if maxdate < curdate:
                maxdate = curdate
                max_filename = f
                max_file_ext = res[1]
    if maxdate == 0:
        return None
    return LogFile(name=max_filename, date=datetime.datetime.strptime(str(maxdate), '%Y%m%d').date(), ext=max_file_ext)


def make_report(report_name, dict_list):
    f = open('report.html', 'r', encoding='utf-8')
    report_template = Template(f.read())
    f.close()
    report = open(report_name, 'w', encoding='utf-8')
    report.write(report_template.safe_substitute({'table_json': json.dumps(dict_list)}))
    report.close()


def xreadlines(log_path):
    log = gzip.open(log_path, 'rt', encoding="utf-8") if log_path.endswith(".gz") else open(log_path, 'r', encoding="utf-8")
    for line in log:
        yield line
    log.close()


def main(conf):
    configure_logging('log_analyzer.log')
    try:
        start_time = time.time()
        if not os.path.isdir(conf['LOG_DIR']):
            print(f"Log directory doesn't exist {conf['LOG_DIR']}")
            exit(1)
        if not os.path.isdir(conf['REPORT_DIR']):
            print(f"Report directory doesn't exist {conf['REPORT_DIR']}")
            exit(1)
        latest_log = get_latest_log(conf['LOG_DIR'])
        if latest_log is None:
            print(f"Not found any log file in directory {conf['LOG_DIR']}")
            exit(1)
        if not os.path.isfile('jquery.tablesorter.min.js'):
            print('Missing file jquery.tablesorter.min.js in current directory')
            exit(1)
        if not os.path.isfile('report.html'):
            print('Missing file report.html in current directory')
            exit(1)

        log_date = datetime.datetime.strftime(latest_log.date, '%Y.%m.%d')
        report_name = os.path.join(conf['REPORT_DIR'], f'report-{log_date}.html')
        if (not conf['FORCE']) and os.path.isfile(report_name):
            print('Latest log already processed. See report here '+report_name)
            exit(1)
        logging.info(f'Starting log_analyzer with config {str(conf)}')
        logging.info(f'Latest log date is {log_date}')
        log_lines = xreadlines(conf['LOG_DIR']+'/'+latest_log.name)
        dct_stat = {}
        total = processed = total_time = 0
        for line in log_lines:
            data = re.search(lineformat_named, line)
            total += 1
            if data:
                processed += 1
                line_dict = data.groupdict()
                url = line_dict['request']
                if not (url in dct_stat):
                    dct_stat[url] = {'times': []}
                req_time = float(line_dict['request_time'])
                dct_stat[url]['times'].append(req_time)
                total_time += req_time
        logging.info("%s of %s lines processed" % (processed, total))
        if (total != processed):
            logging.warning(f'{total-processed} rows not parsed properly. Perhaps due to the changed log-row format.')
        for url in dct_stat:
            dct_stat[url]['times'].sort()
            dct_stat[url]['count'] = len(dct_stat[url]['times'])
            dct_stat[url]['count_perc'] = round(dct_stat[url]['count']/processed*100, 3)
            dct_stat[url]['time_sum'] = round(sum(dct_stat[url]['times']), 3)
            dct_stat[url]['time_perc'] = round(dct_stat[url]['time_sum']/total_time*100, 3)
            dct_stat[url]['time_avg'] = round(dct_stat[url]['time_sum']/dct_stat[url]['count'], 3)
            dct_stat[url]['time_max'] = dct_stat[url]['times'][-1]
            dct_stat[url]['time_med'] = round(median(dct_stat[url]['times']), 3)
            dct_stat[url]['url'] = url
            del dct_stat[url]['times']
        top_urls = sorted(dct_stat.keys(), key=lambda x: dct_stat[x]['time_sum'], reverse=True)[:int(conf['REPORT_SIZE'])]
        make_report(report_name, [dct_stat[url] for url in top_urls])
        if not os.path.isfile(os.path.join(conf['REPORT_DIR'], 'jquery.tablesorter.min.js')):
            copyfile('jquery.tablesorter.min.js', os.path.join(conf['REPORT_DIR'], 'jquery.tablesorter.min.js'))
        logging.info('Finishing log_analyzer')
        logging.info(f"Total time {time.time()-start_time}")
    except KeyboardInterrupt:
        logging.exception('Keyboard interrupt')
        exit(1)
    except Exception as error:
        logging.exception(error)
        exit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='log_analyzer.py')
    parser.add_argument('-c', '--config', type=str, default='./config', help='Path to config file')
    parser.add_argument('-f', '--force', action='store_true', help='Force overwrite existing report')
    args = parser.parse_args()
    if os.path.isfile(args.config):
        config_file = {k.strip(): v.strip() for k, v in (line.split('=') for line in open(args.config))}
        config.update(config_file)
    config['FORCE'] = args.force
    main(config)
