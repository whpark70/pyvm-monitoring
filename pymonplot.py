from datetime import datetime, timedelta
from dateutil.rrule import SECONDLY, MINUTELY
import sys, traceback

from matplotlib.axes._axes import Axes
from matplotlib.figure import Figure
import matplotlib.dates as mdt
import matplotlib.ticker as ticker
import matplotlib.patches as mpatches
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from PyQt5.QtCore import QObject, QRunnable, QSize, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QSizePolicy

from pyVmomi import vim
import pytz
import numpy as np

import pymonbase as pmb
import mvariables as mvars



# 초기 Axes의 tick의 location, format을 설정 
def initAxes(axes, vm_name=None):
	seoul = pytz.timezone('Asia/Seoul')
	now = datetime.now(pytz.UTC)
	delta = timedelta(minutes=30)

	#axes.set_title(vm_name)
	
	axes.set_xlim([now - delta, now])
	axes.set_ylim([0, 20000])

	xlocator = mdt.AutoDateLocator(interval_multiples=True)
	xlocator.intervald[MINUTELY] = [10]

	#ylocator = ticker.MaxNLocator(nbins='5', steps=[1, 5], min_n_ticks=4)
	ylocator = ticker.MaxNLocator(nbins='5')

	xformatter = mdt.DateFormatter('%H:%M', tz=seoul)
	axes.xaxis.set_major_locator(xlocator)
	axes.xaxis.set_major_formatter(xformatter)

	axes.yaxis.set_major_locator(ylocator)
	#axes.grid()

	return axes

def initAxesPercent(axes, vm_name=None):
	axes.set_ylim([0,100])
	y_ticks = [ 0, 20, 40, 60, 80, 100]
	axes.set_yticks(y_ticks)

	return axes

# FigureCanvas: Figure: Server: axes 모두 1:1 대응
class ServerFigureCanvas(FigureCanvas):
	"""docstring for ServerFigureCanvas"""
	def __init__(self, parent=None, vm_name=None):
		self.vm_name = vm_name
		self.fig = Figure(figsize=(4,3))
		self.axes = self.fig.add_subplot(111)

		super().__init__(self.fig)
		self.setParent(parent)
		self.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
		self.updateGeometry()
		
		self.axes = initAxes(self.axes, vm_name)

	@pyqtSlot(Axes)
	def update_plot(self, axes):
		self.axes = axes
		self.axes.legend()
		self.draw()


class ServerFigureCanvas2(FigureCanvas):
	"""docstring for ServerFigureCanvas"""
	def __init__(self, parent=None):
		self.fig = Figure(figsize=(5,3), tight_layout=True)
		#self.fig = Figure(tight_layout=True)
		self.axes = self.fig.add_subplot(111)
		
		super().__init__(self.fig)
		self.setParent(parent)
		self.policy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
		#self.policy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
		self.policy.setHeightForWidth(True)
		self.setSizePolicy(self.policy)
		self.updateGeometry()
		#self.resize(QSize(100,50))
		#self.resize(self.sizeHint())

		self.axes = initAxes(self.axes)

	@pyqtSlot(Axes)
	def update_plot(self, axes):
		self.axes = axes
		self.axes.legend()
		self.draw()

	@pyqtSlot(Axes)
	def clear_plot(self, axes):
		self.axes = axes
		self.axes.clear()


class Plotter(QObject):
	return_fig = pyqtSignal(Axes)

	@pyqtSlot(Axes, vim.VirtualMachine, list )
	def replot(self, axes, entity_moid, metricIds): # A slot take no params
				
		#xdata = None
		entityMetricInfo = pmb.EntityPerfInfo(entity_moid, metricIds)
		cids = list(entityMetricInfo.counterIds_Metrics.keys())
		# counter id의 description을 가져온다.
		cids_desc = [ mvars.counterId_Desc[i] for i in cids]
		# color에 따른 legend를 생성한다. 
		color_patch = [mpatches.Patch(color=mvars.colors[i], label=str(cids_desc[i])) for i in range(len(cids_desc))]

		for t, _ in entityMetricInfo.generateMetrics():
			
			xdata = list(entityMetricInfo.timestamp)
			# get current xlim from axes
			cur_x_min, cur_x_max = axes.get_xlim()
					
			delta = None
			# adjust xlim
			if isinstance(t, datetime):
				if t > mdt.num2date(cur_x_max):
					delta = timedelta(seconds=20)			# realtime Interval in vSphere 6
					cur_x_min = mdt.num2date(cur_x_min) + delta
					cur_x_max = mdt.num2date(cur_x_max) + delta
					axes.set_xlim([cur_x_min, cur_x_max])
	
				else:
					axes.set_xlim([min(xdata), max(xdata)])	
			
			vmname = pmb.getVmNameFromMoRefId(entity_moid)	
			axes.set_title(vmname)
			axes.set_ylabel('Kbps')

			color_idx =0
			for cid, ydata in entityMetricInfo.counterIds_Metrics.items():
			
				cur_y_min, cur_y_max = axes.get_ylim()	
				y_max = max(ydata)

				if y_max > cur_y_max:
					axes.set_ylim([0, y_max])
				
				line, = axes.plot(xdata, list(ydata), color=mvars.colors[color_idx], linewidth=1)
				color_idx = color_idx + 1 								# differnt color according to counter id

			handles, _ = axes.get_legend_handles_labels()
			axes.legend(handles=color_patch)
			self.return_fig.emit(axes)

# --- QRuannable 사용시 
class WorkerSignals(QObject):
	finished = pyqtSignal()
	error = pyqtSignal(tuple)
	result = pyqtSignal(object)
	progress = pyqtSignal(int)
	
	return_figure = pyqtSignal(Axes)

class Worker(QRunnable):
	"""docstring for Worker"""
	def __init__(self, fn, *args, **kwargs):
		super(Worker, self).__init__()
		self.fn = fn
		self.args = args
		self.kwargs = kwargs
		self.signals = WorkerSignals()

		kwargs['progress_callback'] = self.signals.progress

	@pyqtSlot()
	def run(self):
		try:
			result = self.fn(*self.args, **self.kwargs)
		except:
			traceback.print_exc()
			exctype, value = sys.exc_info()[:2]
			self.signals.error.emit((exctype, value, traceback.format_exc()))
		else:
			self.signals.result.emit(result)
		finally:
			self.signals.finished.emit()



class RunnablePlotter(QRunnable):
	
	def __init__(self, axes, entity_moid, metricIds):
		super(RunnablePlotter,self).__init__()
		self.signals = WorkerSignals()
		self.axes = axes
		self.entity_moid = entity_moid
		self.entityMetricInfo = pmb.EntityPerfInfo(entity_moid, metricIds)
		self.cids = list(self.entityMetricInfo.counterIds_Metrics.keys())
		# counter id의 description을 가져온다.
		self.cids_desc = [ mvars.counterId_Desc[i] for i in self.cids]
		# color에 따른 legend를 생성한다. 
		self.color_patch = [mpatches.Patch(color=mvars.colors[i], label=str(self.cids_desc[i])) for i in range(len(self.cids_desc))]

	@pyqtSlot()
	def run(self): # A slot take no params
				
		for t, _ in self.entityMetricInfo.generateMetrics():
			
			xdata = list(self.entityMetricInfo.timestamp)
			# get current xlim from axes
			cur_x_min, cur_x_max = self.axes.get_xlim()
					
			delta = None
			# adjust xlim
			if isinstance(t, datetime):
				if t > mdt.num2date(cur_x_max):
					delta = timedelta(seconds=20)			# realtime Interval in vSphere 6
					cur_x_min = mdt.num2date(cur_x_min) + delta
					cur_x_max = mdt.num2date(cur_x_max) + delta
					self.axes.set_xlim([cur_x_min, cur_x_max])
	
				else:
					self.axes.set_xlim([min(xdata), max(xdata)])	
			
			vmname = pmb.getVmNameFromMoRefId(self.entity_moid)	
			self.axes.set_title(vmname)
			self.axes.set_ylabel('Kbps')

			color_idx =0
			for cid, ydata in self.entityMetricInfo.counterIds_Metrics.items():
			
				cur_y_min, cur_y_max = self.axes.get_ylim()	
				y_max = max(ydata)

				if y_max > cur_y_max:
					self.axes.set_ylim([0, y_max])

				line, = self.axes.plot(xdata, list(ydata), color=mvars.colors[color_idx], linewidth=1)
				color_idx = color_idx + 1 								# differnt color according to counter id

			handles, _ = self.axes.get_legend_handles_labels()
			self.axes.legend(handles=self.color_patch)
			self.signals.return_figure.emit(self.axes)

class RunnablePlotterTwinx(QRunnable):
	
	def __init__(self, canvas, entity_moid, metricIds):
		super(RunnablePlotterTwinx,self).__init__()
		self.signals = WorkerSignals()
		self.canvas = canvas
		self.axes = canvas.axes
		self.entity_moid = entity_moid
		self.entityMetricInfo = pmb.EntityPerfInfo(entity_moid, metricIds)
		self.cids = list(self.entityMetricInfo.counterIds_Metrics.keys())
		# counter id의 description을 가져온다.
		self.cids_desc = [ mvars.counterId_Desc[i] for i in self.cids]
		# color에 따른 legend를 생성한다. 
		self.color_patch = [mpatches.Patch(color=mvars.colors[i], label=str(self.cids_desc[i])) for i in range(len(self.cids_desc))]

	@pyqtSlot()
	def run(self): # A slot take no params
		
		# counter id: 125
		axes2 = self.axes.twinx()
		axes2 = initAxes(axes2)

		for t, _ in self.entityMetricInfo.generateMetrics():
			
			xdata = list(self.entityMetricInfo.timestamp)
			# get current xlim from axes
			cur_x_min, cur_x_max = self.axes.get_xlim()
					
			delta = None
			# adjust xlim
			if isinstance(t, datetime):
				if t > mdt.num2date(cur_x_max):
					delta = timedelta(seconds=20)			# realtime Interval in vSphere 6
					cur_x_min = mdt.num2date(cur_x_min) + delta
					cur_x_max = mdt.num2date(cur_x_max) + delta
					self.axes.set_xlim([cur_x_min, cur_x_max])
	
				else:
					self.axes.set_xlim([min(xdata), max(xdata)])	
			
			vmname = pmb.getVmNameFromMoRefId(self.entity_moid)	
			self.axes.set_title(vmname)
			#self.axes.set_ylabel('Kbps')

			# display하는 Performance Counter는 2개로 제한 : 1, 125
			# cpu usage 비율(%)를 나타내기 위한 처리: 2017.12. 27
			# counter id: 1
			vcpu_num = mvars.cpus[vmname]
			ydata = list(map(lambda m: m/vcpu_num, self.entityMetricInfo.counterIds_Metrics[1]))
		
			self.axes = initAxesPercent(self.axes)
			line = self.axes.plot(xdata, ydata, color=mvars.colors[0], linewidth=0.8)
			self.axes.tick_params(axis='x', labelsize=9)
			self.axes.tick_params(axis='y',colors=mvars.colors[0], labelsize=9, direction='in') 	# 2017.12.27:  tick label font & color
			self.axes.grid(linewidth=0.2)
			
			# counter id: 125						
			#cur_y_min, cur_y_max = axes2.get_ylim()	
			ydata = list(self.entityMetricInfo.counterIds_Metrics[125])
			y_max = max(ydata)
			axes2.set_ylim([0, y_max])
						
			line2, = axes2.plot(xdata, ydata, color=mvars.colors[1], linewidth=0.8)
			axes2.tick_params('y',colors=mvars.colors[1], labelsize=9, direction='in' )
			#axes2.yaxis.set_major_locator(ticker.MaxNLocator(5))
			axes2.grid(linewidth=0.2)
				
			handles, _ = self.axes.get_legend_handles_labels()
			self.axes.legend(handles=self.color_patch)
			self.signals.return_figure.emit(self.axes)
