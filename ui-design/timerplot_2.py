'''
	interpolation
'''

import sys, pytz, time, gc
from datetime import datetime, timedelta
from dateutil.rrule import MINUTELY

from PyQt5.QtWidgets import QWidget, QSizePolicy, QVBoxLayout
from PyQt5.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot, QThread, QTimer
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.axes._axes import Axes
import matplotlib.dates as mdt
import matplotlib.ticker as ticker

from pyVmomi import vim

import pymonbase as pmb
import mvariables as mvars

#from pympler import tracker

# 초기 Axes의 tick의 location, format을 설정 
def initAxes(axes, ylim=100):
	seoul = pytz.timezone('Asia/Seoul')
	now = datetime.now(pytz.UTC)
	delta = timedelta(minutes=30)

	axes.set_xlim([now - delta, now])
	axes.set_ylim([0, ylim])

	xlocator = mdt.AutoDateLocator(interval_multiples=True)
	xlocator.intervald[MINUTELY] = [10]

	ylocator = ticker.MaxNLocator(nbins='5')

	xformatter = mdt.DateFormatter('%H:%M', tz=seoul)
	axes.xaxis.set_major_locator(xlocator)
	axes.xaxis.set_major_formatter(xformatter)

	axes.yaxis.set_major_locator(ylocator)
	
	return axes

# 하나의 Performance Metrics를 그리기 위한 canvas
class SimpleMplCanvas(FigureCanvas):
	def __init__(self,parent=None):
		#self.fig = Figure(figsize=(3,2), tight_layout=True)
		self.fig = Figure()
		self.axes = self.fig.add_subplot(111)

		super().__init__(self.fig)
		self.setParent(parent)
		self.setMaximumHeight(400)
		self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
		self.updateGeometry()


	@pyqtSlot(Axes)
	def update_plot(self, axes):
		self.axes = axes
		self.draw()

	@pyqtSlot(Axes)
	def clear_plot(self, axes):
		self.axes = axes
		self.axes.clear()


# Axes를 받아 plot후 singnal을 이용하여 emit(Axes)
# 이 plotter는 thread상에서 실행됨.
# numCPU: VM cpu usage percentage를 구하기 위해 vCPU 개수로 나눔.
# category: cpu, mem, disk data값에 대해 특별히 단위를 변경하기 위함. 예) disk: KB -> MB
class SimplePlotter(QObject): 			
	
	return_fig = pyqtSignal(Axes, name='return_fig')
	def __init__(self, axes, entity_moid, cid, numCPU=None, category=None):
		super().__init__()
		self.axes = initAxes(axes)
		self.cid = cid
		self.numCPU = numCPU
		self.category = category
		self._timer = QTimer(self)			# parent를 self를 설정해야 slot인 start(), stop()이 작동함. 2018. 04. 04 -- 중요!!!
		self._timer.setInterval(20000)
		self._timer.timeout.connect(self.replot)
		
		# monitoring 하려는 coutner id를 metric id로 변환 
		metricId = pmb.getMetricIdFromCounterId(cid)
		self.entityMetricInfo = pmb.EntityPerfInfo(entity_moid, [ metricId ])

		#self.memory_tracker = tracker.SummaryTracker()

	@pyqtSlot()
	def startplot(self):
	

		xdata = list(self.entityMetricInfo.timestamp)

		ydata = None
		if self.numCPU != None and self.category == 'cpu':
			ydata = [ (value / self.numCPU ) for value in self.entityMetricInfo.counterIds_Metrics[self.cid] ]

		elif self.category == 'mem': # KB -> GB
			ydata = [ (value / 1000000 ) for value in self.entityMetricInfo.counterIds_Metrics[self.cid] ]

		else:	# disk: KB -> MB
			ydata = [ (value / 1000 ) for value in self.entityMetricInfo.counterIds_Metrics[self.cid] ]
		

		# interpolate data
		mpl_ts_new, metrics = pmb.interploateMetrics(xdata, ydata)
		
		self.axes.set_xlim( [min(mpl_ts_new), max(mpl_ts_new)])
		self.axes.set_ylim( [0, max(metrics)])

		line, = self.axes.plot(mpl_ts_new, metrics, color='gray', linewidth=1)
		# 갱신된 데이터르 canvas에 그림
		self.return_fig.emit(self.axes)

		xdata, ydata = None, None
		gc.collect()

	# entity_moid: entity managed object reference id
	# cid:  counter id to monitoring, 오직 1개,  ex) 1, 2
	@pyqtSlot()
	def replot(self):
	
		self.entityMetricInfo.getMetrics()
		
		xdata = list(self.entityMetricInfo.timestamp)

		ydata = None
		if self.numCPU != None and self.category == 'cpu':
			ydata = [ (value / self.numCPU ) for value in self.entityMetricInfo.counterIds_Metrics[self.cid] ]

		elif self.category == 'mem': # KB -> GB
			ydata = [ (value / 1000000 ) for value in self.entityMetricInfo.counterIds_Metrics[self.cid] ]

		else:	# disk: KB -> MB
			ydata = [ (value / 1000 ) for value in self.entityMetricInfo.counterIds_Metrics[self.cid] ]
		

		# interpolate data
		mpl_ts_new, metrics = pmb.interploateMetrics(xdata, ydata)
		
		self.axes.set_xlim( [min(mpl_ts_new), max(mpl_ts_new)])
		self.axes.set_ylim( [0, max(metrics)])

		line, = self.axes.plot(mpl_ts_new, metrics, color='gray', linewidth=1)
		# 갱신된 데이터르 canvas에 그림
		self.return_fig.emit(self.axes)

		#self.memory_tracker.print_diff()
		xdata, ydata = None, None

		gc.collect()


	@pyqtSlot()
	def start(self):
		self._timer.start()
	
	@pyqtSlot()
	def stop(self):
		self._timer.stop()

class PlotterThread(QThread):
	def run(self):
		self.exec()
	