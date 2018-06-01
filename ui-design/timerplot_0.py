import sys, pytz, time
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
		self.fig = Figure(figsize=(3,2), tight_layout=True)
		self.axes = self.fig.add_subplot(111)

		super().__init__(self.fig)
		self.setParent(parent)
		self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
		self.updateGeometry()
		#self.axes = initAxes(self.axes)

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
class SimplePlotter(QObject): 			
	
	return_fig = pyqtSignal(Axes, name='return_fig')
	def __init__(self, axes, entity_moid, cid):
		super().__init__()
		self.axes = initAxes(axes)
		self.cid = cid
		self._timer = QTimer(self)			# parent를 self를 설정해야 slot인 start(), stop()이 작동함. 2018. 04. 04 -- 중요!!!
		self._timer.setInterval(20000)
		self._timer.timeout.connect(self.replot)
		
		# monitoring 하려는 coutner id를 metric id로 변환 
		metricId = pmb.getMetricIdFromCounterId(cid)
		self.entityMetricInfo = pmb.EntityPerfInfo(entity_moid, [ metricId ])

	# entity_moid: entity managed object reference id
	# cid:  counter id to monitoring, 오직 1개,  ex) 1, 2

	#@pyqtSlot(Axes, vim.VirtualMachine, int)
	@pyqtSlot()
	def replot(self):

		print('ss')		
		self.entityMetricInfo.getMetrics()
		
		xdata = list(self.entityMetricInfo.timestamp)
		self.axes.set_xlim( [min(xdata), max(xdata)])

		ydata = list(self.entityMetricInfo.counterIds_Metrics[self.cid])
		self.axes.set_ylim( [0, max(ydata)])

		line, = self.axes.plot(xdata, ydata, color='gray', linewidth=1)
		# 갱신된 데이터르 canvas에 그림
		self.return_fig.emit(self.axes)

	@pyqtSlot()
	def start(self):
		self._timer.start()
		print('timer started...')
	
	@pyqtSlot()
	def stop(self):
		self._timer.stop()
		print('timer stopped...')


class PlotterThread(QThread):
	def run(self):
		self.exec()
	