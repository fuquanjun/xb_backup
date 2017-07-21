# !/usr/bin/env
# coding:utf8
# python version python3.5+

import os
import time
import argparse
import subprocess
import configparser
import smtplib
from collections import OrderedDict
import mysql.connector as mdb
from email.mime.text import MIMEText

def parser_args():
    parser = argparse.ArgumentParser(description='This a backup help document.')
    parser.add_argument('-f', '--xtrabackup_file', type=str, help='xtrabackup read defaults file')
    args = parser.parse_args()

    # 读取配置文件
    config = configparser.ConfigParser(allow_no_value=True)
    config.read(args.xtrabackup_file)

    parser_arguments = {}

    # 获取邮箱配置
    parser_arguments['mail_config'] = dict(config.items('mail'))

    # 此处使用collections.OrderedDict有序字典
    # 组合成xtrabackup命令
    current_time = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())
    xb_config = OrderedDict(config.items('xtrabackup'))
    result = []
    for k,v in xb_config.items():
        if v:
            if 'target-dir' == k:
                v = '/'.join((v, current_time, 'data'))
                if not os.path.exists(v):
                    os.makedirs(v)
            result.append('--' + '='.join((k,v)))
        else:
            result.append('--' + k)
    parser_arguments['xb_cmd'] = ' '.join(result)

    # 获取xtrabackup里面的数据库账号
    parser_arguments['mysql_config'] = {
        'user': xb_config['user'],
        'host': xb_config['host'],
        'password': xb_config['password'],
        'port': xb_config['port'],
        'database': 'percona_schema'
    }

    # 获取并生成xtrabackup的日志文件
    # xb_log_file：记录备份时，xtrabackup输出的信息，失败时，读取并发送此文件内容
    # xb_status_file：自定义生产的状态信息，用于备份成功时，读取并发送此文件内容
    xb_data_dir = '/'.join((xb_config['target-dir'], current_time))
    parser_arguments['xb_log_file'] = '/'.join((xb_data_dir, 'xb_output.log'))
    parser_arguments['xb_status_file'] = '/'.join((xb_data_dir, 'xb_status.log'))
    parser_arguments['xb_data_dir'] = xb_data_dir

    return parser_arguments

# 获取备份写入到percona_schema的信息
def get_xb_result():
    conn = mdb.connect(**parser_arguments['mysql_config'])
    cur = conn.cursor(dictionary=True)
    cur.execute("select * from percona_schema.xtrabackup_history limit 1")
    for key in cur.fetchall():
        result = []
        for i in key.items():
            first = str(i[0])
            second = str(i[1])
            result.append(first + ': ' + second)
        result_write('[xtrabackup history]')
        result_write('\n')
        result_write('\n'.join(result))
    cur.close()
    conn.close()

# 获取目录大小
def get_dir_size(dir):
    size = 0
    for root, dirs, files in os.walk(dir):
        size += sum([os.path.getsize(os.path.join(root, name))
                     for name in files])
    return  ''.join(('xtrabackup size', ':\t', '%.2f MB' % float(size/1024/1024)))

# 获取分区大小
def get_partition_size(partition):
  vfs=os.statvfs(partition)
  free = (vfs.f_bavail * vfs.f_bsize)/(1024*1024*1024)
  total = (vfs.f_blocks * vfs.f_bsize)/(1024*1024*1024)
  free_size = '{0} {1:.2f}GB\n'.format('free size:\t',free)
  total_size = '{0} {1:.2f}GB\n'.format('total size:\t',total)
  return ''.join((free_size, total_size))

# 记录备份日志信息, 留着备份
def result_write(content):
    with open(parser_arguments['xb_status_file'], 'a') as f:
        f.write(content)

# 邮件
def mail_send(file):
    mail_config = parser_arguments['mail_config']
    content = ''.join(open(file).readlines())
    msg = MIMEText(content, _subtype='plain', _charset='gb2312')
    msg['Subject'] = mail_config['title']
    msg['From'] = mail_config['mail_sender']
    msg['To'] = ";".join(list(mail_config['mail_receiver'].split(',')))

    try:
        server = smtplib.SMTP()
        server.connect(mail_config['mail_host'])
        server.ehlo()
        # 开启tls加密支持
        server.starttls()
        server.login(mail_config['mail_user'], mail_config['mail_pass'])
        server.sendmail(mail_config['mail_sender'], mail_config['mail_receiver'], msg.as_string())
        server.close()
    except Exception as err:
        print(err)

# xtrabackup
def xtrabackup_instance():
    xb_log_file = parser_arguments['xb_log_file']

    cmd = (' ').join(('/usr/bin/xtrabackup', parser_arguments['xb_cmd']))
    status, output = subprocess.getstatusoutput(cmd)

    # xtrabackup退出状态为0，表示成功。非零，为失败
    if status == 0:
        # 如果备份成功，就发送xb_status_file日志
        with open(r'{0}'.format(xb_log_file), 'a') as f:
            f.write(output)

        get_xb_result()
        xb_backup_size = get_dir_size(parser_arguments['xb_data_dir'])
        xb_partition_size = get_partition_size(parser_arguments['xb_data_dir'])
        result_write('\n'*2)
        result_write('\n'.join(('[backup space]', xb_partition_size, xb_backup_size)))
        mail_send(parser_arguments['xb_status_file'])
    else:
        # 如果备份失败，就发送xb_log_file日志
        with open(r'{0}'.format(xb_log_file), 'a') as f:
            f.write(output)
        mail_send(xb_log_file)


if __name__ == '__main__':
    parser_arguments = parser_args()
    xtrabackup_instance()
