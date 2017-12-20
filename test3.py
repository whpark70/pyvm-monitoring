import sys

#from datetime import datetime, timedelta
#from dateutil.rrule import MINUTELY

#import matplotlib.dates as mdt
#import matplotlib.ticker as ticker
#from matplotlib.figure import Figure
#from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from PyQt5.QtWidgets import QMainWindow, QWidget, QPushButton, QApplication, QGridLayout, QVBoxLayout, QHBoxLayout, QSizePolicy
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot

from matplotlib.axes._subplots import Axes
#from pyVmomi import vim

import pymonbase as pmb
import pymonplot as pmp

from pyVmomi import vim


class MyWindow(QWidget):

	# axes, vm, metric ids
	send_fig = pyqtSignal(Axes, vim.VirtualMachine, list, name='send_fig' )
	
	def __init__(self):
		super().__init__()

		pmb.setupManagedObject()
		self.server_moids = pmb.makeManagedObjectIdFromConfig()
		self.server_names = [ pmb.getVmNameFromMoRefId(moid) for moid in self.server_moids ]

		self.main_widget = QWidget(self)
		#self.canvas = pmp.ServerFigureCanvas(parent=self.main_widget,vm_name=self.server_names[0])
		self.canvases = [ pmp.ServerFigureCanvas(parent=self.main_widget,vm_name=vm_name) for vm_name in self.server_names]

		self.setupUI()
		self.show()

		self.startButton.clicked.connect(self.updatePlot)
		
		self.plotter1 = None
		self.plotter2 = None
		self.thread1 = None
		self.thread2 = None


	def setupUI(self):
		self.setGeometry(200,200,800,400)
		layout = QHBoxLayout()
		leftlayout = QHBoxLayout()
		rightlayout = QVBoxLayout()

		self.startButton = QPushButton("start", self)
		self.endButton = QPushButton("end", self)
		leftlayout.addWidget(self.canvases[0])
		leftlayout.addWidget(self.canvases[1])
		rightlayout.addWidget(self.startButton)
		rightlayout.addWidget(self.endButton)

		layout.addLayout(leftlayout)
		layout.addLayout(rightlayout)

		self.setLayout(layout)

	def updatePlot(self):

		entity_moids = pmb.makeManagedObjectIdFromConfig()
		metricIds = pmb.makeMetricIdFromConfig(option='kerpdb')
			
		self.plotters = [ pmp.Plotter() for _ in self.server_names ]
		self.threads =  [ QThread() for _ in self.server_names ]

		plotters_threads = zip(self.plotters, self.threads, entity_moids)

		# signal emit를 하는 순서가 대단히 중요. 관련 thread start 후 곧바로. otherwise emit을 찾지 못함.
		for  idx, (plotter, thread, entity_moid) in enumerate( plotters_threads ): 
			self.send_fig.connect(plotter.replot)
			plotter.return_fig.connect(self.canvases[idx].update_plot)

			plotter.moveToThread(thread)
			thread.start()
			self.send_fig.emit(self.canvases[idx].axes, entity_moid, metricIds )
		

def main():
	
	app = QApplication(sys.argv)
	myWindow = MyWindow()
	app.exec_()



if __name__ == '__main__':
	main()