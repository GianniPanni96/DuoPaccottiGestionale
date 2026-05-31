"""Canvas matplotlib embeddabile in PySide6 per la tab Analisi."""

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure


class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=5.0, height=3.2, dpi=100):
        self.figure = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.figure)
        self.setParent(parent)
        self.axes = self.figure.add_subplot(111)

    def reset_axes(self):
        self.figure.clear()
        self.axes = self.figure.add_subplot(111)
        return self.axes

    def draw_empty(self, message="Nessun dato per il periodo selezionato"):
        ax = self.reset_axes()
        ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes,
                color="#888888")
        ax.set_xticks([])
        ax.set_yticks([])
        self.figure.tight_layout()
        self.draw()
