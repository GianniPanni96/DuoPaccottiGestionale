"""Canvas matplotlib embeddabili in PySide6 per la tab Analisi.

``MplCanvas`` e' il canvas generico (un singolo asse) usato per i grafici a
barre. ``InteractivePieCanvas`` disegna un grafico a torta con legenda e un
tooltip che compare al passaggio del mouse su una fetta (stesso
comportamento dei grafici a torta di WillowGestionale).

Lo sfondo delle figure segue la palette dell'app (ruolo ``Window``), cosi'
i grafici si integrano con il resto dei widget invece di mostrare il bianco
di default di matplotlib."""

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from Utils.View_utils import ViewUtils

# Palette per le fette: tinte distinte e leggibili sia su tema chiaro che
# scuro. Si ripete ciclicamente se le categorie superano la sua lunghezza.
PIE_COLORS = [
    "#45b7d1",
    "#7d8cc4",
    "#4ecdc4",
    "#f7b267",
    "#f25f5c",
    "#a1c181",
    "#f79d65",
    "#c77dff",
    "#2e7d57",
    "#e29578",
]


def palette_colors():
    """(background, foreground) dalla QPalette attiva, in formato '#rrggbb'.

    Fallback su bianco/nero se non c'e' ancora una QApplication."""
    app = QApplication.instance()
    if app is None:
        return "#ffffff", "#000000"
    pal = app.palette()
    bg = pal.color(QPalette.ColorRole.Window)
    fg = pal.color(QPalette.ColorRole.WindowText)
    return bg.name(), fg.name()


class MplCanvas(FigureCanvasQTAgg):
    def __init__(self, parent=None, width=5.0, height=3.2, dpi=100):
        self.figure = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.figure)
        self.setParent(parent)
        self.axes = self.figure.add_subplot(111)
        self._apply_theme(self.axes)

    def _apply_theme(self, ax):
        bg, fg = palette_colors()
        self.figure.set_facecolor(bg)
        ax.set_facecolor(bg)
        ax.tick_params(colors=fg)
        for spine in ax.spines.values():
            spine.set_color(fg)
        ax.xaxis.label.set_color(fg)
        ax.yaxis.label.set_color(fg)
        ax.title.set_color(fg)

    def reset_axes(self):
        self.figure.clear()
        self.axes = self.figure.add_subplot(111)
        self._apply_theme(self.axes)
        return self.axes

    def draw_empty(self, message="Nessun dato per il periodo selezionato"):
        ax = self.reset_axes()
        ax.text(0.5, 0.5, message, ha="center", va="center", transform=ax.transAxes,
                color="#888888")
        ax.set_xticks([])
        ax.set_yticks([])
        self.figure.tight_layout()
        self.draw()


class InteractivePieCanvas(FigureCanvasQTAgg):
    """Grafico a torta con legenda e tooltip interattivo.

    Pensato per essere ricreato a ogni refresh: usa ``Figure`` diretta (non
    pyplot), quindi non serve ``plt.close`` — basta rimuoverlo dal layout e
    chiamarne ``deleteLater``."""

    def __init__(self, parent=None, width=4.0, height=3.4, dpi=100):
        self.figure = Figure(figsize=(width, height), dpi=dpi)
        super().__init__(self.figure)
        self.setParent(parent)
        self._motion_cid = None
        bg, _ = palette_colors()
        self.figure.set_facecolor(bg)

    def draw_empty(self, message):
        bg, fg = palette_colors()
        self.figure.clear()
        self.figure.set_facecolor(bg)
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(bg)
        ax.text(0.5, 0.5, message, ha="center", va="center",
                transform=ax.transAxes, color="#888888", fontsize=9)
        ax.set_xticks([])
        ax.set_yticks([])
        self.figure.tight_layout()
        self.draw()

    def draw_pie(self, title, labels, values, value_suffix=" €"):
        """Disegna la torta. ``labels``/``values`` sono allineati e gia'
        filtrati dai valori nulli."""
        if self._motion_cid is not None:
            self.mpl_disconnect(self._motion_cid)
            self._motion_cid = None

        bg, fg = palette_colors()
        self.figure.clear()
        self.figure.set_facecolor(bg)
        ax = self.figure.add_subplot(111)
        ax.set_facecolor(bg)

        total = sum(values)
        if total <= 0 or not labels:
            self.draw_empty(message="Nessuna spesa")
            return

        colors = [PIE_COLORS[i % len(PIE_COLORS)] for i in range(len(values))]
        wedges, _, autotexts = ax.pie(
            values,
            colors=colors,
            startangle=90,
            autopct=lambda pct: f"{pct:.0f}%" if pct >= 5 else "",
            pctdistance=0.72,
            wedgeprops={"linewidth": 1.0, "edgecolor": bg},
        )
        for autotext in autotexts:
            autotext.set_color("white")
            autotext.set_fontsize(8)
            autotext.set_weight("bold")

        ax.axis("equal")
        if title:
            ax.set_title(title, fontsize=10, fontweight="bold", color=fg)
        ax.legend(
            wedges,
            [ViewUtils.split_string_by_length(label, 22) for label in labels],
            loc="center left",
            bbox_to_anchor=(0.98, 0.5),
            frameon=False,
            labelcolor=fg,
            fontsize=8,
        )
        self.figure.subplots_adjust(left=0.02, right=0.60, top=0.88, bottom=0.04)

        annotation = ax.annotate(
            "",
            xy=(0, 0),
            xytext=(12, 12),
            textcoords="offset points",
            bbox=dict(boxstyle="round", fc="#2b2b2b", ec="white", alpha=0.92),
            color="white",
            fontsize=9,
            zorder=10,
        )
        annotation.set_visible(False)
        state = {"index": None}

        def reset_wedges():
            for w in wedges:
                w.set_alpha(1.0)
            state["index"] = None
            annotation.set_visible(False)

        def on_motion(event):
            if event.inaxes != ax:
                if state["index"] is not None:
                    reset_wedges()
                    self.draw_idle()
                return
            for i, wedge in enumerate(wedges):
                contains, _ = wedge.contains(event)
                if contains:
                    if state["index"] == i:
                        return
                    for w in wedges:
                        w.set_alpha(1.0)
                    wedge.set_alpha(0.7)
                    state["index"] = i
                    pct = (values[i] / total) * 100 if total else 0
                    annotation.xy = (event.xdata, event.ydata)
                    annotation.set_text(
                        f"{labels[i]}\n{values[i]:.2f}{value_suffix} ({pct:.1f}%)"
                    )
                    annotation.set_visible(True)
                    self.draw_idle()
                    return
            if state["index"] is not None:
                reset_wedges()
                self.draw_idle()

        self._motion_cid = self.mpl_connect("motion_notify_event", on_motion)
        self.draw()
