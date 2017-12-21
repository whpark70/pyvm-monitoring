import sys

from PyQt5.QtWidgets import QMainWindow, QWidget, QPushButton, QApplication, QGridLayout, QVBoxLayout, QHBoxLayout, QSizePolicy
from PyQt5.QtCore import QThread, pyqtSignal, pyqtSlot, QRunnable, QThreadPool

from matplotlib.axes._subplots import Axes

import pymonbase as pmb
from pymonplot import Worker, ServerFigureCanvas2, RunnablePlotter

from pyVmomi import vim

# 정상적인 프로그램 종료 테스트

class MyWindow(QWidget):

	# axes, vm, metric ids
	send_fig = pyqtSignal(Axes, name='send_fig' )
		
	def __init__(self):
		super().__init__()

		pmb.setupManagedObject()
		self.server_moids = pmb.makeManagedObjectIdFromConfig()
		self.server_names = [ pmb.getVmNameFromMoRefId(moid) for moid in self.server_moids ]

		self.main_widget = QWidget(self)
		self.canvases = [ ServerFigureCanvas2(parent=self.main_widget) for vm_name in self.server_names]
		self.threadpool = QThreadPool()

		self.setupUI()
		self.show()

		self.startButton.clicked.connect(self.startPlot)
		self.stopButton.clicked.connect(self.stopPlot)

	def setupUI(self):
		self.setGeometry(200,200,800,400)
		layout = QHBoxLayout()
		leftlayout = QHBoxLayout()
		rightlayout = QVBoxLayout()

		self.startButton = QPushButton("start", self)
		self.stopButton = QPushButton("stop", self)
		leftlayout.addWidget(self.canvases[0])
		leftlayout.addWidget(self.canvases[1])
		rightlayout.addWidget(self.startButton)
		rightlayout.addWidget(self.stopButton)

		layout.addLayout(leftlayout)
		layout.addLayout(rightlayout)

		self.setLayout(layout)

	def startPlot(self):
		entity_moids = pmb.makeManagedObjectIdFromConfig()
		metricIds = pmb.makeMetricIdFromConfig(option='kerpdb')

		for idx, entity_moid in enumerate(entity_moids):
			worker = RunnablePlotter(self.canvases[idx].axes, entity_moid, metricIds)
			worker.signals.return_figure.connect(self.canvases[idx].update_plot)
			self.threadpool.start(worker)

	def stopPlot(self):
		pass


def main():
	
	app = QApplication(sys.argv)
	myWindow = MyWindow()
	app.exec_()



if __name__ == '__main__':
	main()