from datetime import timedelta
from collections import namedtuple
import pymonbase as pmb
from pyVmomi import vim, vmodl

# AP 운영시스템 정보: only for saving vm info
class ApLiveVmInfo(object):
	"""Live VM info class"""
	def __init__(self):
		super(ApLiveVmInfo, self).__init__()
		self.serverName = None				# summary.config.name
		self.description = None				# summary.config.annotaion
		self.guest = None					# summary.config.geustFullName
		self.snapshotStaus = None			# vm.rootSnapshot 참조
		self.vmxPath = None					# VM .vmx path
		self.vDisks = None					# virtual disk pysical info: []
		self.lDisks = None					# virtual disk logical info (drive info): []
		self.nics = None					# virtual network card info: []
		self.ipaddr = None					# virtual machine ip address
		self.limits = None					# cpu: vmcpulimit, memory: vmemlimit
		self.reservations = None				# cpu: vmcpures, memory: vmmemres
		self.numOfvCpu = None 				# summary.config.numCpu
		self.cpuReady = None					# cpu.ready.summation, Average:  , Maximum: 
		self.cpuUsage = None				# cpu.usage.average
		self.memory = None 					# MB: summary.config.memorySizeMB, GB: summary.config.memorySizeMB/1024
		self.memoryShared = None				# pct (%): memoryShared/memorySizeMB, size: mem.shared.average (in MB)
		self.memoryBalloon = None				# pct (%): memoryBallon/memorySizeMB, size: mem.vmmemctl.average (in MB)
		self.memorySwapped = None				# pct (%): memorySwapped/memorySizeMB, size: mem.swapped.average (in MB)
		self.memoryActive = None				# pct (%): memoryActive/memorySizeMB, size: mem.active.average (in MB)
		self.datastoreAvgIo = None			# read : datastore.numberReadAveraged.average (IOPS) , write: datastore.numberWriteAveraged.average (IOPS)
		self.datastoreAvgLatency = None		# read: datastore.totalReadLatency.average (ms), write: datastore.totalWriteLatency.average (ms)
		self.overallNetworkUage = None		# Transmitted: net.transmitted.average (Mbps), Received: net.received.average (Mbps)
		self.hostName = None 				# summary.runtime.host.name
		self.hostCpuDetail = None				# numOfSocket: summary.runtime.host.summary.hardware.numCpuPkgs, numOfCoerPerSocket: summary.runtime.host.summary.hardware.numCpuCores/numOfScoket
		self.hostCpuType = None				# summary.runtime.host.summary.hardware.cpuModel
		self.hostCpuUsage = None				# used: summary.runtime.host.summary.quickStats.overallCpuUsage , total
		self.hostMemoryUsage = None			# summary.runtime.host.summary.quickStats.overallMemoryUsage/1024,  total


def GetVmInfo(vm, content, vchtime, interval, perf_dict):
	
	statInt = interval * 3		# There are 3 20s samples in each minute
	summary = vm.summary
	disk_list = []
	network_list = []

	# Convert limit and reservation values from -1 to None
	if vm.resourceConfig.cpuAllocation.limit == -1:
		vmcpulimit = "None"
	else:
		vmcpulimit = "{} Mhz".format(vm.resourceConfig.cpuAllocation.limit)

	if vm.resourceConfig.memoryAllocation.limit == -1:
		vmmemlimit = "None"
	else:
		vmmemlimit = "{} MB".format(vm.resourceConfig.memoryAllocation.limit)

	if vm.resourceConfig.cpuAllocation.reservation == 0:
		vmcpures = "None"
	else:
		vmcpures ="{} Mhz".format(vm.resourceConfig.cpuAllocation.reservation)

	if vm.resourceConfig.memoryAllocation.reservation == 0:
		vmmemres = "None"
	else:
		vmmemres = "{} MB".format(vm.resourceConfig.memoryAllocation.reservation)

	vm_hardware = vm.config.hardware
	for each_vm_hardware in vm_hardware.device:
		if(each_vm_hardware.key >= 2000) and (each_vm_hardware.key < 3000):
			disk_list.append('{} | {:.1f}GB | Thin: {} | {}'.format(each_vm_hardware.deviceInfo.label,
														each_vm_hardware.capacityInKB/1024/1024,
														each_vm_hardware.backing.thinProvisioned,
														each_vm_hardware.backing.fileName))
		elif(each_vm_hardware.key >= 4000) and (each_vm_hardware.key < 5000):
			network_list.append('{} | {} | {}'.format(each_vm_hardware.deviceInfo.label,
													each_vm_hardware.deviceInfo.summary,
													each_vm_hardware.macAddress))

	# Disk Usage
	guestDiskInfos = vm.guest.disk
	DiskInfo = namedtuple('DiskInfo', 'dirve, capacity, free, usage')

	diskinfo_list = []
	for gdiskinfo in guestDiskInfos:
		drive = gdiskinfo.diskPath[0]
		capacity = gdiskinfo.capacity/1024/1024/1024
		free = gdiskinfo.freeSpace/1024/1024/1024
		usage = (capacity - free)/capacity * 100
		diskinfo = DiskInfo(drive,capacity,free,usage)

		diskinfo_list.append(diskinfo)

	diskinfo_list.sort(key=lambda diskinfo: diskinfo[0])

	diskinfo_print_list = []
	for di in diskinfo_list:
		diskinfo_print_list.append('Drive: {}, Capacity: {:0.1f}GB, Free: {:0.1f}GB, Usage: {:0.1f}%'.format(di.dirve, di.capacity, di.free,di.usage))

	# CPU Ready Average
	statCpuReady = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'cpu.ready.summation')), "", vm, interval)
	cpuReady = (float(sum(statCpuReady[0].value[0].value)) / statInt)
	# CPU Usage Average %
	statCpuUsage = BuildQuery(content, vchtime, (StatCheck(perf_dict,'cpu.usage.average')),"", vm, interval)
	cpuUsage = ((float(sum(statCpuUsage[0].value[0].value)) / statInt) / 100)
	# Memory Active Average MB
	statMemoryActive = BuildQuery(content, vchtime, (StatCheck(perf_dict,'mem.active.average')), "", vm, interval)
	memoryAcitve = (float(sum(statMemoryActive[0].value[0].value) / 1024) / statInt)
	# Memory Shared
	statMemoryShared = BuildQuery(content, vchtime, (StatCheck(perf_dict,'mem.shared.average')), "", vm, interval)
	memoryShared = (float(sum(statMemoryShared[0].value[0].value) / 1024) / statInt)
	# memoryBalloon 
	statMemoryBalloon = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'mem.vmmemctl.average')), "", vm, interval)
	memoryBallon = (float(sum(statMemoryBalloon[0].value[0].value) /1024 ) / statInt)
	# memory Swapped
	statMemorySwapped = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'mem.swapped.average')), "", vm, interval)
	memorySwapped = (float(sum(statMemorySwapped[0].value[0].value) / 1024) / statInt)
	
	# Datastore Average IO
	statDatastoreIoRead = BuildQuery(content, vchtime, (StatCheck(perf_dict,'datastore.numberReadAveraged.average')), "*", vm, interval)
	DatastoreIoRead = (float(sum(statDatastoreIoRead[0].value[0].value)) / statInt)
	statDatastoreIoWrite = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'datastore.numberWriteAveraged.average')), "*", vm, interval)
	DatastoreIoWrite = (float(sum(statDatastoreIoWrite[0].value[0].value)) / statInt)

	# Datastore Average Latency
	statDatastoreLatRead = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'datastore.totalReadLatency.average')), "*", vm, interval)
	DatastoreLatRead = (float(sum(statDatastoreLatRead[0].value[0].value)) / statInt)
	statDatastoreLatWrite = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'datastore.totalWriteLatency.average')), "*", vm, interval)
	DatastoreLatWrite = (float(sum(statDatastoreLatWrite[0].value[0].value)) / statInt)

	# Network usage (Tx/Rx)
	statNetworkTx = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'net.transmitted.average')), "", vm, interval)
	networkTx = (float(sum(statNetworkTx[0].value[0].value) * 8/ 1024) / statInt)
	statNetworkRx = BuildQuery(content, vchtime, (StatCheck(perf_dict, 'net.received.average')), "", vm, interval)
	networkRx = (float(sum(statNetworkRx[0].value[0].value) * 8/ 1024) / statInt)

	vminfo = ApLiveVmInfo()
	vminfo.serverName = summary.config.name
	vminfo.description = summary.config.annotation
	vminfo.guest = summary.config.guestFullName
	if vm.rootSnapshot:
		vminfo.snapshotStaus = 'Snapshots present'
	else:
		vminfo.snapshotStaus = 'No Snapshots'
	vminfo.vmxPath = summary.config.vmPathName
	vminfo.vDisks = disk_list
	vminfo.lDisks = diskinfo_print_list
	vminfo.nics = network_list
	vminfo.ipaddr = "{}".format(vm.guest.ipAddress)
	vminfo.limits = "CPU: {}, Memory: {}".format(vmcpulimit, vmmemlimit)
	vminfo.reservations = "CPU: {}, Memory: {}".format(vmcpures, vmmemres)
	vminfo.numOfvCpu = summary.config.numCpu
	vminfo.cpuReady = "Average {:.1f} %, Maximum {:.1f} %".format( (cpuReady / 20000 * 100),
												((float(max(statCpuReady[0].value[0].value)) / 20000 * 100)) )
	vminfo.cpuUsage = "{:.0f} %".format(cpuUsage)
	vminfo.memory = "{} MB ({:.1f} GB".format( summary.config.memorySizeMB, (float(summary.config.memorySizeMB) / 1024))
	vminfo.memoryShared = "{:.0f} %, {:.0f} MB".format( ((memoryShared / summary.config.memorySizeMB) * 100),  memoryShared)
	vminfo.memoryBallon = "{:.0f} %, {:.0f} MB".format( ((memoryBallon / summary.config.memorySizeMB) * 100),  memoryBallon)
	vminfo.memorySwapped = "{:.0f} %, {:.0f} MB".format( ((memorySwapped / summary.config.memorySizeMB) * 100),  memorySwapped)
	vminfo.memoryAcitve = "{:.0f} %, {:.0f} MB".format( ((memoryAcitve / summary.config.memorySizeMB) * 100),  memoryAcitve)
	vminfo.datastoreAvgIo = "Read: {:.0f} IOPS, Write: {:.0f} IOPS".format(DatastoreIoRead, DatastoreIoWrite)
	vminfo.datastoreAvgLatency = "Read: {:.0f} ms, Write: {:.0f} ms".format(DatastoreLatRead, DatastoreLatWrite)
	vminfo.overallNetworkUage = "Transmitted {:.3f} Mbps, Received {:.3f} Mbps".format(networkTx, networkRx)
	vminfo.hostName = "{}".format(summary.runtime.host.name)
	vminfo.hostCpuDetail = "Processor Sockets: {}, Core per Socket {}".format(
		 summary.runtime.host.summary.hardware.numCpuPkgs,
		 (summary.runtime.host.summary.hardware.numCpuCores / summary.runtime.host.summary.hardware.numCpuPkgs) )
	vminfo.hostCpuType = "{}".format(summary.runtime.host.summary.hardware.cpuModel)
	vminfo.hostCpuUsage = "Used: {} Mhz, Total: {} Mhz".format(
		summary.runtime.host.summary.quickStats.overallCpuUsage,
		(summary.runtime.host.summary.hardware.cpuMhz * summary.runtime.host.summary.hardware.numCpuCores))
	vminfo.hostMemoryUsage = "Used: {:.0f} GB, Total: {:.0f} GB".format(
		(float(summary.runtime.host.summary.quickStats.overallMemoryUsage) / 1024),
		(float(summary.runtime.host.summary.hardware.memorySize) / 1024 / 1024 / 1024))

	return vminfo


def GetDisplayVmInfo(vminfo):
	info_list = []				# list for vm info
	#info_list.append("{:<32}{:2}{}".format('Server Name',':', vminfo.serverName))
	info_list.append("Sever Name".ljust(32) + ": " +"{}".format(vminfo.serverName))
	info_list.append("Description".ljust(32) + ": " +"{}".format(vminfo.description))
	info_list.append("Guest".ljust(32) + ": " +"{}".format(vminfo.guest))
	info_list.append("Snapshot Status".ljust(32) + ": " +"{}".format(vminfo.snapshotStaus))
	info_list.append("VM .vmx Path".ljust(32) + ": " +"{}".format(vminfo.vmxPath))
	
	info_list.append("Virtual Disks".ljust(32) + ": " +"{}".format(vminfo.vDisks[0]))
	if len(vminfo.vDisks) > 1:
		vminfo.vDisks.pop(0)
		for vd_info in vminfo.vDisks:
			info_list.append("".ljust(32) + "  " +"{}".format(vd_info))
	
	info_list.append("Logical Drive".ljust(32) + ": " +"{}".format(vminfo.lDisks[0]))
	if len(vminfo.lDisks) > 1:
		vminfo.lDisks.pop(0)
		for drive_info in vminfo.lDisks:
			info_list.append("".ljust(32) + "  " +"{}".format(drive_info))

	info_list.append("Virtual NIC(s)".ljust(32) + ": " +"{}".format(vminfo.nics[0]))
	if len(vminfo.nics) > 1:
		vminfo.nics.pop(0)
		for nic_info in vminfo.nics:
			info_list.append("".ljust(32) + "  " +"{}".format(nic_info))

	info_list.append("[VM] IP Address".ljust(32) + ": " +"{}".format(vminfo.ipaddr))
	info_list.append("[VM] Limits".ljust(32) + ": " +"{}".format(vminfo.limits))
	info_list.append("[VM] Memory".ljust(32) + ": " +"{}".format(vminfo.memory))
	info_list.append("[VM] Memory Shared".ljust(32) + ": " +"{}".format(vminfo.memoryShared))
	info_list.append("[VM] Memory Balloon".ljust(32) + ": " +"{}".format(vminfo.memoryBalloon))
	info_list.append("[VM] Memory Swapped".ljust(32) + ": " +"{}".format(vminfo.memorySwapped))
	info_list.append("[VM] Memory Active".ljust(32) + ": " +"{}".format(vminfo.memoryActive))
	info_list.append("[VM] Datastore Average IO".ljust(32) + ": " +"{}".format(vminfo.datastoreAvgIo))
	info_list.append("[VM] Datastore Average Latency".ljust(32) + ": " +"{}".format(vminfo.datastoreAvgLatency))
	info_list.append("[VM] Overall Network Usage".ljust(32) + ": " +"{}".format(vminfo.overallNetworkUage))
	info_list.append("[Host] Name".ljust(32) + ": " +"{}".format(vminfo.hostName))
	info_list.append("[Host] CPU Detail".ljust(32) + ": " +"{}".format(vminfo.hostCpuDetail))
	info_list.append("[Host] CPU Type".ljust(32) + ": " +"{}".format(vminfo.hostCpuType))
	info_list.append("[Host] CPU Usage".ljust(32) + ": " +"{}".format(vminfo.hostCpuUsage))
	info_list.append("[Host] Memory Usage".ljust(32) + ": " +"{}".format(vminfo.hostMemoryUsage))

	return info_list


# counterId에 따른 performance metrics를 구한다.
def BuildQuery(content, vchtime, counterId, instance, vm, interval):
	perfManager = content.perfManager
	metricId = vim.PerformanceManager.MetricId(counterId=counterId, instance=instance)
	if interval <= 0: interval = 1
	startTime = vchtime - timedelta(minutes=(interval + 1))
	endTime = vchtime - timedelta(minutes=1)
	querySpec = vim.PerformanceManager.QuerySpec(intervalId=20, entity=vm, metricId=[metricId], startTime=startTime,
							endTime=endTime)
	perfResults = perfManager.QueryPerf(querySpec=[querySpec])
	if perfResults:
		return perfResults
	else:
		print('ERROR: Performance results empty.  TIP: Check time drift on source and vCenter server')
		print('Troubleshooting info:')
		print('vCenter/host date and time: {}'.format(vchtime))
		print('Start perf counter time   :  {}'.format(startTime))
		print('End perf counter time     :  {}'.format(endTime))
		print(query)
		exit()


# content: ServiceInstance.content
# viewtype: containerview func의 type parameter
# props: property의 stirng list
# specType: PropertySpec의 대상 type
def GetProperties(content, viewType, props, specType ):
	'''
	specific properties를 갖고 있는 관리 객체(managed object)를 찾아, 객체 참조와 specific property set(name,value)를
	갖는 객체를 return한다.
	'''
	# create containerview(starting point object, type, recursive)
	# viewType: container에 담으려는 managed object type
	containerView = content.viewManager.CreateContainerView(content.rootFolder, viewType, recursive=True)

	# TraversalSpec(name, path, selectSet, skip, type)
	# view : managed object list
	tSpec = vmodl.query.PropertyCollector.TraversalSpec(name="tSpec", path= 'view', skip=False, type=vim.view.ContainerView)
	# TraversalSpec의 path와 type을 이용하여 object들 filtering
	oSpec = vmodl.query.PropertyCollector.ObjectSpec(obj=containerView, selectSet=[tSpec], skip=False)
	# 수집할 property 설정
	# PropertySpec(all, pathSet, type): pathSet:Specifies which managed object properties are retrieved
	pSpec = vmodl.query.PropertyCollector.PropertySpec(all=False, pathSet=props, type=specType )
	filterSpec = vmodl.query.PropertyCollector.FilterSpec(objectSet= [oSpec], propSet=[pSpec])
	# maxObjects #
	options = vmodl.query.PropertyCollector.RetrieveOptions()
	totalProps = []
	retProps = content.propertyCollector.RetrievePropertiesEx(specSet=[filterSpec], options=options)
	totalProps += retProps.objects 		# property set을 가진 managed object list

	# 가져올 데이터가 더 있을 경우,
	while retProps.token:
		retProps = content.propertyCollector.ContinueRetrievePropertiesEx(token=retProps.token)
		totalProps += retProps.objects

	containerView.Destroy()
	#GetProperties Output
	gpOutput = []
	for eachProp in totalProps:
		propDic = {}
		for prop in eachProp.propSet:
			propDic[prop.name] = prop.val
		propDic['moref'] = eachProp.obj
		gpOutput.append(propDic)

	return gpOutput

# counter_name이 perf_dict에 있는 지 check 
def StatCheck(perf_dict, counter_name):
	counter_key = perf_dict[counter_name]
	return counter_key

# content: content property in ServiceInstance
# return: {counter_full_name: couterid } ex) cpu.usage.average: 6
def GetPerfDict(content):
	# Get all the performance counters
	perf_dict = {}
	perfList = content.perfManager.perfCounter
	for counter in perfList:
		counter_full = "{}.{}.{}".format(counter.groupInfo.key, counter.nameInfo.key, counter.rollupType)
		perf_dict[counter_full] = counter.key

	return perf_dict

# get moref from object set filtered by property
def GetMoFromFilteredObjByProps(props, vmanme):
	for prop in props:
		if vmanme in prop['moref'].name:
			return prop['moref']
	return None

def main():
	pmb.setupManagedObject()
	content = pmb.si.content
	
	# Get all the performance counters
	perf_dict = GetPerfDict(content)

	prop_list = ['runtime.powerState', 'name']
	props = GetProperties(content, [vim.VirtualMachine], prop_list, vim.VirtualMachine)

	moref = GetMoFromFilteredObjByProps(props, 'kerpdb')
	
	vchtime = pmb.si.CurrentTime()

	vminfo = None
	if moref != None:
		vminfo = GetVmInfo(moref, content, vchtime, 1, perf_dict)

	vminfo_list = GetDisplayVmInfo(vminfo)

	for info in vminfo_list:
		print(info)



if __name__ == '__main__':
	main()