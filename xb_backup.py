# -*- coding:utf-8 -*-
# edit by fuzongfei

import argparse
import configparser
import logging
import os
import shutil
import smtplib
import socket
import subprocess
import sys
import time
from email.mime.text import MIMEText
from os.path import isfile

# set logger
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
logging.basicConfig(level=logging.DEBUG, format=LOG_FORMAT, datefmt=DATE_FORMAT)
logger = logging.getLogger(__name__)

# get hostname
hostname = socket.gethostname()
# get time
current_time = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())
# set statistics
backup_statistics = [{'备份主机': hostname}]


# get input
def get_arguments():
    parser = argparse.ArgumentParser(description='This a backup help document.')
    parser.add_argument('-f', '--file', type=str, help='xtrabackup read config file')
    args = parser.parse_args()
    return args.file


def check_file_content_valid(file):
    """
    # Check config file content valid
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
        'mysqladmin',
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
    # Process the config file and Generate variables
    """

    def __init__(self, file):
        if isfile(file):
            config = configparser.ConfigParser(allow_no_value=True)
            config.read(file)

            Mysql = config['mysql']
            self.mysqladmin = Mysql['mysqladmin']
            self.user = Mysql['user']
            self.host = Mysql['host']
            self.password = Mysql['password']
            self.port = Mysql['port']

            Xtrabackup = config['xtrabackup']
            self.backup_tool = Xtrabackup['backup_tool']
            self.defaults_file = Xtrabackup['defaults-file']
            self.backupdir = Xtrabackup['backupdir']
            self.fmt_backupdir = '/'.join((Xtrabackup['backupdir'], current_time))
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


class CheckEnv(General):
    """
    # Check environment
    """

    def __init__(self, file):
        self.file = file
        General.__init__(self, self.file)

    def check_mysql_backuptool(self):
        if not os.path.exists(self.backup_tool):
            logger.error(f'FAILED: {self.backup_tool} not found.')
            sys.exit(1)
        else:
            logger.info(f'OK: backup tool is {self.backup_tool}')

    def check_sshpass(self):
        if not os.path.exists('/usr/bin/sshpass'):
            logger.error(f'FAILED: /usr/bin/sshpass not found.')
            sys.exit(1)

    def check_mysql_status(self):
        statusargs = f"{self.mysqladmin} --user={self.user} --password={self.password} --host={self.host} status"
        status, output = subprocess.getstatusoutput(statusargs)
        if status == 0:
            logger.info('OK: MySQL Server is up and running')
        else:
            logger.error('FAILED: MySQL Server is not up')
            sys.exit(1)

    def check_mysql_config_file(self):
        if not os.path.exists(self.defaults_file):
            logger.error(f'FAILED: {self.defaults_file} not found.')
            sys.exit(1)
        else:
            logger.info(f'OK: default file is {self.defaults_file}')

    def check_all_env(self):
        self.check_mysql_backuptool()
        self.check_sshpass()
        self.check_mysql_config_file()
        self.check_mysql_status()
        return True


class ToolsKit(General):
    """
    # define some tools
    """

    def __init__(self, file):
        self.file = file
        General.__init__(self, self.file)

        self.xb_output_log = '/'.join((self.fmt_backupdir, 'xb_output.log'))

        backup_statistics.append({
            '备份目录': self.fmt_backupdir,
            '备份工具': self.backup_tool,
        })

    def create_backup_dir(self):
        """ create backup directory """
        if not os.path.exists(self.fmt_backupdir):
            os.makedirs(self.fmt_backupdir)
            logger.info(f'OK: the backup dir not exisit, create {self.fmt_backupdir}')

    def log_backup_output(self, content):
        """ log xtrabackup produce output to file """
        with open(self.xb_output_log, 'a') as f:
            f.write(content)
            f.write('\n')

    FMT_INFO = '{:.2f}GB'

    @property
    def get_backup_file_size(self):
        size = 0
        for root, dirs, files in os.walk(self.fmt_backupdir):
            size += sum([os.path.getsize(os.path.join(root, name))
                         for name in files])
        logger.info(f'OK: get backup file size')
        return {'文件大小': self.FMT_INFO.format(float(size / 1024 / 1024 / 1024))}

    @property
    def get_partition_size(self):
        vfs = os.statvfs(self.fmt_backupdir)
        free = (vfs.f_bavail * vfs.f_bsize) / (1024 * 1024 * 1024)
        total = (vfs.f_blocks * vfs.f_bsize) / (1024 * 1024 * 1024)
        partition_free_size = self.FMT_INFO.format(free)
        partition_total_size = self.FMT_INFO.format(total)
        logger.info(f'OK: get disk partition usage')
        return {'可用空间': partition_free_size, '总空间': partition_total_size}

    def remove_backup_file(self):
        """ if remove_local_backup = Yes, delete local backup files """
        if hasattr(self, 'remote_host') and hasattr(self, 'remote_ssh_user') \
                and hasattr(self, 'remote_ssh_pass') and hasattr(self, 'remote_dir') \
                and hasattr(self, 'remove_local_backup'):
            if self.remove_local_backup == 'Yes':
                shutil.rmtree(self.fmt_backupdir)
                backup_statistics.append({'本地留存': 'No'})
                logger.info(f"OK: the directory {self.fmt_backupdir} remove success")
        else:
            backup_statistics.append({'本地留存': 'Yes'})
            return False

    def send_mail(self, file=False, data=None):
        """ 
        send mail notice 
        fail: read and send self.xb_output_log
        success: send backup_statistics
        """
        FMT_INFO = '{} --> {}\n'
        if file is True:
            content = ''.join(open(self.xb_output_log).readlines())
        else:
            content_list = []
            for i in data:
                for k in i:
                    content_list.append(FMT_INFO.format(k, i[k]))
            content = '\n'.join(content_list)
        msg = MIMEText(content, _subtype='plain', _charset='utf8')
        msg['Subject'] = '{} from {}'.format(self.title, hostname)
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
    # Generate command
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
            backup_statistics.append({'是否压缩': 'Yes'})
        else:
            backup_statistics.append({'是否压缩': 'No'})

        if hasattr(self, 'encrypt') and hasattr(self, 'encrypt_key') and hasattr(self, 'encrypt_threads') and hasattr(
                self, 'encrypt_chunk_size'):
            encrypt_cmd = f"--encrypt={self.encrypt} --encrypt-key={self.encrypt_key} --encrypt-threads={self.encrypt_threads} --encrypt-chunk-size={self.encrypt_chunk_size}"
            cmd_list.append(encrypt_cmd)
            backup_statistics.append({'是否加密': 'Yes'})
        else:
            backup_statistics.append({'是否加密': 'No'})

        if hasattr(self, 'xtra_options'):
            xtra_options = self.xtra_options
            cmd_list.append(xtra_options)

        xb_cmd = f"{self.backup_tool} --defaults-file={self.defaults_file} --backup --target-dir={self.fmt_backupdir}"

        return ' '.join((xb_cmd, mysql_cmd, ' '.join(cmd_list)))

    @property
    def generate_rsync_cmd(self):
        if hasattr(self, 'remote_host') and hasattr(self, 'remote_ssh_user') \
                and hasattr(self, 'remote_ssh_pass') and hasattr(self, 'remote_dir'):
            rsync_cmd = f"rsync -avprP -e 'sshpass -p {self.remote_ssh_pass} " \
                        f"ssh -o StrictHostKeyChecking=no -l {self.remote_ssh_user}' " \
                        f"{self.fmt_backupdir} {self.remote_ssh_user}@{self.remote_host}:{self.remote_dir}"
            backup_statistics.append({'远程主机': self.remote_host})
            backup_statistics.append({'远程目录': '/'.join((self.remote_dir, os.path.basename(self.fmt_backupdir)))})
            return rsync_cmd
        else:
            return False


class RunCommand(object):
    def __init__(self, command):
        self.command = command

    @property
    def runner(self):
        status, output = subprocess.getstatusoutput(self.command)
        return {'status': status, 'output': output}


def xb_run():
    config_file = get_arguments()

    # check whether the config file is valid
    check_file_content_valid(config_file)
    logger.info(f"OK: the config file {config_file} check success")

    # check environment
    CheckEnv(config_file).check_all_env()
    logger.info(f'OK: the environment check success')

    # instance Prepare and Toolskit
    prepare = Prepare(config_file)
    tools = ToolsKit(config_file)

    xb_cmd = prepare.generate_xb_cmd
    logger.info(f'OK: generate xtrabackup command \n {xb_cmd}')

    # exec backup
    backup_result = RunCommand(xb_cmd).runner
    logger.info(f'OK: perform backup process, please waiting...')

    # log output to file
    tools.log_backup_output(backup_result['output'])
    if backup_result['status'] == 0:
        logger.info(f'OK: perform backup process success')
        get_backup_file_size = tools.get_backup_file_size
        get_partition_size = tools.get_partition_size
        backup_statistics.append(get_backup_file_size)
        backup_statistics.append(get_partition_size)

        time.sleep(2)

        # copy files to remote server
        rsync_cmd = prepare.generate_rsync_cmd
        if rsync_cmd:
            result = RunCommand(rsync_cmd).runner
            logger.info(f'OK: copying backup files to remote server, waiting...')
            if result['status'] == 0:
                logger.info(f'OK: copy backup files to remote server success')
                tools.remove_backup_file()
            else:
                logger.error(f'FAIL: copy backup files to remote server fail')

        tools.send_mail(data=backup_statistics)
    else:
        logger.info(f'FAILED: perform backup process fail')
        tools.send_mail(file=True)


if __name__ == '__main__':
    xb_run()
