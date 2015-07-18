# encoding: UTF-8
from __future__ import print_function
from __future__ import unicode_literals
from builtins import range
import traceback
import os.path

from PyQt4 import QtGui, QtCore, uic

# TODO: Mover a un fichero de utilidades
def filedir(*path): return os.path.realpath(os.path.join(os.path.dirname(__file__), *path))


class MainForm(QtGui.QWidget):
    areas = []
    toolBoxs = []
    tab = 0
    ui = None
    areasTab = None
    formTab = None

    def load(self):
        self.ui = uic.loadUi(filedir('forms/mainform.ui'), self)
        self.areasTab = self.ui.areasTab
        self.areasTab.removeTab(0) #Borramos tab de ejemplo.
        self.formTab = self.ui.formTab
        self.formTab.setTabsClosable(True)
        self.connect(self.formTab, QtCore.SIGNAL('tabCloseRequested(int)'), self.closeFormTab)
        self.formTab.removeTab(0)

    def closeFormTab(self, numero):
        #print"Cerrando pestaña número %d " % numero
        self.formTab.removeTab(numero)

    def addFormTab(self, widget):
        #print"Añadiendo Form a pestaña"
        self.formTab.addTab(widget, widget.windowTitle())
        self.formTab.setCurrentWidget(widget)



    def addAreaTab(self, widget, module):
        self.areasTab.addTab(widget, module.areaid)


    def addModuleInTab(self, module):
        #print "Procesando %s " % module.name
        #button = QtGui.QCommandLinkButton(module.description)
        #button.setText(module.description)
        #button.clicked.connect(module.run)
        vl = QtGui.QWidget()
        vBLayout = QtGui.QWidget()
        vBLayout.layout = QtGui.QVBoxLayout() #layout de cada módulo.
        vBLayout.layout.setSpacing(0)
        vBLayout.layout.setContentsMargins(1, 2, 2, 0)

        vBLayout.setLayout(vBLayout.layout)
        #Creamos pestañas de areas y un vBLayout por cada módulo. Despues ahí metemos los actions de cada módulo
        if self.areas.count(module.areaid):
            i = 0
            for i in range(self.tab):
                if self.areas[i] == module.areaid:
                    moduleToolBox = self.toolBoxs[i]
                    #print"Cargando en pestaña %d" % i
                    moduleToolBox.addItem(vBLayout, module.description)

        else:
            #print "Nueva Pestaña"
            vl.layout = QtGui.QVBoxLayout() #layout de la pestaña
            moduleToolBox = QtGui.QToolBox(self)#toolbox de cada módulo
            moduleToolBox.addItem(vBLayout, module.description)

            self.areas.append(module.areaid)
            self.toolBoxs.append(moduleToolBox)
            self.tab = self.tab + 1
            vl.setLayout(vl.layout)
            vl.layout.addWidget(moduleToolBox)
            self.addAreaTab(vl, module)
        try:
            module.run(vBLayout.layout)
        except Exception:
            print("ERROR al procesar modulo %s:" % module.name)
            print(traceback.format_exc(), "---")

mainWindow = MainForm()


