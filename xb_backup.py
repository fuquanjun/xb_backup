# -*- coding:utf-8 -*-
# edit by fuzongfei

import argparse
import configparser
import logging
import shutil
import smtplib
import socket
import subprocess
import sys
import os
import jinja2
import time
from email.mime.text import MIMEText
from os.path import isfile
from tempfile import TemporaryFile

# Set logger
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT, datefmt=DATE_FORMAT)
logger = logging.getLogger(__name__)

# Get HOSTNAME
HOSTNAME = socket.gethostname()

# Get os time
CURRENT_TIME = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())

# Set statistics info
STATISTICS_INFO = {'备份主机': HOSTNAME}

# Set render html template
module_path = os.path.dirname(__file__)
html_template = os.path.join(module_path + '/table_template.html')


def render_to_template(html_path, html_context):
    path, filename = os.path.split(html_path)
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(path)
    )
    if isinstance(html_context, dict):
        return env.get_template(filename).render({'data': html_context})
    else:
        return env.get_template(filename).render({'err_msg': html_context})


def get_arguments():
    """
    Get user input 
    """
    parser = argparse.ArgumentParser(description='This a backup help document.')
    parser.add_argument('-f', '--file', type=str, help='xtrabackup read config file')
    args = parser.parse_args()
    return args.file


def check_config_valid(file):
    """
    Check config file content valid
    """
    config = configparser.ConfigParser()
    try:
        config.read(file)
    except configparser.MissingSectionHeaderError:
        logger.warning('WARN: this first line must contains section headers')

    config_items = [x for x in config.keys()]

    config_keys = []
    for i in [config.items(x) for x in config.keys()]:
        for j in i:
            config_keys.append(j[0])

    keep_items = ['mysql', 'xtrabackup', 'compress', 'encrypt', 'mail']
    keep_keys = [
        'user',
        'host',
        'password',
        'port',
        'backup_tool',
        'defaults-file',
        'backupdir',
        'title',
        'mail_sender',
        'mail_receiver',
        'mail_host',
        'mail_user',
        'mail_pass'
    ]

    for header in keep_items:
        if header not in config_items:
            logger.error(f'FAILED: this section header [{header}] not found.')
            sys.exit(1)

    for key in keep_keys:
        if key not in config_keys:
            logger.error(f'FAILED: this argument [{key}] not found.')
            sys.exit(1)

    return True


class General(object):
    """
    Process the config file and Generate variables
    """

    def __init__(self, file):
        if isfile(file):
            config = configparser.ConfigParser(allow_no_value=True)
            config.read(file)

            Mysql = config['mysql']
            self.user = Mysql['user']
            self.host = Mysql['host']
            self.password = Mysql['password']
            self.port = Mysql['port']

            Xtrabackup = config['xtrabackup']
            self.backup_tool = Xtrabackup['backup_tool']
            self.defaults_file = Xtrabackup['defaults-file']
            self.backupdir = Xtrabackup['backupdir']
            self.fmt_backupdir = '/'.join((Xtrabackup['backupdir'], CURRENT_TIME))
            if 'xtra_options' in Xtrabackup:
                self.xtra_options = Xtrabackup['xtra_options']

            Compress = config['compress']
            if 'compress' in Compress:
                self.compress = Compress['compress']
            if 'compress_chunk_size' in Compress:
                self.compress_chunk_size = Compress['compress_chunk_size']
            if 'compress_threads' in Compress:
                self.compress_threads = Compress['compress_threads']

            Encrypt = config['encrypt']
            if 'encrypt' in Encrypt:
                self.encrypt = Encrypt['encrypt']
            if 'encrypt_key' in Encrypt:
                self.encrypt_key = Encrypt['encrypt_key']
            if 'encrypt_threads' in Encrypt:
                self.encrypt_threads = Encrypt['encrypt_threads']
            if 'encrypt_chunk_size' in Encrypt:
                self.encrypt_chunk_size = Encrypt['encrypt_chunk_size']

            Remote = config['remote']
            if 'remote_host' in Remote:
                self.remote_host = Remote['remote_host']
            if 'remote_ssh_user' in Remote:
                self.remote_ssh_user = Remote['remote_ssh_user']
            if 'remote_ssh_pass' in Remote:
                self.remote_ssh_pass = Remote['remote_ssh_pass']
            if 'remote_dir' in Remote:
                self.remote_dir = Remote['remote_dir']
            if 'remove_local_backup' in Remote:
                self.remove_local_backup = Remote['remove_local_backup']

            Mail = config['mail']
            self.title = Mail['title']
            self.mail_sender = Mail['mail_sender']
            self.mail_receiver = Mail['mail_receiver']
            self.mail_host = Mail['mail_host']
            self.mail_user = Mail['mail_user']
            self.mail_pass = Mail['mail_pass']


class CheckEnvironment(General):
    """
    Check if the file and command exists
    """

    def __init__(self, file):
        self.file = file
        General.__init__(self, self.file)
        self.FILE_LIST = [self.backup_tool, self.defaults_file, '/usr/bin/sshpass', self.backupdir]

    def check_file_exist(self):
        for file in self.FILE_LIST:
            if not os.path.exists(file):
                logger.error(f'FAILED: {file} not found.')
                logger.error('FAILED: 程序退出.')
                sys.exit(1)
            else:
                logger.info(f'OK: the file {file} exist.')
        return True


class ToolsUtils(General):
    """
    Define some tools
    """

    def __init__(self, file):
        self.file = file
        General.__init__(self, self.file)

        self.xb_output_log = '/'.join((self.fmt_backupdir, 'xb_output.log'))

        STATISTICS_INFO['备份目录'] = self.fmt_backupdir
        STATISTICS_INFO['备份工具'] = self.backup_tool

    def create_backup_dir(self):
        """ create backup directory """
        if not os.path.exists(self.fmt_backupdir):
            os.makedirs(self.fmt_backupdir)
            logger.info(f'OK: the backup dir not exisit, create {self.fmt_backupdir}')

    FMT_INFO = '{:.2f}GB'

    def get_backup_file_size(self):
        size = 0
        for root, dirs, files in os.walk(self.fmt_backupdir):
            size += sum([os.path.getsize(os.path.join(root, name))
                         for name in files])
        logger.info(f'OK: get backup file size')
        STATISTICS_INFO['备份大小'] = self.FMT_INFO.format(float(size / 1024 / 1024 / 1024))
        return True

    def get_partition_size(self):
        vfs = os.statvfs(self.fmt_backupdir)
        free = (vfs.f_bavail * vfs.f_bsize) / (1024 * 1024 * 1024)
        total = (vfs.f_blocks * vfs.f_bsize) / (1024 * 1024 * 1024)
        partition_free_size = self.FMT_INFO.format(free)
        partition_total_size = self.FMT_INFO.format(total)
        logger.info(f'OK: get disk partition usage')
        STATISTICS_INFO['可用空间'] = partition_free_size
        STATISTICS_INFO['总空间'] = partition_total_size
        return True

    def remove_backup_file(self):
        """ if remove_local_backup = Yes, delete local backup files """
        if hasattr(self, 'remote_host') and hasattr(self, 'remote_ssh_user') \
                and hasattr(self, 'remote_ssh_pass') and hasattr(self, 'remote_dir') \
                and hasattr(self, 'remove_local_backup'):
            if self.remove_local_backup == 'Yes':
                shutil.rmtree(self.fmt_backupdir)
                STATISTICS_INFO['本地留存'] = 'No'
                logger.info(f"OK: the directory {self.fmt_backupdir} remove success")
        else:
            STATISTICS_INFO['本地留存'] = 'Yes'
            return False

    def send_mail(self, data):
        """ 
        Send mail notice 
        Read TemporaryFile content
        """
        msg = MIMEText(data, _subtype='html', _charset='gbk')
        msg['Subject'] = '{} from {}'.format(self.title, HOSTNAME)
        msg['From'] = self.mail_sender
        msg['To'] = ";".join(list(self.mail_receiver.split(',')))
        mail_receiver = list(self.mail_receiver.split(','))

        try:
            server = smtplib.SMTP()
            server.connect(self.mail_host)
            server.ehlo()
            # enable tls encrypt
            server.starttls()
            server.login(self.mail_user, self.mail_pass)
            server.sendmail(self.mail_sender, mail_receiver, msg.as_string())
            server.close()
            logger.info(f'OK: send mail success')
        except Exception as err:
            logger.error(f'FAILED: send mail fail')
            logger.error(err)


class Prepare(General):
    """
    Generate command
    """

    def __init__(self, file):
        self.file = file
        General.__init__(self, self.file)

    @property
    def generate_xb_cmd(self):
        mysql_cmd = f"--user={self.user} --password={self.password} --host={self.host} --port={self.port}"

        cmd_list = []
        if hasattr(self, 'compress') and hasattr(self, 'compress_chunk_size') and hasattr(self, 'compress_threads'):
            compress_cmd = f"--compress={self.compress} --compress-chunk-size={self.compress_chunk_size} --compress-threads={self.compress_threads}"
            cmd_list.append(compress_cmd)
            STATISTICS_INFO['是否压缩'] = 'Yes'
        else:
            STATISTICS_INFO['是否压缩'] = 'No'

        if hasattr(self, 'encrypt') and hasattr(self, 'encrypt_key') and hasattr(self, 'encrypt_threads') and hasattr(
                self, 'encrypt_chunk_size'):
            encrypt_cmd = f"--encrypt={self.encrypt} --encrypt-key={self.encrypt_key} --encrypt-threads={self.encrypt_threads} --encrypt-chunk-size={self.encrypt_chunk_size}"
            cmd_list.append(encrypt_cmd)
            STATISTICS_INFO['是否加密'] = 'Yes'
        else:
            STATISTICS_INFO['是否加密'] = 'No'

        if hasattr(self, 'xtra_options'):
            xtra_options = self.xtra_options
            cmd_list.append(xtra_options)

        xb_cmd = f"{self.backup_tool} --defaults-file={self.defaults_file} --backup --target-dir={self.fmt_backupdir}"

        return ' '.join((xb_cmd, mysql_cmd, ' '.join(cmd_list)))

    def generate_rsync_cmd(self):
        if hasattr(self, 'remote_host') and hasattr(self, 'remote_ssh_user') \
                and hasattr(self, 'remote_ssh_pass') and hasattr(self, 'remote_dir'):
            rsync_cmd = f"rsync -avprP -e 'sshpass -p {self.remote_ssh_pass} " \
                        f"ssh -o StrictHostKeyChecking=no -l {self.remote_ssh_user}' " \
                        f"{self.fmt_backupdir} {self.remote_ssh_user}@{self.remote_host}:{self.remote_dir}"
            remote_dir = '/'.join((self.remote_dir, os.path.basename(self.fmt_backupdir)))
            return rsync_cmd, self.remote_host, remote_dir


class RunCommand(object):
    def __init__(self, command):
        self.command = command

    @property
    def runner(self):
        status, output = subprocess.getstatusoutput(self.command)
        return {'status': status, 'output': output}


def main():
    start_time = time.time()

    config_file = get_arguments()

    # check whether the config file is valid
    check_config_valid(config_file)

    # check environment
    CheckEnvironment(config_file).check_file_exist()

    # instance Prepare and Toolskit
    prepare = Prepare(config_file)
    tools = ToolsUtils(config_file)

    xb_cmd = prepare.generate_xb_cmd
    logger.info(f'OK: generate xtrabackup command \n {xb_cmd}')

    # exec backup
    backup_result = RunCommand(xb_cmd).runner
    logger.info(f'OK: perform backup process, please waiting.')

    with TemporaryFile('w+t', encoding='gbk') as f:
        if backup_result['status'] == 0:
            logger.info(f'OK: xtrabackup backup success')
            tools.get_backup_file_size()
            tools.get_partition_size()

            # copy files to remote server
            rsync_cmd = prepare.generate_rsync_cmd()
            if rsync_cmd:
                result = RunCommand(rsync_cmd[0]).runner
                logger.info(f'OK: copying backup files to remote server, please waiting.')
                if result['status'] == 0:
                    tools.remove_backup_file()
                    logger.info(f'OK: copy backup files to remote server success')
                    STATISTICS_INFO['远程主机'] = rsync_cmd[1]
                    STATISTICS_INFO['远程目录'] = rsync_cmd[2]
                else:
                    logger.error(f'FAIL: copy backup files to remote server fail')
                    logger.error(f"ERROR: {result['output']}")
                    STATISTICS_INFO['远程拷贝'] = '失败'
                    STATISTICS_INFO['失败原因'] = result['output']

            end_time = time.time()
            STATISTICS_INFO['备份耗时'] = '{:0.2f}s'.format(end_time - start_time)

            result = render_to_template(html_template, STATISTICS_INFO)
            f.write(result)
        else:
            logger.error(f"ERROR: {backup_result['output']}")
            f.write(backup_result['output'])

        f.seek(0)
        TEXT_DATA = f.read()

        tools.send_mail(TEXT_DATA)


if __name__ == '__main__':
    main()

