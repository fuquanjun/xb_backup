# 使用python简单封装的脚本，实现自动化备份、通知

支持：
1. 邮件发送备份信息(html格式)
2. 支持备份信息的统计
3. 支持自动拷贝到远程主机目录

环境部署：
1. 安装python3.6
2. rpm -ivh percona-xtrabackup-24-2.4.9-1.el7.x86_64.rpm
3. yum -y install sshpass
3. pip install jinja2 MarkupSafe

创建备份用户
create user 'bkpuser'@'127.0.0.1' identified by 'Phqwrx4FuKb6';<br>
grant RELOAD, LOCK TABLES, PROCESS, REPLICATION CLIENT, SUPER, CREATE, INSERT, SELECT on *.* to 'bkpuser'@'127.0.0.1';<br>
flush privileges;<br>

随机生成24字节序列，然后使用base64编码的字符串
xtrabackup加密密钥<br>
openssl rand -base64 24<br>
--> /Ypbi69zhme8KifZc6FEFHb+XnhtKA8J<br>

使用方法：
1. 编辑配置文件
vim /etc/xb_backup.cnf 

2. 命令
python3.6 xb_backup.py -f/etc/xb_backup.cnf

邮件格式：
html表格格式
```
备份主机	dj-mysql-244-33
备份目录	/data/backup/xtrabackup/2018-01-17_13:47:58
备份工具	/usr/bin/xtrabackup
是否压缩	Yes
是否加密	Yes
备份大小	0.44GB
可用空间	88.04GB
总空间	99.95GB
本地留存	No
远程主机	10.74.243.50
远程目录	/data/backup/2018-01-17_13:47:58
备份耗时	22.53s
```
