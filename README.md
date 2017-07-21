# xb_backup
xtrabackup simple scripts
支持：
1. 记录备份信息，通过xtrabackup --history获取
2. 支持备份后，发送邮件
a. 备份成功，发送统计状态信息
b. 备份失败，发送xtrabackup输出的日志信息

环境部署：
1. 安装python3.5+
   yum -y install openssl
   ./configure --prefix=/usr/local/python3.6 && make -j4 && make install
   ln -s /usr/local/python3.6/bin/python3.6 /usr/local/bin
2. 安装mysql-connector-python-2.1.6
  wget https://dev.mysql.com/get/Downloads/Connector-Python/mysql-connector-python-2.1.6.zip
  tar -zxf mysql-connector-python-2.1.6.zip
  python3.6 setup.py install

3. 安装xtrabackup最新版

使用方法：
1. 编辑配置文件
vim /etc/xtrabackup.cnf

2. 命令
python3.6 xb_backup.py -f/etc/xtrabackup.cnf
