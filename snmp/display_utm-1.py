import pandas as pd
import pymysql
from sqlalchemy import create_engine
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from statistics import mean
from datetime import datetime
import matplotlib.dates as mdt

ifname = 'eth2'
if_usage_df = None
# connect to snmpdb
dbuser = 'snmpuser'
dbuser_pwd = 'snmpuser'
db_engine = create_engine("mysql+pymysql://"+dbuser+':'+dbuser_pwd +"@10.1.1.148:3306/snmpdb")

with db_engine.connect() as conn:
  if_usage_df = pd.read_sql_query("select name, date, InOctets, OutOctets from utm_interface_usage where name = 'eth2' and date(date) = curdate()", db_engine, index_col='name')
  # if_usage_df = pd.read_sql_query("select name, date, InOctets, OutOctets from utm_interface_usage where name = 'eth2'" , db_engine, index_col='name')

sampled = if_usage_df.resample('H', on='date').mean()
sampled.rename(columns={'InOctets':'In', 'OutOctets': 'Out'}, inplace=True)
in_max = max(sampled['In'])
out_max = max(sampled['Out'])

kilo = 1000; mega = 1000000
y_unit = None

vect_sample = None
def convert_unit(row, div):
	return pd.Series( { 'In': round(row['In']/div),'Out': round(row['Out']/div) })

# 데이터 크기에 따른 단위 변환
if in_max >= mega or out_max >= mega:
	vect_sample = sampled.apply(lambda x: convert_unit(x, mega), axis=1)	
	y_unit = 'Mbit/s'
else:
	vect_sample = sampled.apply(lambda x: convert_unit(x, kilo), axis=1)
	y_unit = 'Kbit/s'

print(vect_sample)
ax = vect_sample.plot()
ax.set_ylabel(y_unit)

plt.show()
# ifdate = if_usage_df.date
# InOctets = if_usage_df.InOctets
# OutOctets = if_usage_df.OutOctets

# in_arr = InOctets.values
# out_arr = OutOctets.values

# kilo = 1000; mega = 1000000
# y_unit = None
# if mean(in_arr) >= mega  or mean(out_arr) >= mega:
# 	in_arr = [ round(n/mega) for n in in_arr]
# 	out_arr = [ round(n/mega) for n in out_arr]
# 	y_unit = 'Mbit/s'
# else:
# 	in_arr = [ round(n/kilo) for n in in_arr]
# 	out_arr = [ round(n/kilo) for n in out_arr]
# 	y_unit = 'Kbit/s'


# # print(ifdate.astype(datetime))
# fig, ax = plt.subplots()
# ax.set_xlabel('hour')
# ax.set_ylabel(y_unit)
# xlocator = mdt.HourLocator()
# xformatter = mdt.DateFormatter('%H')
# ax.xaxis.set_major_locator(xlocator)
# ax.xaxis.set_major_formatter(xformatter)
# # convert datetime64 to Object type (ex: python datetime)
# ax.plot(ifdate.astype('O'), in_arr)

# fig.tight_layout()
# plt.show()
  
 
#   