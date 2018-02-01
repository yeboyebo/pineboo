# -*- coding: utf-8 -*-

from builtins import object
import re
import os.path
from PyQt5 import QtCore, QtWidgets


import traceback
import pineboolib
from pineboolib import decorators
from pineboolib.utils import filedir

import weakref
from PyQt5.Qt import qWarning, QDateEdit

from pineboolib.fllegacy.FLUtil import FLUtil
from pineboolib.fllegacy.AQObjects import AQSql

AQUtil = FLUtil()  # A falta de crear AQUtil, usamos la versión anterior
util = FLUtil()  # <- para cuando QS erróneo usa util sin definirla

Insert = 0
Edit = 1
Del = 2
Browse = 3


class File(object):

    @classmethod
    def exists(cls, name):
        return os.path.isfile(name)


class FileDialog(QtWidgets.QFileDialog):

    # def __init__(self):
    #    super(FileDialog, self).__init__()

    def getOpenFileName(*args):
        obj = None
        parent = QtWidgets.QApplication.activeModalWidget()
        if len(args) == 2:
            obj = QtWidgets.QFileDialog.getOpenFileName(
                parent, str(args[0]), str(args[1]))
        elif len(args) == 3:
            obj = QtWidgets.QFileDialog.getOpenFileName(
                parent, str(args[0]), str(args[1]), str(args[2]))
        elif len(args) == 4:
            obj = QtWidgets.QFileDialog.getOpenFileName(parent, str(
                args[0]), str(args[1]), str(args[2]), str(args[3]))

        return obj

    def getExistingDirectory(basedir):
        return "%s/" % QtWidgets.QFileDialog.getExistingDirectory(basedir)


def parseFloat(x):
    if x is None:
        return 0
    return float(x)


"""
class parseString(object):

    obj_ = None
    length = None

    def __init__(self, objeto):
        try:
            self.obj_ = objeto.toString()
        except Exception:
            self.obj_ = str(objeto)

        self.length = len(self.obj_)

    def __str__(self):
        return self.obj_

    def __getitem__(self, key):
        return self.obj_.__getitem__(key)



    def charAt(self, pos):
        try:
            return self.obj_[pos]
        except Exception:
            return False

    def substring(self, ini, fin):
        return self.obj_[ini: fin]

 """


def parseString(objeto):
    try:
        return objeto.toString()
    except Exception:
        return str(objeto)


def parseInt(x):
    if x is None:
        return 0
    return int(x)


def isNaN(x):
    if not x:
        return True

    try:
        float(x)
        return False
    except ValueError:
        return True


# TODO: separar en otro fichero de utilidades
def ustr(*t1):

    return "".join([ustr1(t) for t in t1])


def ustr1(t):
    if isinstance(t, str):
        return t

    if isinstance(t, float):
        try:
            t = int(t)
        except Exception:
            pass

    # if isinstance(t, QtCore.QString): return str(t)
    if isinstance(t, str):
        return str(t, "UTF-8")
    try:
        return str(t)
    except Exception as e:
        print("ERROR Coercing to string:", repr(t))
        print("ERROR", e.__class__.__name__, str(e))
        return None


def debug(txt):
    print("---> DEBUG:", ustr(txt))


class aqApp(object):

    def db():
        return pineboolib.project.conn


class SysType(object):
    def __init__(self):
        self._name_user = None

    def nameUser(self):
        return pineboolib.project.conn.user()

    def interactiveGUI(self):
        return "Pineboo"

    def isLoadedModule(self, modulename):
        return modulename in pineboolib.project.conn.managerModules().listAllIdModules()

    def translate(self, text):
        return text

    def osName(self):
        util = FLUtil()
        return util.getOS()

    def nameBD(self):
        return pineboolib.project.conn.databaseName()

    def setCaptionMainWidget(self, value):
        self.mainWidget().setWindowTitle("Pineboo - %s" % value)
        pass

    def toUnicode(self, text, format):
        return u"%s" % text

    def mainWidget(self):
        return pineboolib.project.main_window.ui

    def installPrefix(self):
        return filedir("..")

    def __getattr__(self, name):
        obj = eval("sys.widget.%s" % name, pineboolib.qsaglobals.__dict__)
        if obj:
            return obj
        else:
            qWarning("No se encuentra sys.%s" % name)

    def version(self):
        return pineboolib.project.version

    @decorators.NotImplementedWarn
    def processEvents(self):
        pass

    @decorators.NotImplementedWarn
    def reinit(self):
        pass

    def cleanupMetaData(self, connName="default"):
        pineboolib.project.conn.database(connName).manager().cleanupMetaData()

    def updateAreas(self):
        pineboolib.project.initToolBox()

    @decorators.NotImplementedWarn
    def isDebuggerMode(self):
        return False

    def nameDriver(self, connName="default"):
        return pineboolib.project.conn.database(connName).driverName()

    def addDatabase(self, connName="default"):
        return pineboolib.project.conn.useConn(connName)()

    def removeDatabase(self, connName="default"):
        return pineboolib.project.conn.removeConn(connName)


def proxy_fn(wf, wr, slot):
    def fn(*args, **kwargs):
        f = wf()
        if not f:
            return None
        r = wr()
        if not r:
            return None

        # Apaño para conectar los clicked()
        if args == (False,):
            return f()

        return f(*args, **kwargs)
    return fn


def connect(sender, signal, receiver, slot, doConnect=True):
    # print("Connect::", sender, signal, receiver, slot)
    if sender is None:
        print("Connect Error::", sender, signal, receiver, slot)
        return False
    m = re.search(r"^(\w+)\.(\w+)(\(.*\))?", slot)
    if slot.endswith("()"):
        slot = slot[:-2]
    remote_fn = getattr(receiver, slot, None)

    sl_name = re.sub(' *\(.*\)', '', signal)
    oSignal = getattr(sender, sl_name, None)
    if not oSignal and sender.__class__.__name__ == "FormInternalObj":
        oSignal = getattr(sender.parent(), sl_name, None)

    if not oSignal:
        print("ERROR: No existe la señal %s para la clase %s" % (signal, sender.__class__.__name__))
        return

    if remote_fn:
        try:
            weak_fn = weakref.WeakMethod(remote_fn)
            weak_receiver = weakref.ref(receiver)
            try:
                oSignal.disconnect(proxy_fn(weak_fn, weak_receiver, slot))
            except Exception:
                pass

            if doConnect:
                oSignal.connect(proxy_fn(weak_fn, weak_receiver, slot))
            else:
                oSignal.disconnect()
                print("Desconectando %s - %s" % (signal, slot))

        except RuntimeError as e:
            print("ERROR Connecting:", sender,
                  QtCore.SIGNAL(signal), remote_fn)
            print("ERROR %s : %s" % (e.__class__.__name__, str(e)))
            return False
    elif m:
        remote_obj = getattr(receiver, m.group(1), None)
        if remote_obj is None:
            raise AttributeError("Object %s not found on %s" %
                                 (remote_obj, str(receiver)))
        remote_fn = getattr(remote_obj, m.group(2), None)
        if remote_fn is None:
            raise AttributeError("Object %s not found on %s" %
                                 (remote_fn, remote_obj))
        try:
            if isinstance(sender, QDateEdit):
                if "valueChanged" in signal:
                    signal = signal.replace("valueChanged", "dateChanged")

            # Quito cualquier texto entre parentesis
            sg_name = re.sub(' *\(.*\)', '', signal)

            try:
                getattr(sender, sg_name).disconnect(remote_fn)
            except Exception:
                pass

            if doConnect:
                getattr(sender, sg_name).connect(remote_fn)
        except RuntimeError as e:
            print("ERROR Connecting:", sender, sg_name, remote_fn)
            print("ERROR %s : %s" % (e.__class__.__name__, str(e)))
            return False

    else:
        if isinstance(receiver, QtCore.QObject):

            try:
                sender.signal.disconnect(receiver.slot)
            except Exception:
                pass

            if doConnect:
                sender.signal.connect(receiver.slot)
        else:
            print("ERROR: Al realizar connect %r:%r -> %r:%r ; el slot no se reconoce y el receptor no es QObject." %
                  (sender, signal, receiver, slot))
    return True


def disconnect(sender, signal, receiver, slot):
    # print("Disconnect::", sender, signal, receiver, slot)
    connect(sender, signal, receiver, slot, False)


class Date(object):

    @classmethod
    def parse(cls, value):
        return QtCore.QDate.fromString(value)


QMessageBox = QtWidgets.QMessageBox


class MessageBox(QMessageBox):
    @classmethod
    def msgbox(cls, typename, text, button0, button1=None, button2=None, title=None, form=None):
        if title or form:
            print(
                "WARN: MessageBox: Se intentó usar título y form, y no está implementado.")
        icon = QMessageBox.NoIcon
        title = "Message"
        if typename == "question":
            icon = QMessageBox.Question
            title = "Question"
        elif typename == "information":
            icon = QMessageBox.Information
            title = "Information"
        elif typename == "warning":
            icon = QMessageBox.Warning
            title = "Warning"
        elif typename == "critical":
            icon = QMessageBox.Critical
            title = "Critical"
        # title = unicode(title,"UTF-8")
        # text = unicode(text,"UTF-8")
        msg = QMessageBox(icon, str(title), str(text))
        msg.addButton(button0)
        if button1:
            msg.addButton(button1)
        if button2:
            msg.addButton(button2)
        return msg.exec_()

    @classmethod
    def question(cls, *args):
        return cls.msgbox("question", *args)

    @classmethod
    def information(cls, *args):
        return cls.msgbox("question", *args)

    @classmethod
    def warning(cls, *args):
        return cls.msgbox("warning", *args)

    @classmethod
    def critical(cls, *args):
        return cls.msgbox("critical", *args)


class Input(object):
    @classmethod
    def getText(cls, question, prevtxt, title):
        text, ok = QtWidgets.QInputDialog.getText(None, title,
                                                  question, QtWidgets.QLineEdit.Normal, prevtxt)
        if not ok:
            return None
        return text


def qsa_length(obj):
    lfn = getattr(obj, "length", None)
    if lfn:
        return lfn()
    return len(lfn)


def qsa_text(obj):
    try:
        return obj.text()
    except Exception:
        return obj.text


class qsa:
    parent = None
    loaded = False

    def __init__(self, parent):
        if isinstance(parent, str):
            parent = parent
        self.parent = parent
        self.loaded = True

    def __getattr__(self, k):
        if not self.loaded:
            return super(qsa, self).__getattr__(k)
        try:
            f = getattr(self.parent, k)
            if callable(f):
                return f()
            else:
                return f
        except Exception:
            if k == 'length':
                if self.parent:
                    return len(self.parent)
                else:
                    return 0
            print("FATAL: qsa: error al intentar emular getattr de %r.%r" %
                  (self.parent, k))
            print(traceback.format_exc(4))

    def __setattr__(self, k, v):
        if not self.loaded:
            return super(qsa, self).__setattr__(k, v)
        try:
            if not self.parent:
                return
            f = getattr(self.parent, k)
            if callable(f):
                return f(v)
            else:
                return setattr(self.parent, k, v)
        except Exception:
            try:
                k = 'set' + k[0].upper() + k[1:]
                f = getattr(self.parent, k)
                if callable(f):
                    return f(v)
                else:
                    return setattr(self.parent, k, v)
            except Exception:
                print("FATAL: qsa: error al intentar emular setattr de %r.%r = %r" % (
                    self.parent, k, v))
                print(traceback.format_exc(4))


# -------------------------- FORBIDDEN FRUIT ----------------------------------
# Esto de aquí es debido a que en Python3 decidieron que era mejor abandonar
# QString en favor de los strings de python3. Por lo tanto ahora el código QS
# llama a funciones de str en lugar de QString, y obviamente algunas no existen

# forbidden fruit tiene otra licencia (gplv3) y lo he incluído dentro del código
# por simplicidad de la instalación; pero sigue siendo gplv3, por lo que si
# alguien quiere hacer algo que en MIT se puede y en GPLv3 no, tendría que sacar
# ese código de allí. (como mínimo; no sé hasta donde llegaría legalmente)

# Para terminar, esto es una guarrada, pero es lo que hay. Si lo ves aquí, te
# gusta y lo quieres usar en tu proyecto, no, no es una bunea idea. Yo no tuve
# más opción. (Es más, si consigo parchear el python para que no imprima "left"
# quitaré esta librería demoníaca)

# from forbiddenfruit import curse
# curse(str, "left", lambda self, n: self[:n])
