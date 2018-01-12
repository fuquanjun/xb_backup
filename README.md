# xb_backup
xtrabackup simple scripts
支持：
1. 记录备份信息
2. 支持备份后，发送邮件
3. 支持备份完成后，自动拷贝到远程主机目录


环境部署：
1. 安装python3.5+
2. 安装mysql-connector-python-2.1.6 
3. 安装xtrabackup最新版

使用方法：
1. 编辑配置文件
vim /etc/xb_backup.cnf 

2. 命令
python3.6 xb_backup.py -f/etc/xb_backup.cnf


最后邮件收到的内容：
```
备份主机 --> Cent7-mysql-21-110

备份目录 --> /app/backup/2018-01-12_05:00:01

备份工具 --> /usr/local/percona-xtrabackup/bin/xtrabackup

是否压缩 --> Yes

是否加密 --> Yes

文件大小 --> 10.92GB

可用空间 --> 187.16GB

总空间 --> 198.90GB

远程主机 --> 10.73.22.17

远程目录 --> /backup/xtrabackup/user_center/2018-01-12_05:00:01

本地留存 --> No
```
