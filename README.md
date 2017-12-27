# xb_backup
xtrabackup simple scripts
支持：
1. 记录备份信息，通过xtrabackup --history获取
2. 支持备份后，发送邮件
a. 备份成功，发送统计状态信息
b. 备份失败，发送xtrabackup输出的日志信息

环境部署：
1. 安装python3.5+ <br>
   yum -y install openssl <br>
   ./configure --prefix=/usr/local/python3.6 && make -j4 && make install <br>
   ln -s /usr/local/python3.6/bin/python3.6 /usr/local/bin <br>
2. 安装mysql-connector-python-2.1.6 <br>
  wget https://dev.mysql.com/get/Downloads/Connector-Python/mysql-connector-python-2.1.6.zip <br>
  tar -zxf mysql-connector-python-2.1.6.zip <br>
  python3.6 setup.py install <br>

3. 安装xtrabackup最新版

使用方法：
1. 编辑配置文件
vim /etc/xtrabackup.cnf 

2. 命令
python3.6 xb_backup.py -f/etc/xtrabackup.cnf


最后邮件收到的内容：
```
[xtrabackup info]
uuid --> 87489253-ea81-11e7-b2c2-002590e04920
name --> None
tool_name --> xtrabackup
tool_command --> --defaults-file=/etc/my.cnf --user=bkpuser --password=... --host=127.0.0.1 --port=3306 --backup --target-dir=/backup/xtrabackup/2017-12-27_05:00:01/data --compress --compress-threads=2 --compress-chunk-size=64K --parallel=4 --encrypt=AES256 --encrypt-threads=2 --encrypt-key=... --rsync --history --binlog-info=ON
tool_version --> 2.4.7
ibbackup_version --> 2.4.7
server_version --> 5.6.36-82.0-log
start_time --> 2017-12-27 05:00:04
end_time --> 2017-12-27 05:12:49
lock_time --> 0
binlog_pos --> filename 'binlog.000650', position '644582423'
innodb_from_lsn --> 0
innodb_to_lsn --> 1534097333635
partial --> N
incremental --> N
format --> file
compact --> N
compressed --> Y
encrypted --> Y
backup_file_size --> 17.61GB
partition_free_size --> 981.99GB
partition_total_size --> 5039.53GB
```
