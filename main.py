import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
import svgpathtools as svgpt
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QWidget, QFileDialog, QMainWindow, QHBoxLayout, QVBoxLayout, QFileDialog,
                             QSlider, QPushButton, QLabel, QCheckBox, QSpinBox)
import copy
import sys


class Canvas(FigureCanvasQTAgg):
    def __init__(self):
        super().__init__()
        self.ax = self.figure.add_axes([0,0,1,1])
        self.ax.axis('off')
        self.ax.set_aspect('equal')
        self.plot_nothing_loaded()
        
    def plot_nothing_loaded(self):
        self.ax.scatter([-0.5,0.5],[0.4,0.4])
        x=np.linspace(-0.75,0.75,50)
        y=0.4*abs(x**3)-0.1
        self.ax.plot(x,y)
        r=np.linspace(0,2*np.pi,100)
        self.ax.plot(np.cos(r),np.sin(r),'C0')
        
    def clear(self):
        self.ax.clear()
        self.ax.axis('off')
        self.ax.set_aspect('equal')

    def plot_path(self,path,**kwargs):
        if len(path)>0:
            for segment in path:
                if type(segment)==svgpt.CubicBezier:
                    interps=[segment.point(i) for i in np.linspace(0,1,20)]
                    self.ax.plot(np.real(interps),-np.imag(interps),'-',**kwargs)
                else:
                    self.ax.plot([np.real(segment.start),np.real(segment.end)],
                                 [-np.imag(segment.start),-np.imag(segment.end)],
                                 '-',**kwargs)
            self.draw()
        else: # there is no file loaded
            self.plot_nothing_loaded()

    def plot_arrows(self,path,**kwargs):
        if len(path)>0:
            self.ax.scatter([np.real(path[0].start)],[-np.imag(path[0].start)],c='k',s=10)
            # get direction of path initial vector
            segment = path[0]
            if type(segment)==svgpt.CubicBezier:
                diff = segment.point(0.001)-segment.point(0)
            else:
                diff = segment.end-segment.start
            diff = diff/np.abs(diff)
            # draw an arrow starting from the intial point in the direction of diff
            xmin, xmax, ymin, ymax = self.ax.axis()
            arrow_length = 0.03*(abs(xmax-xmin)+abs(ymax-ymin))
            arrow_head_size = 0.5*arrow_length
            self.ax.arrow(np.real(path[0].start),-np.imag(path[0].start),
                          arrow_length*diff.real,-arrow_length*diff.imag,
                          head_width=arrow_head_size,
                          head_length=arrow_head_size,
                          length_includes_head=True,
                          **kwargs)
            self.draw()


class PathGroup:
    def __init__(self):
        self.paths = []
        self.attributes = []
        self.svg_attributes = []
        self.npaths = 0
        self.path1idx = 0
        self.path2idx = 0
        self.path1start = 0
        self.path1reverse = False
        self.nbefore = 0
        self.ninter = 0
        self.nafter = 0
        self.path1_unshifted = []
        self.path1 = []
        self.path2 = []
        self.all_paths = []
    
    def update_paths(self):
        if len(self.paths)>1:
            self.path1_unshifted = self.paths[self.path1idx]
            self.path1 = copy.deepcopy(self.path1_unshifted)
            self.path1 = self.shift_path(self.path1,self.path1start)
            if self.path1reverse:
                self.path1 = self.reverse_path(self.path1)
            self.path2 = self.paths[self.path2idx]
            if self.nbefore+self.ninter+self.nafter>0:
                try:
                    self.all_paths = self.calculate_interpolated_paths()
                except ValueError:
                    self.all_paths = [self.path1,self.path2]            
            else:
                self.all_paths=[self.path1,self.path2]
            
    def load_file(self,filename):
        self.paths, self.attributes, self.svg_attributes = svgpt.svg2paths2(filename)
        self.npaths = len(self.paths)
        self.path1idx = 0
        self.path1_unshifted = self.paths[self.path1idx]
        self.path1 = self.path1_unshifted
        self.path2 = self.paths[self.path2idx]

    @staticmethod
    def reverse_segment(segment):
        start_temp=segment.start
        segment.start=segment.end
        segment.end=start_temp
        if type(segment)==svgpt.CubicBezier:
            control1_temp=segment.control1
            segment.control1=segment.control2
            segment.control2=control1_temp
        return segment
    
    @staticmethod
    def reverse_path(path):
        path_list = [PathGroup.reverse_segment(segment) for segment in path]
        path_list.reverse()
        path = svgpt.Path(*path_list)
        return path

    @staticmethod
    def shift_path(path,rotatepoints):
        return svgpt.Path(*path[rotatepoints:],*path[:rotatepoints])

    def path_colors(self,y1=0.25,y2=0.75):
        total_curves=self.nbefore+self.ninter+self.nafter+2
        ys = np.zeros(total_curves)
        for i in range(total_curves):
            if i<self.nbefore:
                ys[i]=y1*i/(self.nbefore)
            elif i<=(self.nbefore+self.ninter+1):
                ys[i]= y1 + (i-self.nbefore)/(self.ninter+1)*(y2-y1)
            else:
                ys[i]= y2 + (1-y2)*(i-self.nbefore-self.ninter-1)/(self.nafter)
        colors=[plt.cm.rainbow(y) for y in ys]
        return colors
    
    def guess_alignment(self,points=200):
        if len(self.path1)==len(self.path2):
            results=np.zeros([len(self.path1),2])
            for i in range(len(self.path1)):
                for j in [0,1]:
                    path1shifted = copy.deepcopy(self.path1_unshifted)
                    if j:
                        path1shifted = self.reverse_path(self.shift_path(path1shifted,i))
                    else:
                        path1shifted = self.shift_path(path1shifted,i)
                    interp1=[path1shifted.point(i) for i in np.linspace(0,1,points)]
                    interp2=[self.path2.point(i) for i in np.linspace(0,1,points)]
                    results[i,j]=np.sum(abs(np.array(interp1)-np.array(interp2)))
            guessed_rotation,guessed_reverse = np.unravel_index(results.argmin(), results.shape)
            return guessed_rotation,guessed_reverse
        else:
            raise ValueError('Paths are not the same length')
    
    def calculate_interpolated_paths(self):
        if len(self.path1)==len(self.path2):
            total_curves=self.nbefore+self.ninter+self.nafter+2
            pathparams=np.zeros([len(self.path1),4,total_curves],dtype=complex)
            for j,path in [(self.nbefore,self.path1),(-self.nafter-1,self.path2)]:
                for i,segment in enumerate(path):
                        pathparams[i,0,j] = segment.start
                        pathparams[i,1,j] = segment.end
                        if type(segment)==svgpt.CubicBezier:
                            pathparams[i,2,j] = segment.control1
                            pathparams[i,3,j] = segment.control2

            for i in range(total_curves):
                pathparams[:,:,i] = ((-i+self.ninter+self.nbefore+1)/(self.ninter+1) * pathparams[:,:,self.nbefore] 
                                     + (i-self.nbefore)/(self.ninter+1) * pathparams[:,:,-self.nafter-1])
            all_paths = []
            for j in range(total_curves):
                segments=[]
                for i in range(len(self.path1)):
                    if ((pathparams[i,2,j]==0) and (pathparams[i,3,j]==0)):
                        segments.append(svgpt.Line(start=pathparams[i,0,j],end=pathparams[i,1,j]))
                    else:
                        segments.append(svgpt.CubicBezier(start=pathparams[i,0,j],end=pathparams[i,1,j],
                                                          control1=pathparams[i,2,j],control2=pathparams[i,3,j]))
                all_paths.append(svgpt.Path(*segments))
            return all_paths
        else:
            raise ValueError('Paths are not the same length')
    
    def plot_curves(self,canvas):
        canvas.clear()
        colors = self.path_colors()
        for i,path in enumerate(self.all_paths):
            canvas.plot_path(path,color=colors[i])
        canvas.plot_arrows(self.path1,color=colors[self.nbefore])
        canvas.plot_arrows(self.path2,color=colors[self.nbefore+self.ninter+1])


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Pattern auto-grading")

        self.pathgroup = PathGroup()

        file_select_button = QPushButton("Select file")
        file_select_button.clicked.connect(self.file_select_button_was_clicked)
        
        #slider for path 1 index
        self.path1idx_slider = QSlider(Qt.Orientation.Horizontal)
        self.path1idx_slider.setMinimum(0)
        self.path1idx_slider.setMaximum(0)
        self.path1idx_slider.setValue(0)
        self.path1idx_slider.setTickPosition(QSlider.TicksBelow)
        self.path1idx_slider.setTickInterval(1)
        self.path1idx_slider.valueChanged.connect(self.path1idx_slider_changed)
        self.path1idx_label = QLabel("Path 1 index: 1")

        #slider for path 2 index
        self.path2idx_slider = QSlider(Qt.Orientation.Horizontal)
        self.path2idx_slider.setMinimum(0)
        self.path2idx_slider.setMaximum(0)
        self.path2idx_slider.setValue(0)
        self.path2idx_slider.setTickPosition(QSlider.TicksBelow)
        self.path2idx_slider.setTickInterval(1)
        self.path2idx_slider.valueChanged.connect(self.path2idx_slider_changed)
        self.path2idx_label = QLabel("Path 2 index: 1")

        #slider for path start index
        self.pathstart_slider = QSlider(Qt.Orientation.Horizontal)
        self.pathstart_slider.setMinimum(0)
        self.pathstart_slider.setMaximum(0)
        self.pathstart_slider.setValue(0)
        self.pathstart_slider.setTickPosition(QSlider.TicksBelow)
        self.pathstart_slider.setTickInterval(1)
        self.pathstart_slider.valueChanged.connect(self.pathstart_slider_changed)
        self.pathstart_label = QLabel("Path start index: 1")

        self.reverse_checkbox = QCheckBox("Reverse path 1")
        self.reverse_checkbox.stateChanged.connect(self.reverse_checkbox_changed)

        # integer input for number of curves before
        self.nbefore_input = QSpinBox()
        self.nbefore_input.setRange(0,100)
        self.nbefore_input.setValue(0)
        self.nbefore_input.valueChanged.connect(self.nbefore_input_changed)
        # label for integer input for number of curves before
        self.nbefore_label = QLabel("Number of curves before: ")
        
        # integer input for number of curves in between
        self.ninter_input = QSpinBox()
        self.ninter_input.setRange(0,100)
        self.ninter_input.setValue(0)
        self.ninter_input.valueChanged.connect(self.ninter_input_changed)
        # label for integer input for number of curves in between
        self.ninter_label = QLabel("Number of curves in between: ")

        # integer input for number of curves after
        self.nafter_input = QSpinBox()
        self.nafter_input.setRange(0,100)
        self.nafter_input.setValue(0)
        self.nafter_input.valueChanged.connect(self.nafter_input_changed)
        # label for integer input for number of curves after
        self.nafter_label = QLabel("Number of curves after: ")

        # canvas for plotting
        self.svg_canvas = Canvas()
        self.plot_message = QLabel("No file loaded")
        self.plot_message.setAlignment(Qt.AlignCenter)
        
        # button for automatically guessing path alignment
        self.guess_button = QPushButton("Auto align paths")
        self.guess_button.clicked.connect(self.guess_button_clicked)

        # button for saving the finished svg
        self.save_button = QPushButton("Save")
        # TODO make this function
        #self.save_button.clicked.connect(self.save_button_clicked)

        # layout
        control_layout = QVBoxLayout()

        control_layout.addWidget(file_select_button)

        path1idx_layout = QVBoxLayout()
        path1idx_layout.addWidget(self.path1idx_label)
        path1idx_layout.addWidget(self.path1idx_slider)
        control_layout.addLayout(path1idx_layout)

        path2idx_layout = QVBoxLayout()
        path2idx_layout.addWidget(self.path2idx_label)
        path2idx_layout.addWidget(self.path2idx_slider)
        control_layout.addLayout(path2idx_layout)
        
        control_layout.addWidget(self.guess_button)

        manual_align_layout = QVBoxLayout()
        manual_align_layout.addWidget(QLabel("Manual alignment"))

        pathstart_layout = QVBoxLayout()
        pathstart_layout.addWidget(self.pathstart_label)
        pathstart_layout.addWidget(self.pathstart_slider)
        manual_align_layout.addLayout(pathstart_layout)
        manual_align_layout.addWidget(self.reverse_checkbox)
        control_layout.addLayout(manual_align_layout)

        nbefore_layout = QVBoxLayout()
        nbefore_layout.addWidget(self.nbefore_label)
        nbefore_layout.addWidget(self.nbefore_input)
        control_layout.addLayout(nbefore_layout)

        ninter_layout = QVBoxLayout()
        ninter_layout.addWidget(self.ninter_label)
        ninter_layout.addWidget(self.ninter_input)
        control_layout.addLayout(ninter_layout)

        nafter_layout = QVBoxLayout()
        nafter_layout.addWidget(self.nafter_label)
        nafter_layout.addWidget(self.nafter_input)
        control_layout.addLayout(nafter_layout)

        control_layout.addWidget(self.save_button)
        
        plot_layout = QVBoxLayout()
        plot_layout.addWidget(self.svg_canvas)
        plot_layout.addWidget(self.plot_message)

        main_layout = QHBoxLayout()
        main_layout.addLayout(control_layout)
        main_layout.addLayout(plot_layout)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

    def file_select_button_was_clicked(self):
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        file_dialog.setNameFilter("SVG files (*.svg)")
        if file_dialog.exec_():
            filename = file_dialog.selectedFiles()
            self.pathgroup.load_file(filename[0])
            self.initialise_sliders(self.pathgroup)
            if self.pathgroup.npaths > 1:
                self.path2idx_slider.setValue(1)
                self.path2idx_label.setText("Path 2 index: 2")
                self.pathgroup.path2idx = 1
            self.pathgroup.update_paths()
            self.pathgroup.plot_curves(self.svg_canvas)
            self.plot_message.setText("File loaded: "+filename[0])
    
    def initialise_sliders(self,pathgroup):
        self.path1idx_slider.setMaximum(pathgroup.npaths-1)
        self.path2idx_slider.setMaximum(pathgroup.npaths-1)
        self.pathstart_slider.setMaximum(len(pathgroup.path1)-1)
        self.path1idx_slider.setValue(0)
        self.path2idx_slider.setValue(0)
        self.pathstart_slider.setValue(0)
        self.nbefore_input.setValue(0)
        self.ninter_input.setValue(0)
        self.nafter_input.setValue(0)

    def path1idx_slider_changed(self):
        self.pathgroup.path1idx = self.path1idx_slider.value()
        self.pathgroup.update_paths()
        self.pathstart_slider.setMaximum(len(self.pathgroup.path1)-1)
        self.pathgroup.plot_curves(self.svg_canvas)
        self.path1idx_label.setText("Path 1 index: "+str(self.pathgroup.path1idx+1))

    def path2idx_slider_changed(self):
        self.pathgroup.path2idx = self.path2idx_slider.value()
        self.pathgroup.update_paths()
        self.pathgroup.plot_curves(self.svg_canvas)
        self.path2idx_label.setText("Path 2 index: "+str(self.pathgroup.path2idx+1))

    def pathstart_slider_changed(self):
        self.pathgroup.path1start = self.pathstart_slider.value()
        self.pathgroup.update_paths()
        self.pathgroup.plot_curves(self.svg_canvas)
        self.pathstart_label.setText("Path 1 start: "+str(self.pathgroup.path1start+1))

    def reverse_checkbox_changed(self):
        self.pathgroup.path1reverse = self.reverse_checkbox.isChecked()
        self.pathgroup.update_paths()
        self.pathgroup.plot_curves(self.svg_canvas)

    def nbefore_input_changed(self):
        self.pathgroup.nbefore = self.nbefore_input.value()
        self.pathgroup.update_paths()
        self.pathgroup.plot_curves(self.svg_canvas)

    def ninter_input_changed(self):
        self.pathgroup.ninter = self.ninter_input.value()
        self.pathgroup.update_paths()
        self.pathgroup.plot_curves(self.svg_canvas)
    
    def nafter_input_changed(self):
        self.pathgroup.nafter = self.nafter_input.value()
        self.pathgroup.update_paths()
        self.pathgroup.plot_curves(self.svg_canvas)

    def guess_button_clicked(self):
        try:
            shift,reverse = self.pathgroup.guess_alignment()
            self.pathgroup.path1start = shift
            self.pathgroup.path1reverse = reverse
            self.pathstart_slider.setValue(shift)
            self.pathstart_label.setText("Path 1 start: "+str(self.pathgroup.path1start+1))
            self.reverse_checkbox.setChecked(reverse)
            self.pathgroup.update_paths()
            self.pathgroup.plot_curves(self.svg_canvas)
        except ValueError:
            self.plot_message.setText("Auto align error: paths do not have the same length")

# main window for pyqt5 gui
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec_()