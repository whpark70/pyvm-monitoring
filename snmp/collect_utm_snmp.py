# UTM interface network In/Out량은 흘러간 데이터 총량을 나타낸다.
# 따라서, 특정 interval간 데이터 량을 계산하기 위해서는 이전 측정한
# 데이터 량을 빼야한다.
# interface_usage table에는 그 interval간 흐른 데이터 량을 저장한다.
# 기본적으로 interval은 5 분으로 설정으로, 이 프로그램은 schedule(corntab) 으로 
# 수행한다.

from pysnmp.hlapi import *
from collections import defaultdict
import pandas as pd
from datetime import datetime
import pytz
import pymysql
from sqlalchemy import create_engine

now = datetime.now()

# snmp data type이 unsigned int이므로 보정, used in dataframe.applymap
def modified_network_usage(s):
  return s if s >= 0 else s + 4294967295

g = bulkCmd(SnmpEngine(),
    CommunityData('public'),
    UdpTransportTarget(('utm_head', 161)),
    ContextData(),
    3, 0,
    ObjectType(ObjectIdentity('IF-MIB', 'ifDescr')),
    ObjectType(ObjectIdentity('IF-MIB', 'ifInOctets')),
    ObjectType(ObjectIdentity('IF-MIB', 'ifOutOctets')),
    lexicographicMode=False
    )

iftable = defaultdict(dict)

for errorIndication, errorStatus, errorIndex, varBinds in g:
  if errorIndication:
    print(errorIndication)
  elif errorStatus:
    print('%s at %s' % (errorStatus.prettyPrint(),
                  errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
  else:
    for name, value in varBinds:
      instance = name.getOid()._value[-1]
      
      if name.getMibSymbol()[1] == 'ifDescr':
        iftable[instance]['name'] = value.prettyPrint()

      if name.getMibSymbol()[1] == 'ifInOctets':
        iftable[instance]['InOctets'] = value._value

      if name.getMibSymbol()[1] == 'ifOutOctets':
        iftable[instance]['OutOctets'] = value._value

df = pd.DataFrame.from_dict(iftable)
df_T = df.T

# current interface snmp data
if_current_df = df_T.set_index('name')

# connect to snmpdb
dbuser = 'snmpuser'
dbuser_pwd = 'snmpuser'

db_engine = create_engine("mysql+pymysql://"+dbuser+':'+dbuser_pwd +"@10.1.1.148:3306/snmpdb")

with db_engine.connect() as conn:
  
  # read and delete prior data from interface_raw table
  # if_prior_df = pd.read_sql_table("interface_raw", db_engine, index_col='name')
  if_prior_df = pd.read_sql_query("select name, InOctets, OutOctets from utm_interface_raw", db_engine, index_col='name')
  db_engine.execute("delete from utm_interface_raw")

  if_usage_df = if_current_df.subtract(if_prior_df,fill_value=0) 
  if_musage_df = if_usage_df.applymap(modified_network_usage)
  
  # save current snmp data
  if_current_df['date'] = now
  if_current_df.to_sql(name='utm_interface_raw', con=db_engine, if_exists='append')
  if_musage_df['date'] = now
  if_musage_df.to_sql(name='utm_interface_usage', con=db_engine, if_exists='append')







