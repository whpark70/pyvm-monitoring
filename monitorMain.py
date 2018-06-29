'''
interpolattion 적용
'''

import sys, threading, gc
from PyQt5.QtWidgets import QApplication, QWidget, QListView, QMainWindow, QHBoxLayout, QTextBrowser, QScrollArea, QTabWidget
from PyQt5.QtGui import QStandardItem, QStandardItemModel
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QModelIndex, Qt, QObject, QStringListModel, QTimer, QVariant
from mainUI import Ui_Form

from matplotlib.axes._axes import Axes
from pyVmomi import vim

import pymonbase as pmb
import timerplot as tim
import mvariables as mvars
from vmcollector import  GetVmInfoMetrics, GetDisplayVmInfo_rjust

import utm_db as utm
import mplUtmWidget as muw
#from pympler import tracker

class MyWindow(QObject):   # QWidget-> QObejct로 변경. UI thread와 logic thread 분리? 2018.04.04
	"""docstring for MyMainWindow"""
	send_fig = pyqtSignal(Axes, vim.VirtualMachine, int, str, name='send_fig' )
	stop_plotter = pyqtSignal(name='start_plotter')
	
	def __init__(self, parent=None):
		super().__init__()
		self.widget = QWidget()
		self.ui = Ui_Form()
		self.db_engine = None
		self.ifname_list = ['eth'+str(i) for i in range(1, 11)]			# utm interface name list
		self.ui.setupUi(self.widget)
		self.prevViewPage = None 	# view list의 item index, 화면전환 시 사용.

		self.cpuCanvas, self.memCanvas, self.diskCanvas = [tim.SimpleMplCanvas() for _ in range(3)]
		self.cpuThread, self.memThread, self.diskThread = tim.PlotterThread(), tim.PlotterThread(), tim.PlotterThread()

		pmb.setupManagedObject()

		self.serverList = pmb.getVmList()
		self.networkList = ['HeadUTM']

		serverModel = QStringListModel()
		serverModel.setStringList(self.serverList)
		serverItemCount = serverModel.rowCount()			# model item count
		self.ui.serverListView.setModel(serverModel)

		networkModel = QStringListModel()
		networkModel.setStringList(self.networkList)
		self.ui.networkListView.setModel(networkModel)
				
		self.ui.verticalLayout.setAlignment(Qt.AlignTop)
		self.ui.serverListView.setVisible(False)
		self.ui.networkListView.setVisible(False)
		
		# listview category info added, select page
		self.ui.serverListView.clicked.connect(lambda index: self.selectServerPage(index, 'server'))
		self.ui.networkListView.clicked.connect(lambda index: self.selectNetworkPage(index, 'network'))

		self.ui.HeadUTM_tab.currentChanged.connect(self.changeTab)
	
		self.ui.dashboardButton.clicked.connect(self.itemToggle)
		self.ui.serverButton.clicked.connect(self.itemToggle)
		self.ui.networkButton.clicked.connect(self.itemToggle)

		self.ui.stackedWidget.setCurrentIndex(0)		# first page in start

		self.widget.show()
	

	# when click toolbox button in left side, collapse/expand view
	def itemToggle(self):
		btn = self.sender()
		if btn.objectName() == 'dashboardButton':
			self.ui.serverListView.setVisible(False)
			self.ui.networkListView.setVisible(False)
			self.ui.stackedWidget.setCurrentIndex(0)		# stacked index 0: dashboard page

		elif btn.objectName() == 'serverButton':		# page name: serverSummary
			self.ui.serverListView.setVisible(True)
			self.ui.networkListView.setVisible(False)
			stackedWidget = self.ui.stackedWidget.findChild(QObject, 'serverSummary', Qt.FindDirectChildrenOnly)
			self.ui.stackedWidget.setCurrentWidget(stackedWidget)

		elif btn.objectName() == 'networkButton':		# page name: networkSummary
			self.ui.serverListView.setVisible(False)
			self.ui.networkListView.setVisible(True)
			stackedWidget = self.ui.stackedWidget.findChild(QObject, 'networkSummary', Qt.FindDirectChildrenOnly)
			self.ui.stackedWidget.setCurrentWidget(stackedWidget)

		else:
			self.ui.serverListView.setVisible(False)
			self.ui.networkListView.setVisible(False)
			self.ui.stackedWidget.setCurrentIndex(0)
		
	# tab widget에서 tab click 시 slot,  other event: selectNetworkPage
	def changeTab(self, i):
		
		signal_source = self.sender()		# ex: HeadUTM_tab
		tabName = signal_source.tabText(i)
		tabPage = signal_source.widget(i)	# ex: current tab widget: HeadUTM_day
		
		deviceName, c_interval = tabPage.objectName().split('_')	
		scrollArea = tabPage.findChild(QScrollArea,'scrollArea_'+ c_interval) 	# find scrollArea for each interval
		
		sampling_mean_interval= None
		if tabName == '일간':
			sampling_mean_interval = '10T'
		elif tabName == '주간':
			sampling_mean_interval = '30T'
		elif tabName == '월간':
			sampling_mean_interval = '30T'

		if_usage_info_list = utm.get_ifusage_dafaframes(self.db_engine, self.ifname_list, c_interval=c_interval, sampling_mean_interval=sampling_mean_interval)
		plotter = muw.CanvasWidget(if_usage_info_list)
		scrollArea.setWidget(plotter)	




	# index: index of listview
	def selectServerPage(self, index, category):
		'''
		Main StackedWidget에서 Server Name이용하여 해당 child widget을 찾는다.
		Top Layout을 찾아 20초 간격으로 실시간 갱신 되는 graph를 위해 cpu, memory, disk 개의 canvas를 추가하고 
		thread를 연결한다.
		'''
	
		serverName = index.data()				# host name in domain

		# listview의 각 항목을 click 할 때마다, canvas clear, plotter stop. thread 실행 중지 
		if self.prevViewPage != serverName:
			#  emit Plotter stop signal
			self.stop_plotter.emit()
			
			if self.cpuThread.isRunning():
				self.cpuCanvas.axes.clear()
				self.cpuThread.terminate()
				self.cpuThread.wait()

			if self.memThread.isRunning():
				self.memCanvas.axes.clear()
				self.memThread.terminate()
				self.memThread.wait()

			if self.diskThread.isRunning():
				self.diskCanvas.axes.clear()
				self.diskThread.terminate()
				self.diskThread.wait()
				
			
		# staked widget의 child widget, 즉 Page를 찾는다.
		stackedWidget = self.ui.stackedWidget.findChild(QObject, serverName, Qt.FindDirectChildrenOnly)
		if stackedWidget:
			self.ui.stackedWidget.setCurrentWidget(stackedWidget)

			# Page내 graph를 포함하고 있는 layout를 찾는다.
			topLayout = stackedWidget.findChild(QHBoxLayout, serverName+'TopLayout')
			
			if topLayout != None:
				if topLayout.count() == 0:
					
					# 각 canvas를  topLayout에  추가 

					topLayout.addWidget(self.cpuCanvas)
					topLayout.addWidget(self.memCanvas)
					topLayout.addWidget(self.diskCanvas)


				self.cpuCanvas.axes.set_title('CPU Usage (%)')
				#self.cpuCanvas.fig.set_facecolor('lightblue')
				#self.cpuCanvas.fig.set_edgecolor('green')
				self.cpuCanvas.fig.subplots_adjust(left=0.1, right=0.95)

				self.memCanvas.axes.set_title('Atcive Memory (GB)')
				#self.memCanvas.fig.set_facecolor('lightgreen')
				self.memCanvas.fig.subplots_adjust(left=0.1, right=0.95)
				
				self.diskCanvas.axes.set_title('Disk Usage (MBps)')
				#self.diskCanvas.fig.set_facecolor('#EDC4F9')
				self.diskCanvas.fig.subplots_adjust(left=0.125, right=0.99)

				moid = pmb.getManagedObjectRefId(serverName) 
				numCPU = mvars.cpus[serverName]
				# 해당 Canvas를 연결해서 각 Plotter를 생성: cid: 2, 32, 125
				self.cpuPlotter = tim.SimplePlotter(self.cpuCanvas.axes, moid, 2, numCPU=numCPU, category='cpu')
				self.memPlotter = tim.SimplePlotter(self.memCanvas.axes, moid, 32, category='mem')
				self.diskPlotter = tim.SimplePlotter(self.diskCanvas.axes, moid, 125, category='disk')
				
				# 각 Plotter를 해당 Thread로 이동 
				self.cpuPlotter.moveToThread(self.cpuThread)
				self.memPlotter.moveToThread(self.memThread)
				self.diskPlotter.moveToThread(self.diskThread)

				# 해당 thread에 signal 연결  
				self.cpuThread.started.connect(self.cpuPlotter.start)		# tiemr 시작, 20초 후 replot 수행 
				self.cpuThread.started.connect(self.cpuPlotter.startplot) 		# thread시작과 동시에 지난 30분간 성능 데이터 수집 및 plotting
				self.memThread.started.connect(self.memPlotter.start)
				self.memThread.started.connect(self.memPlotter.startplot)
				self.diskThread.started.connect(self.diskPlotter.start)
				self.diskThread.started.connect(self.diskPlotter.startplot)

				
				# 별도 signal을 생성해서 listview index(item) 변경 시, plotting 중지 후 plotter object delete. 2018. 04.04
				self.stop_plotter.connect(self.cpuPlotter.stop)
				self.stop_plotter.connect(self.cpuPlotter.deleteLater)
				self.stop_plotter.connect(self.memPlotter.stop)
				self.stop_plotter.connect(self.memPlotter.deleteLater)
				self.stop_plotter.connect(self.diskPlotter.stop)
				self.stop_plotter.connect(self.diskPlotter.deleteLater)
				
				# plotter update signal을 해당 canvas update plot에 연결 
				self.cpuPlotter.return_fig.connect(self.cpuCanvas.update_plot)
				self.memPlotter.return_fig.connect(self.memCanvas.update_plot)
				self.diskPlotter.return_fig.connect(self.diskCanvas.update_plot)
				
				# 각 thread start
				self.cpuThread.start()
				self.memThread.start()
				self.diskThread.start()

			
			# 화면 하단에 해당 서버의 구성정보를 표시하기 위한 텍스트 브라우저 검색: 디자이너에서 고정폭 폰트(monospaced font) 설정 (Courier, 가독성)
			# 확인 필요할때:fixedFont = QFontDatabase.systemFont(QFontDatabase.FixedFont)
			# from PyQt5.QtGui import QFont
			# font = QFont('Monospace')
			# font.setStyleHint(QFont.TypeWriter)
			# font.setPointSize(12)
			
			
			confStatus = stackedWidget.findChild(QTextBrowser, serverName+'Info')
		
			content = pmb.si.content
			vchtime = pmb.si.CurrentTime()
			vminfo = GetVmInfoMetrics(moid, content, vchtime, 1)
			vminfo_list = GetDisplayVmInfo_rjust(vminfo)	

			for info in vminfo_list:
				confStatus.append(info)

			vminfo, vminfo_list = None, None
			gc.collect()
			
		else:
			self.ui.stackedWidget.setCurrentIndex(0)

		self.prevViewPage = serverName

	def selectNetworkPage(self, index, category):
		'''
		Network device name을 이용하여 stackedWidget 내에 해당 widget을  찾는다.
		'''
		deviceName = index.data()	# network device name

		if self.db_engine == None:
			self.db_engine = utm.create_db_engine()

		# staked widget의 child widget, 즉 Page를 찾는다.
		stackedWidget = self.ui.stackedWidget.findChild(QObject, deviceName, Qt.FindDirectChildrenOnly)
		if stackedWidget:
			self.ui.stackedWidget.setCurrentWidget(stackedWidget)

		# find Tab Widget under stackedWidget
		tabWidgetName = deviceName + '_tab'
		tabWidget = stackedWidget.findChild(QTabWidget, tabWidgetName)
		tabWidget.setCurrentIndex(0)
		
		# for daily
		tabPage = tabWidget.widget(0)	# ex: current tab widget: HeadUTM_day
		c_interval = tabPage.objectName().split('_')[1]	
		scrollArea = tabPage.findChild(QScrollArea,'scrollArea_'+ c_interval) 
		if_usage_info_list = utm.get_ifusage_dafaframes(self.db_engine, self.ifname_list, c_interval=c_interval, sampling_mean_interval='10T')
		plotter = muw.CanvasWidget(if_usage_info_list)
		scrollArea.setWidget(plotter)	
		

def main():

    app = QApplication(sys.argv)
    
    window = MyWindow()
    #window.show()

    sys.exit(app.exec_())

 
if __name__ == "__main__":
 	main()