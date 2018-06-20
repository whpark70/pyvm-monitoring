import pandas as pd
import pymysql
from sqlalchemy import create_engine
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from statistics import mean
from datetime import datetime, timedelta
import matplotlib.dates as mdt
import matplotlib.ticker as ticker


# type: search type (ex: daily, weekly. ...)
# days: # of day, 일자 수에 따라 ticker 개수 조정을 위하여 
# return: x-axis, xlocator, formatter
def get_xlocator_formatter_network(axis=ax, type=None, days=0):
	'''
	검색 구간에 맞는 x축 label 설정
	'''
	xlocator = None
	xformatter = None
		
	if type == 'daily':
		xlocator = mdt.HourLocator()
		xformatter = mdt.DateFormatter('%H')
		ax.set_xlabel('hour')

	elif type == 'weekly':
		xlocator = mdt.DayLocator()
		xformatter = mdt.DateFormatter("%m/%d")
		ax.set_xlabel('date')
	elif type == 'monthly':
		xlocator = ticker.MaxNLocator(nbins=5)
		xformatter = mdt.DateFormatter("%m/%d")
		ax.set_xlabel('date')
	elif type == 'yearly':
		xlocator = mdt.MonthLocator()
		xformatter = mdt.DateFormatter("%m")
		ax.set_xlabel('month')
	else:
		if (days > 7) and (days <= 31):
			xlocator = ticker.MaxNLocator(nbins=5)
			xformatter = mdt.DateFormatter("%m/%d")
			ax.set_xlabel('date')
		else:
			xlocator = mdt.AutoDateLocator()
			xformatter = mdt.DateFormatter("%m/%d")
			# xformatter = mdt.AutoDateFormatter(xlocator)

	return ax, xlocator, xformatter


# In/Out의 Sacle 문제가 있을 경우, 각각 조정 가능하게 함.
# row: datafraem Series (row)
# div: 전송된 데이터 량의 단위를 조절하기 위해 나누어 주는 값: mega, kilo, giga
def convert_unit(row, div, type='Both'):
	if type == 'Both':
		return pd.Series( { 'In': round(row['InOctets']/div),'Out': round(row['OutOctets']/div) })
	elif type == 'In':
		return pd.Series( { 'In': round(row['InOctets']/div) } )
	elif type == 'Out':
		return pd.Series( { 'Out': round(row['OutOctets']/div) } )


ifname = 'eth2'
sdate = '2018-05-24'; edate = '2018-06-01'
if_usage_df = None
# connect to snmpdb
dbuser = 'snmpuser'
dbuser_pwd = 'snmpuser'
db_engine = create_engine("mysql+pymysql://"+dbuser+':'+dbuser_pwd +"@10.1.1.148:3306/snmpdb")
base_sql = "select * from utm_interface_usage "

# 검색 조건: interface name, date
today_sql = base_sql + " where name = %s and DATE(date) = curdate()"
anyday_sql = base_sql + " where name = %s and DATE_FORMAT(date,'%%Y-%%m-%%d') = %s"
week_sql = base_sql + " where name = %s and YEARWEEK(date) = YEARWEEK(%s)"
month_sql = base_sql + " where name = %s and MONTH(date) = MONTH(%s)"
duration_sql = base_sql + " where name = %s and DATE(date) between %s and %s"

params1 =[ifname]
params2 = [ifname,sdate]
params3 = [ifname,sdate, edate]
which_sql = duration_sql


with db_engine.connect() as conn:
  if_usage_df = pd.read_sql_query(which_sql, db_engine, params=params3)

'''
# resample시 data interval 
  - daily: 30T
  - weekly: 

'''
sampling_mean_interval = 'H'
sampled = if_usage_df.resample(sampling_mean_interval, on='date').mean()

in_max = max(sampled['InOctets'])
out_max = max(sampled['OutOctets'])

kilo = 1000; mega = 1000000
y_unit = None

vect_sample = None


# 데이터 크기에 따른 단위 변환
if in_max >= mega or out_max >= mega:
	vect_sample = sampled.apply(lambda x: convert_unit(x, mega), axis=1)	
	y_unit = 'Mbit/s'
else:
	vect_sample = sampled.apply(lambda x: convert_unit(x, kilo), axis=1)
	y_unit = 'Kbit/s'

vect_sample.reset_index(inplace=True)

ifdate = vect_sample.date
# print(vect_sample)

in_arr = vect_sample.In.values
out_arr = vect_sample.Out.values

# # print(ifdate.astype(datetime))
fig, ax = plt.subplots()
ax.set_ylabel(y_unit)


td = datetime.strptime(edate, '%Y-%m-%d' ) - datetime.strptime(sdate, '%Y-%m-%d')
days = td.days		# user defined interval

ax, xlocator, xformatter = get_xlocator_formatter_network(axis=ax, type='monthly',days=days)

ax.xaxis.set_major_locator(xlocator)
ax.xaxis.set_major_formatter(xformatter)

# convert datetime64 to Object type (ex: python datetime)
# ax.plot(ifdate.astype('O'), in_arr)
l1, l2 = ax.plot(ifdate.astype('O'), in_arr, ifdate.astype('O'), out_arr)
ax.legend((l1, l2), ('In', 'Out'))
ax.set_title(ifname)
fig.tight_layout()
plt.show()
  
 
#   