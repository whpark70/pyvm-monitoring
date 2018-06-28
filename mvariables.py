# Counter id - description
counterId_Desc = { 1:'cpu usage', 125:'disk usage', 82: 'mem swapout' }
# counter id and instance type for vmcollector.py
counterId_instance = {
	12: "",			# 'cpu.ready.summation',
	2: "",			# 'cpu.usage.average',
	33: "",			# 'mem.active.average',
	37: "",			# 'mem.shared.average',
	90: "",			# 'mem.vmmemctl.average',
	70: "",			# 'mem.swapped.average', 
	178: "*",		# 'datastore.numberReadAveraged.average', 
	179: "*",		# 'datastore.numberWriteAveraged.average', 
	182: "*",		# 'datastore.totalReadLatency.average',
	183: "*",		# 'datastore.totalWriteLatency.average',
	149: "",		# 'net.transmitted.average',
	148: ""		#'net.received.average'

}


# plot 시 color: 회색: #808080 
colors = {0:'blue', 1:'#808080', 2: 'green', 3:'black', 4: 'yellow', 5: 'red', 6: 'white'}

# number of cpu per VM
cpus = { 'kerp': 32, 'kerpdb': 32, 'gw00': 32, 'GW2': 32, 'epdmapp': 8 ,'epdmfms': 8, 'bi': 8, 'kerpholdings': 32, 'kerpholdingsDB': 32}