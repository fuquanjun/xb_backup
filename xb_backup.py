# -*- coding:utf-8 -*-
# edit by fuzongfei

import os
import time
import argparse
import subprocess
import configparser
import smtplib
import socket
from collections import OrderedDict
import mysql.connector as mdb
from email.mime.text import MIMEText

hostname = socket.gethostname()
current_time = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())


def get_args():
    parser = argparse.ArgumentParser(description='This a backup help document.')
    parser.add_argument('-f', '--file', type=str, help='xtrabackup read config file')
    args = parser.parse_args()

    config = configparser.ConfigParser(allow_no_value=True)
    config.read(args.file)

    # 读取邮箱配置
    args = {'mail': dict(config.items('mail'))}

    # 此处使用collections.OrderedDict有序字典
    # 组合成xtrabackup命令
    xb_config = OrderedDict(config.items('xtrabackup'))
    result = []
    for k, v in xb_config.items():
        if v:
            if 'target-dir' == k:
                v = '/'.join((v, current_time, 'data'))
                if not os.path.exists(v):
                    os.makedirs(v)
            if 'xtrabackup' == k:
                result.append(v)
            else:
                result.append('--' + '='.join((k, v)))
        else:
            result.append('--' + k)
    args['xb_cmd'] = ' '.join(result)

    # 读取数据库账号配置
    args['mysql'] = {
        'user': xb_config['user'],
        'host': xb_config['host'],
        'password': xb_config['password'],
        'port': xb_config['port'],
        'database': 'percona_schema'
    }

    # 获取并生成xtrabackup的日志文件
    # xb_log：记录备份时，xtrabackup输出的信息，失败时，读取并发送此文件内容
    # xb_status_log：自定义生产的状态信息，用于备份成功时，读取并发送此文件内容
    xb_datadir = '/'.join((xb_config['target-dir'], current_time))
    args['xb_log'] = '/'.join((xb_datadir, 'xb_output.log'))
    args['xb_status_log'] = '/'.join((xb_datadir, 'xb_status.log'))
    args['xb_datadir'] = xb_datadir

    return args


def writelog(file, content):
    with open(file, 'a') as f:
        f.write(content)
        f.write('\n')


# 邮件
def mail_send(parameter, file):
    mail_config = parameter['mail']
    content = ''.join(open(file).readlines())
    msg = MIMEText(content, _subtype='plain', _charset='gb2312')
    msg['Subject'] = '{} from {}'.format(mail_config['title'], hostname)
    msg['From'] = mail_config['mail_sender']
    msg['To'] = ";".join(list(mail_config['mail_receiver'].split(',')))
    mail_receiver = list(mail_config['mail_receiver'].split(','))

    try:
        server = smtplib.SMTP()
        server.connect(mail_config['mail_host'])
        server.ehlo()
        # 开启tls加密支持
        server.starttls()
        server.login(mail_config['mail_user'], mail_config['mail_pass'])
        server.sendmail(mail_config['mail_sender'], mail_receiver, msg.as_string())
        server.close()
    except Exception as err:
        print(err)


class GetMySQLInfo(object):
    def __init__(self, parameter, query):
        self.parameter = parameter
        self.query = query

    @property
    def runner(self):
        try:
            conn = mdb.connect(**self.parameter['mysql'])
        except conn.ProgrammingError as err:
            writelog(self.parameter['xb_status_log'], err)
        else:
            cur = conn.cursor(dictionary=True)
            cur.execute(self.query)
            return cur.fetchall()
            cur.close()
            conn.close()


class GetDiskUsageInfo(object):
    """
    获取备份文件大小、获取分区已使用空间、总空间
    return：list
    """

    def __init__(self, path):
        self.path = path

    FMT_INFO = '{:} --> {:.2f}GB'

    @property
    def bk_size(self):
        size = 0
        for root, dirs, files in os.walk(self.path):
            size += sum([os.path.getsize(os.path.join(root, name))
                         for name in files])
        return [''.join(self.FMT_INFO.format('backup_file_size', float(size / 1024 / 1024 / 1024)))]

    @property
    def partition_size(self):
        vfs = os.statvfs(self.path)
        free = (vfs.f_bavail * vfs.f_bsize) / (1024 * 1024 * 1024)
        total = (vfs.f_blocks * vfs.f_bsize) / (1024 * 1024 * 1024)
        partition_free_size = self.FMT_INFO.format('partition_free_size', free)
        partition_total_size = self.FMT_INFO.format('partition_total_size', total)
        return [partition_free_size, partition_total_size]

    @property
    def runner(self):
        return self.bk_size + self.partition_size


# xtrabackup
def xtrabackup(parameter):
    status, output = subprocess.getstatusoutput(parameter['xb_cmd'])
    writelog(parameter['xb_log'], output)

    # xtrabackup退出状态为0，表示成功。非零，为失败
    result = []
    if status == 0:
        query = "select * from xtrabackup_history order by start_time desc limit 1"
        FMT_RESULT = '{} --> {}'

        for key in GetMySQLInfo(parameter, query).runner:
            for k, v in key.items():
                result.append(FMT_RESULT.format(k, v))
        get_disk_usage_info = GetDiskUsageInfo(parameter['xb_datadir']).runner
        writelog(parameter['xb_status_log'], '[xtrabackup info]')
        writelog(parameter['xb_status_log'], '\n'.join((result + get_disk_usage_info)))
    return status


def xb_run():
    argument = get_args()
    xb_status = xtrabackup(argument)
    if xb_status == 0:
        mail_send(argument, argument['xb_status_log'])
    else:
        mail_send(argument, argument['xb_log'])


if __name__ == '__main__':
    xb_run()
