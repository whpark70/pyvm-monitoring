
from datetime import datetime, timedelta
from collections import defaultdict, deque
import time, configparser, ssl, atexit
import re, os

from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect

import pytz
from pytz import timezone

import matplotlib.pyplot as plt
import matplotlib as mpl
from dateutil.rrule import MINUTELY
import matplotlib.dates as mdt
import numpy	as np
from scipy.interpolate import interp1d

from pandas import Series, DataFrame
import pandas as pd


# vCenter 접속용 변수 
config, host, user, password, si, ssl_context = [ None for _ in range(6) ]       # si: servercie instacne
# Managed Object in vSphere 602
content, perfManager, viewManager, propertyCollector, searchIndex, container = [ None for _ in range(6) ]

def readConfig(inifile='monitor.ini'):
    global config
    config = configparser.ConfigParser()
    #conf = config.read(inifile)
    filename = os.path.join(os.path.abspath(os.path.dirname(__file__)), '', inifile)
    conf = config.read(filename)
    if len(conf) == 0:
        raise ValueError("Failed to open monitor.ini file")

    return config

# Return a string list from a ConfigParser option. By default,
# split on a comma and strip whitespaces."""
def getlist(option, sep=',', chars=None):
    return [ chunk.strip(chars) for chunk in option.split(sep) ]

# config file의 [vm.hostname]의 base에 등록된 server list를 가져온다. 2018. 04. 10
def getVmList(option='base'):
    global config
    if config == None:  readConfig()
    vm_hostnames = getlist(config['vm.hostname'][option])
    return vm_hostnames


# make vm server moref id from section: [vm.hostname] opiton:['base']
def makeManagedObjectIdFromConfig(option='base'):
    global config
    if config == None:  readConfig()
    vm_hostnames = getlist(config['vm.hostname'][option])           # [ 'kerp', 'kerpdb']
    moids = []
    for hostname in vm_hostnames:
        moids.append( getManagedObjectRefId(hostname) )

    return moids

# get metric for counter id
def getMetricIdFromCounterId(cid):
    metricId = vim.PerformanceManager.MetricId(counterId=cid, instance="") 
    return metricId


# Config 파일에서 [counter.ids] section으로 부터 counter id들을 가저와 
# metric id list를 생성하여 반환
# section : counter.ids
# option: common (default)
def makeMetricIdFromConfig(option='common'):
    
    global config
    if config == None:  readConfig()

    cids = config['counter.ids'][option]
    cid_list = getlist(cids)    # stirng list --> int list
    metricIds = [ vim.PerformanceManager.MetricId(counterId=int(id), instance="") for id in cid_list ]

    return metricIds

# apsi.co.kr domain에 포함된 vm objects를 return
def getAllVmInDomain():
    global container, viewManager

    viewType = [vim.VirtualMachine]
    recursive = True
    vms = []
    
    # create a list of vim.VirtualMachine bojects
    containerView = viewManager.CreateContainerView(container, viewType, recursive)

    regex = re.compile('apsi.co.kr')

    for vm in containerView.view:
        dnsname = vm.guest.hostName
        if dnsname != None and regex.search(dnsname) != None:
            vms.append(vm)

    return vms

# get Managed Object Reference Id to specific entity (vm)
def getManagedObjectRefId(vmname=None):
    dnsname = vmname + '.apsi.co.kr'
    entity = searchIndex.FindByDnsName(None,dnsname, True)
    moid = entity.summary.vm

    return moid

# get vm name (except domain name) from virtual manchine moref id
def getVmNameFromMoRefId(vm_moid=None):
    vmname = vm_moid.name
    name = vmname.split('.')[0]

    return name

# vCenter에 접속하고, 성능측정을 위한 기본 Managed Object 설정 
def setupManagedObject():
    global config, host, user, password, si, ssl_context
    global content, perfManager, viewManager, propertyCollector, searchIndex, container
    
    # monitor.ini file로부터 설정 정보를 읽어 옴
    readConfig()  
        
    # vCenter 연결정보 
    section = 'vCenter'
    host = config[section]['host']
    user = config[section]['user']
    password = config[section]['password']

    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
    ssl_context.verify_mode = ssl.CERT_NONE
    
    try :
        si = SmartConnect(host=host, user=user, pwd=password, sslContext=ssl_context)
        atexit.register(Disconnect, si)

    except IOError as e:
        pass

    if not si:
        raise SystemExit("unable to connect to host.")

    content = si.RetrieveServiceContent()

    # get PerformanceManager, ViewManager & PropertyCollector
    perfManager = content.perfManager

    viewManager = content.viewManager
    propertyCollector = content.propertyCollector
    searchIndex = content.searchIndex
    container = content.rootFolder      # starting point for query 


# performance metrics repository per entity
class EntityPerfInfo(object):
    """docstring for MetricInfo"""
    # enity id: Managed Object to being monitored
    def __init__(self, moid, counterMetricIds, collectInAdvance=True):
        super(EntityPerfInfo, self).__init__()
        self.moid = moid 		# Managed Object Reference ID of entity
        self.name = None		# dns name or server name
        self.monitorOn = False		# turn entity on/off for all perf counter id of entity

        # Definition of the queries for getting performance data form vCenter
        #self.qSpecs = []			# for vSphere 6.5
        self.qSpec = vim.PerformanceManager.QuerySpec()


        self.intervalId = 20		# QueryPerfProviderSummary.refreshRate : perf data query cycle: realtime(20s)
        self.maxSample = 1
        self.endTime = datetime.now(pytz.utc)
        self.startTime = self.endTime - timedelta(minutes=30) 		# Performance data Query start time , 현 시점에서 30분 전 데이터부터 수집
        self.counterMetricIds = counterMetricIds			# monitering이 on으로 설정된 metric ids (perf conter ids):list

        # x, y date for plotting
        self.timestamp = deque(maxlen=90)		# x-data: query timestamp. 20초 간격으로 수집 1분에 3개, 30분 당안 90개
        self.counterIds_Metrics = {}			# y-data: metrics per counter id

        self.setupQuerySpecs()
        if collectInAdvance == True: 
            self.collectMetrics()					# in advance, collect previous 30-mins data


    # return perf counter ids being monitored currently
    def getCounterMetricIds(self):
        return self.counterMetricIds

    def setCounterMetricIds(self, counterMetricIds):
        self.counterMetricIds = counterMetricIds

    # modify(add/remove) perf counter ids being monitored currently
    def modifyCounterMetricIds(self, counterMetricIds):
        modified = cmp(self.counterMetricIds, counterMetricIds) 		# counter id의 변화가 있으면, 성능 데이터 수집함수 호출
        self.counterMetricIds = counterMetricIds

    # setup Query Spec
    # maxSample: # of sample, use to determine whether reatime or not
    def setupQuerySpecs(self,max_sample=90):
        try:

            if	len(self.counterMetricIds) != 0:
                self.qSpec.entity = self.moid
                self.qSpec.metricId = self.counterMetricIds
                self.qSpec.startTime = self.startTime
                self.qSpec.maxSample = max_sample
                self.qSpec.intervalId = self.intervalId
                self.qSpec.format = "normal"
                # self.qSpecs.append(qSpec)
            else:
                raise Exception("at first, Configure MetricId to monitoring")

        except Exception as e:
            print(e.args)

    def startCollectMetrics(self, monitoron=True):
        self.monitorOn = monitoron
        self.collectMetrics()

    def stopCollectMetrics(self, monitoron=False):
        self.monitorOn = monitoron

    # Retrieve the peroformance metrics for this entity
    # based on the properties specified in the qSpecs
    # 지난 데이터 수집용: perform once
    def collectMetrics(self):

        global perfManager

        self.qSpec.maxSample = 90
        metricsOfEntity = perfManager.QueryStats(querySpec=[self.qSpec])

        for m in metricsOfEntity:
            for ts in m.sampleInfo:
                self.timestamp.append(ts.timestamp)

            for metric in m.value:			# walk through conter id
                cid = metric.id.counterId
                metrics = metric.value[:]
                self.counterIds_Metrics.setdefault(cid, deque(maxlen=90)).extend(metrics)  # 5분간의 데이터 저장

        #print('collectMetrics func: collecting performance data....')		#
        return self.timestamp, self.counterIds_Metrics


    # for realtime: update 용
    def generateMetrics(self, monitoron=True): 	# generator
        
        global perfManager
        self.qSpec.maxSample = 1
              
        while monitoron:
            
            metricsOfEntity = perfManager.QueryStats(querySpec=[self.qSpec])

            timestamp_in_gen ,metrics_in_gen = None, {}

            for m in metricsOfEntity:
                for ts in m.sampleInfo:
                    timestamp_in_gen =ts.timestamp
                    self.timestamp.append(ts.timestamp)     # update orginal timestamp

                for metric in m.value:			# walk through conter id
                    cid = metric.id.counterId
                    metrics = metric.value[0]	# only one
                    metrics_in_gen.setdefault(cid, metrics)
                    self.counterIds_Metrics.setdefault(cid, deque(maxlen=90)).append(metrics)     # update original metrics

            yield timestamp_in_gen, metrics_in_gen

            time.sleep(20)

    def getMetrics(self): 
        
        global perfManager
        self.qSpec.maxSample = 1
                   
        metricsOfEntity = perfManager.QueryStats(querySpec=[self.qSpec])

        for m in metricsOfEntity:
            for ts in m.sampleInfo:
                self.timestamp.append(ts.timestamp)     # update orginal timestamp

            for metric in m.value:          # walk through conter id
                cid = metric.id.counterId
                metrics = metric.value[0]   # only one
                self.counterIds_Metrics.setdefault(cid, deque(maxlen=90)).append(metrics)     # update original metrics
               

# added: 2018. 04. 09
def interploateMetrics(ts, metrics, kind='quadratic' ):
    '''
    scipy.interploate.interp1d를 이용한 데이타 보간
    ts, metrics: orignal data which need to interpolate (timestamp, metrics)
    kind: kind of interpolation
    return: interpolated timestamp for mpl, metrics
    데이터 보간함수는 object array를 데이터(여기서는 datatime list)기반이 아니므로, timestamp list를 float list로 변환해서 
    보간함수르 구한다.
    '''

    # interp1d func가 argument로 object array를 받지 않기 때문에 
    # datetime.datetime 유형을 float형으로 변환(Unix time: 1970.01.01 이후의 누적 초)
    unix_ts = [ t.timestamp() for t in ts] 

    # interpolation(보간)을 하기 위해 time interval을 조정, ex) interaval 10secs
    ts_new = [ t for t in np.arange(min(unix_ts), max(unix_ts) + 1, 5.0) ] 
    
    # 보간 된 위 ts_new를 mpl datetime float format으로 변환(기준 변경 : 1970.1.1  -> 0001.1.1 UTC)
    # mpl datetime float format을 mpl datetime으로 변환
    # mpl은 기본적으로 plotting을 하기 위해 datetime을 형식의 data를 float으로 변환한다. 
    mpl_ts_new = [ mdt.num2date(mdt.epoch2num(t)) for t in np.arange(min(unix_ts), max(unix_ts) + 1, 5.0) ]
   
    # 기존 데이터를 이용한 interpolation function을 구한다
    f = interp1d(unix_ts, metrics, kind=kind)
    # 위 보간함수를 이용하여 새 데이터에 대한 함수 값을 구한다. 
    metrics_new = f(ts_new)

    return mpl_ts_new, metrics_new



# data generator for Test
class MetricGeneratorForTest(object):
    """docstring for GenData"""
    def __init__(self):
        super(MetricGenerator, self).__init__()
        self.past_xdata = [datetime.now(pytz.utc) - timedelta(seconds=i) for i in range(30*60, 0, -20) ]
        self.past_ydata = [ random.randint(1,50) for _ in range(90)]

    def gen(self):
        for i in range(1000):
            if i == 0:
                yield self.past_xdata, self.past_ydata
            else:
                yield datetime.now(pytz.utc), ps.cpu_percent()

            time.sleep(20)

# monitoring programm using VMWare Managed Object Management Interface(vmomi)
if __name__ == '__main__':
    
    # vCenter 연결 및 주요 MO 생성
    setupManagedObject()
    # 특정 VM 에 대한 ref id를 얻음.
    moref_id = getManagedObjectRefId(vmname='kerpdb')
    # 모니터링할 MetricsId 생성
    cid = 1
    metricId = vim.PerformanceManager.MetricId(counterId=int(cid), instance="")
    # Performance Info 생성 
    entityMetricsInfo = EntityPerfInfo(moid=moref_id, counterMetricIds=[ metricId] )
    print(entityMetricsInfo.timestamp)
    entityMetricsInfo.getMetrics()
    print(entityMetricsInfo.timestamp)

    '''
    ts = list(entityMetricsInfo.timestamp)
    metrics = list(entityMetricsInfo.counterIds_Metrics[cid])
    
    # get interpolated data
    mpl_ts_new, metrics_new = interploateMetrics(ts, metrics)

    axes = plt.axes()

    seoul = pytz.timezone('Asia/Seoul')
    now = datetime.now(pytz.UTC)
    delta = timedelta(minutes=30)

    axes.set_xlim([min(mpl_ts_new), max(mpl_ts_new)])
    #axes.set_xlim([min(ts_new), max(ts_new)])

    xlocator = mdt.AutoDateLocator(interval_multiples=True)
    xlocator.intervald[MINUTELY] = [10]
    xformatter = mdt.DateFormatter('%H:%M', tz=seoul)
    axes.xaxis.set_major_locator(xlocator)
    axes.xaxis.set_major_formatter(xformatter)


    plt.plot(mpl_ts_new, metrics_new)
    plt.show()
    '''
   

