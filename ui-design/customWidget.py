from PyQt5.QtWidgets import QListView
from PyQt5.QtCore import QSize

class MyList(QListView):
	def __init__(self, parent=None):
		super().__init__(parent)

	def sizeHint(self):
		rowCount= self.model().rowCount()
		rowHeight = self.sizeHintForRow(0)
		viewHeight =  (rowCount+2)*rowHeight if rowCount else self.height()
		return QSize(self.width(), viewHeight )
