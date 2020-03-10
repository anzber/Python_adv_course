#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Log Analyzer v.0.1
run:
python log_analyzer.py -c config
"""
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


LINEFORMAT_NAMED = re.compile(r'(?P<remote_addr>\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}) '+
                              r'(?P<remote_user>\S+)'+
                              r'  (?P<http_x_real_ip>\S+) \[(?P<time_local>.*?)\] '+
                              r'"(\bGET |POST \b)?(?P<request>.*?)"'+
                              r' (?P<status>\S+) (?P<body_bytes_sent>\S+) '+
                              r'"(?P<http_referer>.*?)" "(?P<http_user_agent>.*?)'+
                              r'" "(?P<http_x_forwarded_for>.*?)" "'+
                              r'(?P<http_X_REQUEST_ID>.*?)" "(?P<http_X_RB_USER>.*?)"'+
                              r' (?P<request_time>\d{0,}\.\d{1,}|\d{1,}\.\d{0,}|d{1,})')

CONFIG = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR": "./reports",
    "LOG_DIR": "./log",
    "FORCE": False,
    "SELF_LOG_DIR": "./"
}


def median(nums: list):
    """
    Calculate median of numbers in sorted list
    """
    list_length = len(nums)
    if list_length % 2 == 1:
        return nums[list_length//2]
    return sum(nums[list_length//2-1:list_length//2+1])/2

def configure_logging(conf):
    """
    Configure logging using config path.
    """
    if not os.path.isdir(conf['SELF_LOG_DIR']):
        try:
            os.mkdir(conf['SELF_LOG_DIR'])
        except OSError:
            print(f"Can not create directory for script logging {conf['SELF_LOG_DIR']}")
            return None
    log_file_name = os.path.join(conf['SELF_LOG_DIR'], 'log_analyzer.log')

    logging.basicConfig(filename=log_file_name,
                        format='[%(asctime)s] %(levelname).1s %(message)s',
                        datefmt='%Y.%m.%d %H:%M:%S', level=logging.DEBUG)
    logging.getLogger().addHandler(logging.StreamHandler(sys.stdout))
    return 1

def get_latest_log(log_dir):
    """
    Search for latest log file and return named tuple with name, date, ext
    """
    regex = re.compile(r'^nginx-access-ui\.log-(\d{8})(\.gz)?$')
    LogFile = namedtuple('LogFile', 'name date ext')
    maxdate = 0
    max_filename = ''
    max_file_ext = ''
    for filename in os.listdir(log_dir):
        res = regex.findall(filename)
        if res:
            res = res[0]
            curdate = int(res[0])
            if maxdate < curdate:
                maxdate = curdate
                max_filename = filename
                max_file_ext = res[1]
    if maxdate == 0:
        return None
    date = datetime.datetime.strptime(str(maxdate), '%Y%m%d').date()
    return LogFile(name=max_filename,
                   date=datetime.datetime.strftime(date, '%Y.%m.%d'),
                   ext=max_file_ext)

def make_report(report_name, dict_list):
    """
    Create report from template and given data.
    """
    with open('report.html', 'r', encoding='utf-8') as frep_tmpl:
        report_template = Template(frep_tmpl.read())
    with open(report_name, 'w', encoding='utf-8') as freport:
        freport.write(report_template.safe_substitute({'table_json': json.dumps(dict_list)}))

def xreadlines(log_path):
    """
    Generator for reading file line by line
    """
    if log_path.endswith(".gz"):
        log = gzip.open(log_path, 'rt', encoding="utf-8")
    else:
        log = open(log_path, 'r', encoding="utf-8")
    for line in log:
        yield line
    log.close()

def process_logfile(conf, latest_log):
    """
    Read log file and parse line by line.
    Return dictionary with each row, number of processed rows, and total_time taken by requests
    """
    logging.info(msg=f'Starting log_analyzer with config {str(conf)}')
    logging.info(msg=f'Latest log date is {latest_log.date}')
    log_lines = xreadlines(conf['LOG_DIR']+'/'+latest_log.name)
    dct_stat = {}
    total = processed = total_time = 0
    for line in log_lines:
        data = re.search(LINEFORMAT_NAMED, line)
        total += 1
        if data:
            processed += 1
            line_dict = data.groupdict()
            url = line_dict['request']
            if url not in dct_stat:
                dct_stat[url] = {'times': []}
            req_time = float(line_dict['request_time'])
            dct_stat[url]['times'].append(req_time)
            total_time += req_time
    logging.info(msg=f"{processed} of {total} lines processed")
    if total != processed:
        logging.warning(msg=f'''{total-processed} rows not parsed properly.
    Perhaps due to the changed log-row format.''')
    return dct_stat, processed, total_time

def calc_stat_top_urls(conf, dct_stat, processed, total_time):
    """
    Calculate statistic data and get top urls
    """
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
    return sorted(dct_stat.keys(),
                  key=lambda x: dct_stat[x]['time_sum'],
                  reverse=True)[:int(conf['REPORT_SIZE'])]


def main(conf):
    """
    Main function
    """
    if not configure_logging(conf):
        exit(1)
    try:
        start_time = time.time()
        if not os.path.isdir(conf['LOG_DIR']):
            logging.info(msg=f"Log directory doesn't exist {conf['LOG_DIR']}")
            exit(1)
        if not os.path.isdir(conf['REPORT_DIR']):
            try:
                os.mkdir(conf['REPORT_DIR'])
            except OSError:
                logging.info(msg=f"Can not create directory {conf['REPORT_DIR']}")
                exit(1)
        latest_log = get_latest_log(conf['LOG_DIR'])
        if latest_log is None:
            logging.info(msg=f"Not found any log file in directory {conf['LOG_DIR']}")
            exit(1)

        report_name = os.path.join(conf['REPORT_DIR'], f'report-{latest_log.date}.html')
        if (not conf['FORCE']) and os.path.isfile(report_name):
            logging.info(msg=f'Latest log already processed. See report here {report_name}')
            exit(1)

        dct_stat, processed, total_time = process_logfile(conf, latest_log)
        top_urls = calc_stat_top_urls(conf, dct_stat, processed, total_time)
        make_report(report_name, [dct_stat[url] for url in top_urls])
        if not os.path.isfile(os.path.join(conf['REPORT_DIR'], 'jquery.tablesorter.min.js')):
            copyfile('jquery.tablesorter.min.js',
                     os.path.join(conf['REPORT_DIR'], 'jquery.tablesorter.min.js'))
        logging.info(msg='Finishing log_analyzer')
        logging.info(msg=f"Total time {time.time()-start_time}")
    except KeyboardInterrupt:
        logging.exception('Keyboard interrupt')
        exit(1)
    except Exception as error:
        logging.exception(error)
        exit(1)

def get_config(cmd_line_args):
    """
    Create config dictionary from default and external data given by command line arguments.
    """
    config = CONFIG.copy()
    if os.path.isfile(cmd_line_args.config):
        config_file = {k.strip(): v.strip() for k, v in \
                       (line.split('=') for line in open(cmd_line_args.config))}
        config.update(config_file)
    config['FORCE'] = cmd_line_args.force
    return config


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='log_analyzer.py')
    parser.add_argument('-c', '--config',
                        type=str,
                        default='./config',
                        help='Path to config file')
    parser.add_argument('-f', '--force',
                        action='store_true',
                        help='Force overwrite existing report')
    main(get_config(parser.parse_args()))
