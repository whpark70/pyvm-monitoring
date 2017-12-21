from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from matplotlib.axes._subplots import Axes
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import sys
from datetime import datetime, timedelta
import numpy as np
import psutil as ps
import pytz, random, time
import matplotlib.dates as mdt
from collections import deque
from dateutil.rrule import SECONDLY, MINUTELY


class WorkerSignal(QObject):
	return_fig = pyqtSignal(Axes)

class MetricGenerator(object):
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



class MyMplCanvas(FigureCanvas):
	
	def __init__(self, parent=None):
		self.fig = Figure()
		self.axes = self.fig.add_subplot(111)

		FigureCanvas.__init__(self, self.fig)
		self.setParent(parent)

		FigureCanvas.setSizePolicy(self, QSizePolicy.Expanding, QSizePolicy.Expanding)
		FigureCanvas.updateGeometry(self)

	pyqtSlot(Axes)
	def update_plot(self, axes):
		self.axes = axes
		self.draw()

class PlotterRunnable(QRunnable):
	def __init__(self, axes):
		super().__init__()
		self.signals = WorkerSignal()
		self.axes = axes

	@pyqtSlot()
	def run(self): # A slot take no params
				
		xdata = deque(maxlen=300)
		ydata = deque(maxlen=300)

		metric_gen = MetricGenerator()
		for t, y in metric_gen.gen():

			if isinstance(t, list):
				xdata.extend(t)
				ydata.extend(y)
			else:
				xdata.append(t)
				ydata.append(y)
	
			cur_x_min, cur_x_max = self.axes.get_xlim()
		
		
			delta = None
			if isinstance(t, datetime):
				if t > mdt.num2date(cur_x_max):
					delta = timedelta(seconds=20)
					cur_x_min = mdt.num2date(cur_x_min) + delta
					cur_x_max = mdt.num2date(cur_x_max) + delta
					self.axes.set_xlim([cur_x_min, cur_x_max])
	
			else:
				self.axes.set_xlim([min(xdata), max(xdata)])	
	
			locator = mdt.AutoDateLocator(interval_multiples=True)
			locator.intervald[MINUTELY] = [5]

			formatter = mdt.DateFormatter('%H:%M')
			self.axes.xaxis.set_major_locator(locator)
			self.axes.xaxis.set_major_formatter(formatter)

			self.axes.plot(xdata, ydata, 'k')
			self.signals.return_fig.emit(self.axes)



class MainWindow(QMainWindow):
	
	def __init__(self):
		super(MainWindow, self).__init__()

		self.main_widget = QWidget(self)
		self.myplot = [ MyMplCanvas(self.main_widget) for _ in range(2) ]
		self.startButton = QPushButton("start", self)
		self.addButton = QPushButton("add", self)

		self.layout = QGridLayout(self.main_widget)
		self.layout.addWidget(self.startButton)
		self.layout.addWidget(self.addButton)
		self.layout.addWidget(self.myplot[0])
		self.layout.addWidget(self.myplot[1])

		self.setCentralWidget(self.main_widget)

		self.move(500, 500)
		self.show()

		self.startButton.clicked.connect(self.updatePlot)
		self.addButton.clicked.connect(self.addPlot)

		self.threadpools = QThreadPool()

	def updatePlot(self):
		
		for idx, myplot in enumerate(self.myplot):
			worker = PlotterRunnable(self.myplot[idx].axes)
			worker.signals.return_fig.connect(self.myplot[idx].update_plot)
			self.threadpools.start(worker)

	def addPlot(self):
		self.myplot.append(MyMplCanvas(self.main_widget))
		self.layout.addWidget(self.myplot[-1])
		worker = PlotterRunnable(self.myplot[-1].axes)
		worker.signals.return_fig.connect(self.myplot[-1].update_plot)
		self.threadpools.start(worker)


if __name__ == '__main__':
	app = QApplication(sys.argv)
	win = MainWindow()
	sys.exit(app.exec_())

