import sys, threading, gc
from PyQt5.QtWidgets import QApplication, QWidget, QListView, QMainWindow, QHBoxLayout
from PyQt5.QtGui import QStandardItem, QStandardItemModel
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QModelIndex, Qt, QObject, QStringListModel, QTimer
from toolbox2 import Ui_Form

from matplotlib.axes._axes import Axes
from pyVmomi import vim

import pymonbase as pmb
import timerplot_0 as tim

class MyWindow(QObject):   # QWidget-> QObejct로 변경. UI thread와 logic thread 분리? 2018.04.04
	"""docstring for MyMainWindow"""
	send_fig = pyqtSignal(Axes, vim.VirtualMachine, int, str, name='send_fig' )
	stop_plotter = pyqtSignal(name='start_plotter')
	
	def __init__(self, parent=None):
		super().__init__()
		self.widget = QWidget()
		self.ui = Ui_Form()
		self.ui.setupUi(self.widget)
		self.prevViewPage = None

		self.canvas = tim.SimpleMplCanvas()
		
		self.thread = tim.PlotterThread()

		pmb.setupManagedObject()

		self.serverList = ['kerp', 'kerpdb', 'gw00', 'GW2','epdmapp']
		self.networkList = ['HeadUTM','Head02UTM', 'BalanUTM', 'KaUTM' ]

		serverModel = QStringListModel()
		serverModel.setStringList(self.serverList)
		self.ui.serverListView.setModel(serverModel)

		networkModel = QStringListModel()
		networkModel.setStringList(self.networkList)
		self.ui.networkListView.setModel(networkModel)
				
		self.ui.verticalLayout.setAlignment(Qt.AlignTop)
		self.ui.serverListView.setVisible(False)
		self.ui.networkListView.setVisible(False)
		
		# listview category info added, select page
		self.ui.serverListView.clicked.connect(lambda index: self.selectPage(index, 'server'))
		self.ui.networkListView.clicked.connect(lambda index: self.selectPage(index, 'network'))
	
		# plotting
		#self.ui.serverListView.clicked.connect(self.update_plot)

		self.ui.dashboardButton.clicked.connect(self.itemToggle)
		self.ui.serverButton.clicked.connect(self.itemToggle)
		self.ui.networkButton.clicked.connect(self.itemToggle)

		self.ui.stackedWidget.setCurrentIndex(0)		# first page in start

		self.widget.show()
	

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
		
	# index: index of listview
	def selectPage(self, index, category):
	
		serverName = index.data()				# host name in domain
	

		# listview의 각 항목을 click 할 때마다, canvas clear, plotter stop. thread 실행 중지 
		if self.prevViewPage != serverName:
			if self.thread.isRunning():
				print('thread is running...')
				self.stop_plotter.emit()
				self.plotter.return_fig.disconnect(self.canvas.update_plot)
				self.canvas.axes.clear()
				self.thread.terminate()
				self.thread.wait()
				


				
		# staked widget의 child widget, 즉 Page를 찾는다.
		stackedWidget = self.ui.stackedWidget.findChild(QObject, serverName, Qt.FindDirectChildrenOnly)
		if stackedWidget:
			self.ui.stackedWidget.setCurrentWidget(stackedWidget)

			# Page내 graph를 포함하고 있는 layout를 찾는다.
			topLayout = stackedWidget.findChild(QHBoxLayout, serverName+'TopLayout')

			# server name (clicked item in ListView)을 이용하여 widget name을 생성
			nameList = [ serverName + '_' + mtype for mtype in [ 'cpu', 'memory', 'disk'] ]

			#canvases = [ tim.SimpleMplCanvas(self) for _ in range(3)]

			
			if topLayout != None:
				if topLayout.count() == 0:
					'''
					# canvas에 이름을 붙여 topLayout에  추가 
					for name, canvas in zip(nameList, canvases):
						canvas.setObjectName(name)
						topLayout.addWidget(canvas)
					'''
					topLayout.addWidget(self.canvas)

				cids = [1, 32, 125]		# cpu.usage.none, mem.swapout.none, disk udage
				moid = pmb.getManagedObjectRefId(serverName) 
				self.plotter = tim.SimplePlotter(self.canvas.axes, moid, 1)
				
				print('ing...')
				
				self.plotter.moveToThread(self.thread)
				self.thread.started.connect(self.plotter.start)
				self.thread.started.connect(self.plotter.replot)
				
				# 별도 signal을 생성해서 listview index(item) 변경 시, plotting 중지 후 plotter object delete. 2018. 04.04
				self.stop_plotter.connect(self.plotter.stop)
				self.stop_plotter.connect(self.plotter.deleteLater)

				self.plotter.return_fig.connect(self.canvas.update_plot)
				self.thread.start()
				
			'''
			
			

			for cid, canvas, thread in zip(cids, canvases, threads):
				plotter = tim.SimplePlotter(canvas.axes, moid, cid)
				plotter.moveToThread(thread)
				self.start_worker.connect(plotter.start)
				plotter.return_fig.connect(canvas.update_plot)
				thread.start()
				self.start_worker.emit()
			'''


		else:
			self.ui.stackedWidget.setCurrentIndex(0)

		self.prevViewPage = serverName
		

if __name__ == "__main__":

    app = QApplication(sys.argv)
    
    window = MyWindow()
    #window.show()
    
    sys.exit(app.exec_())