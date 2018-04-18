# -*- coding: utf-8 -*-
from PyQt5 import QtCore, QtWidgets
from PyQt5.Qt import QRegExp

import pineboolib
from pineboolib import decorators

from pineboolib.utils import DefFun, XMLStruct
from pineboolib.cursortablemodel import CursorTableModel
from pineboolib.flcontrols import ProjectClass

from pineboolib.fllegacy.FLSqlQuery import FLSqlQuery
from pineboolib.fllegacy.FLUtil import FLUtil
from pineboolib.fllegacy.FLSqlSavePoint import FLSqlSavePoint
from pineboolib.fllegacy.FLFieldMetaData import FLFieldMetaData
from pineboolib.fllegacy.FLAccessControlFactory import FLAccessControlFactory
from pineboolib.fllegacy.FLAction import FLAction

import weakref
import copy
import datetime
import logging
logger = logging.getLogger(__name__)


class Struct(object):
    pass


# ###############################################################################
# ###############################################################################
# ######
# ######
# ######                           PNBuffer
# ######
# ######
# ###############################################################################
# ###############################################################################


class PNBuffer(ProjectClass):

    fieldList_ = None
    cursor_ = None
    clearValues_ = False
    line_ = None
    inicialized_ = False

    def __init__(self, cursor):
        super(PNBuffer, self).__init__()
        self.cursor_ = cursor
        self.fieldList_ = []
        tmd = self.cursor().metadata()
        if not tmd:
            return
        else:
            campos = tmd.fieldList()
        for campo in campos:
            field = Struct()
            field.name = str(campo.name())
            field.value = None
            field.metadata = campo
            field.type_ = field.metadata.type()
            field.modified = False
            field.originalValue = None
            field.generated = campo.generated()

            self.line_ = None
            self.fieldList_.append(field)

    """
    Retorna el numero de campos que componen el buffer
    @return int
    """

    def count(self):
        return len(self.fieldsList())
    """
    Actualización inicial de los campos del buffer
    @param row = Linea del cursor
    """

    def primeInsert(self, row=None):
        if self.inicialized_:
            logger.debug("(%s)PNBuffer. Se inicializa nuevamente el cursor", self.cursor().curName())

        self.primeUpdate(row)
        self.inicialized_ = True

    def primeUpdate(self, row=None):

        if row < 0 or row is None:
            row = self.cursor().currentRegister()

        for field in self.fieldsList():

            if field.type_ in ("unlock", "bool"):
                field.value = (self.cursor().model().value(
                    row, field.name) in ("True", True, 1, "1"))
                #    field.value = True
                # else:
                #    field.value = False

            elif self.cursor().model().value(row, field.name) in ("None", None):
                field.value = None

            else:
                field.value = self.cursor().model().value(row, field.name)
            # val = self.cursor().model().value(row , field.name)
            # if val == "None":
            #    val = None
            # self.setValue(field.name, val)

            field.originalValue = copy.copy(field.value)
            # self.cursor().bufferChanged.emit(field.name)

        self.setRow(self.cursor().currentRegister())

    """
    Borra los valores de todos los campos del buffer
    """

    def primeDelete(self):
        for field in self.fieldList():
            self.setNull(field.name)

    """
    Indica la linea del cursor a la que hace referencia el buffer
    @return int
    """

    def row(self):
        return self.line_

    """
    Setea la linea del cursor a la que se supone hace referencia el buffer
    @param l = registro del cursor
    """

    def setRow(self, l):
        self.line_ = l

    """
    Setea a None el campo especificado
    @param name = Nombre del campo
    """

    def setNull(self, name):
        # field = self.field(name)
        return self.setValue(name, None)

    """
    Indica si el campo es generado o no
    @return bool (True es generado, False no es generado)
    """

    def isGenerated(self, name):
        return self.field(name).generated

        """
    Setea que es generado un campo.
    @param f. FLFieldMetadata campo a marcar
    @param value. True o False si el campo es generado
    """

    def setGenerated(self, f, value):
        if not isinstance(f, str) and not isinstance(f, int):
            f = f.name()
        self.field(f).generated = value

    """
    Setea todos los valores a None y marca field.modified a True
    @param b bool (True, False no hace nada)
    """

    def clearValues(self, b):
        if b:
            for field in self.fieldList_:
                field.value = None
                field.modified = False

    """
    Indica si el buffer no se ha iniciado
    @return bool True está iniciado, False no está iniciado
    """

    def isEmpty(self):
        return self.inicialized_

    """
    Indica si un valor esta vacío
    @param n (str,int) del campo a comprobar si está vacío
    @return bool (True vacío, False contiene valores)
    """

    def isNull(self, n):
        field = self.field(n)

        if field is None:
            # FIXME: Esto es un error. Si el campo no existe, es una llamada
            # errónea.
            return True

        if field.type_ in ("bool", "unlock"):
            return not (self.value(field.name) in (True, False))

        return self.value(field.name) is None

    """
    Retorna el valor de un campo
    @param n (str,int) del campo a recoger valor
    @return valor del campo
    """

    def value(self, n):
        field = self.field(n)

        v = field.value
        if field.value is None:
            v = None
        else:
            if field.type_ in ("str", "pixmap", "time", "date"):
                try:
                    v = str(field.value)
                except Exception:
                    v = ""

            if field.type_ in ("int", "uint", "serial"):
                try:
                    v = int(field.value)
                except Exception:
                    v = 0

            if field.type_ == "double":
                try:
                    v = float(field.value)
                except Exception:
                    v = 0.0

        if field.type_ in ("bool", "unlock"):
            v = field.value in (True, "true")
        # ret = self.convertToType(field.value, field.type_)
        # logger.trace("---->retornando %s %s %s",v , type(v), field.value, field.name)
        return v

    """
    Setea el valor de un campo del buffer
    @param name. Nombre del campo
    @param value. Valor a asignar al campo
    @param mark_. Si True comprueba que ha cambiado respecto al valor asignado en primeUpdate y si ha cambiado lo marca como modificado (Por defecto a True)
    """

    def setValue(self, name, value, mark_=True):
        # logger.trace("**** %s *** ->%s previo ->%s" % (name, value, self.value(name)))
        if value is not None and not isinstance(value, (int, float, str, datetime.time, datetime.date, bool)):
            raise ValueError(
                "No se admite el tipo %r , en setValue %r" % (type(value), value))

        field = self.field(name)
        if field is None:
            return False

        if field.type_ in ("string", "stringlist") and not isinstance(value, str) and value is not None:
            value = str(value)

        # if field.type_ in ("bool","unlock") and isinstance(value , str):
        #    value = (value == "true")

        if self.hasChanged(field.name, value):

                    # if not value == None:
                    #    value = str(value)

            # if field.type_ == "date" and value == None: #Evitamos poner un date a None
            #    pass
            # else:
            field.value = value

            if mark_:
                if not field.value == field.originalValue:
                    field.modified = True
                else:
                    field.modified = False
                    # self.setMd5Sum(value)

        return True

    """
    Convierte un valor del buffer en su tipo de dato válido
    @param value. Valor a convertir
    @param type_. tipo de campo a convertir_
    @return valor en tipo valido
    """
    # def convertToType(self, value, type_):
    #
    #    if value in (u"None", None):
    #        if type_ in ("bool","unlock"):
    #            value = False
    #        elif type_ in ("int", "uint", "serial"):
    #            value = 0
    #        elif type_ == "double":
    #            value = 0.00
    #        elif type_ in ("string","pixmap","stringlist"):
    #            value = ""
    #
    #    else:
    #        if type_ in ("bool","unlock") and isinstance(value, str):
    #            value = (value == "true")
    #        elif type_ in ("int", "uint", "serial") and not isinstance( value, int):
    #            value =  int(value)
    #        elif type_ == "double" and not isinstance( value, float):
    #            value = float(value)
    #        elif type_ in ("string","pixmap","stringlist") and not isinstance( value, str):
    #            value = str(value)
    #
    #        elif type_ == "date" and not isinstance(value, str):
    #             fv = value
    #             if isinstance(fv, QDate):
    #                 value = fv.toString("yyyy-MM-dd")
    #             else:
    #                 value = fv.strftime('%Y-%m-%d')
    #
    #        elif type_ == "date" and value == "null":
    #            value = None
    #
    #        elif type_ == "time" and not isinstance(value, str):
    #             fv = value
    #             value = fv.strftime('%H:%M:%S')
    #    return value

    """
    Comprueba si un campo tiene valor diferente. Esto es especialmente util para los número con decimales
    @return True si ha cambiado, False si es el mismo valor
    """

    def hasChanged(self, name, value):
        field = self.field(name)
        if value in (None, "None"):
            return True

        if field.name == name:
            type = field.type_
            actual = field.value
            if actual in (None, "None"):
                return True

            if (actual == "" and value != "") or (actual != "" and value == ""):
                return True
            elif type in ("string", "stringlist"):
                return not (actual == value)
            elif type in ("int", "uint", "serial"):
                return not (int(actual) == int(value))
            elif type == "double":
                return not (float(actual) == float(value))
            else:
                return True

        return True

    """
    Indica al cursor que pertenecemos
    @return Cursor al que pertenecemos
    """

    def cursor(self):
        return self.cursor_

    """
    Retorna los campos del buffer modificados desde original
    @return array Lista de campos modificados
    """

    def modifiedFields(self):
        lista = []
        for f in self.fieldsList():
            if f.modified:
                lista.append(f.name)

        return lista

    """
    Setea todos los campos como no modificados
    """

    def setNoModifiedFields(self):
        for f in self.fieldsList():
            if f.modified:
                f.modified = False

    """
    Indica que campo del buffer es clave primaria
    @return Nombre del campo que es clave primaria
    """

    def pK(self):
        for f in self.fieldsList():
            if f.metadata.isPrimaryKey():
                return f.name

        logger.message("PNBuffer.pk(): No se ha encontrado clave Primaria")

    """
    Indica la posicion del buffer de un campo determinado
    @param name
    @return Posición del campo a buscar
    """

    def indexField(self, name):
        i = 0
        for f in self.fieldsList():
            if f.name == name:
                return i

            i = i + 1

    def fieldsList(self):
        return self.fieldList_

    def field(self, n):
        if isinstance(n, str):
            for f in self.fieldsList():
                if f.name.lower() == n.lower():
                    return f
        else:
            i = 0
            for f in self.fieldsList():
                if i == n:
                    return f

                i = i + 1

        return None

# ###############################################################################
# ###############################################################################
# ######
# ######
# ######                      FLSqlCursorPrivate
# ######
# ######
# ###############################################################################
# ###############################################################################


class FLSqlCursorPrivate(QtCore.QObject):

    """
    Buffer con un registro del cursor.

    Según el modo de acceso FLSqlCursor::Mode establecido para el cusor, este buffer contendrá
    el registro activo de dicho cursor listo para insertar,editar,borrar o navegar.
    """
    buffer_ = None

    """
    Copia del buffer.

    Aqui se guarda una copia del FLSqlCursor::buffer_ actual mediante el metodo FLSqlCursor::updateBufferCopy().
    """
    bufferCopy_ = None

    """
    Metadatos de la tabla asociada al cursor.
    """
    metadata_ = None

    """
    Mantiene el modo de acceso actual del cursor, ver FLSqlCursor::Mode.
    """
    modeAccess_ = None

    """
    Cursor relacionado con este.
    """
    cursorRelation_ = None

    """
    Relación que determina como se relaciona con el cursor relacionado.
    """
    relation_ = None

    """
    Esta bandera cuando es TRUE indica que se abra el formulario de edición de regitros en
    modo edición, y cuando es FALSE se consulta la bandera FLSqlCursor::browse. Por defecto esta
    bandera está a TRUE
    """
    edition_ = True

    """
    Esta bandera cuando es TRUE y la bandera FLSqlCuror::edition es FALSE, indica que se
    abra el formulario de edición de registro en modo visualización, y cuando es FALSE no hace
    nada. Por defecto esta bandera está a TRUE
    """
    browse_ = True
    browseStates_ = []

    """
    Filtro principal para el cursor.

    Este filtro persiste y se aplica al cursor durante toda su existencia,
    los filtros posteriores, siempre se ejecutaran unidos con 'AND' a este.
    """
    # self.d._model.where_filters["main-filter"] = None

    """
    Accion asociada al cursor, esta accion pasa a ser propiedad de FLSqlCursor, que será el
    encargado de destruirla
    """
    action_ = None

    """
    Cuando esta propiedad es TRUE siempre se pregunta al usuario si quiere cancelar
    cambios al editar un registro del cursor.
    """
    askForCancelChanges_ = False

    """
    Indica si estan o no activos los chequeos de integridad referencial
    """
    activatedCheckIntegrity_ = True

    """
    Indica si estan o no activas las acciones a realiar antes y después del Commit
    """
    activatedCommitActions_ = True

    """
    Contexto de ejecución de scripts.

    El contexto de ejecución será un objeto formulario el cual tiene asociado un script.
    Ese objeto formulario corresponde a aquel cuyo origen de datos es este cursor.
    El contexto de ejecución es automáticamente establecido por las clases FLFormXXXX.
    """
    ctxt_ = None

    """
    Cronómetro interno
    """
    timer_ = None

    """
    Cuando el cursor proviene de una consulta indica si ya se han agregado al mismo
    la definición de los campos que lo componen
    """
    populated_ = False

    """
    Cuando el cursor proviene de una consulta contiene la sentencia sql
    """
    query_ = None

    """
    Cuando el cursor proviene de una consulta contiene la clausula order by
    """
    queryOrderBy_ = None

    """
    Base de datos sobre la que trabaja
    """
    db_ = None

    """
    Pila de los niveles de transacción que han sido iniciados por este cursor
    """
    transactionsOpened_ = []

    """
    Filtro persistente para incluir en el cursor los registros recientemente insertados aunque estos no
    cumplan los filtros principales. Esto es necesario para que dichos registros sean válidos dentro del
    cursor y así poder posicionarse sobre ellos durante los posibles refrescos que puedan producirse en
    el proceso de inserción. Este filtro se agrega a los filtros principales mediante el operador OR.
    """
    persistentFilter_ = None

    """
    Cursor propietario
    """
    cursor_ = None

    """
    Nombre del cursor
    """
    curName_ = None

    """
    Orden actual
    """
    sort_ = None
    """
    Auxiliares para la comprobacion de riesgos de bloqueos
    """
    inLoopRisksLocks_ = False
    inRisksLocks_ = False
    modalRisksLocks_ = None
    timerRisksLocks_ = None

    """
    Para el control de acceso dinámico en función del contenido de los registros
    """

    acTable_ = None
    acPermTable_ = None
    acPermBackupTable_ = None
    acosTable_ = None
    acosBackupTable_ = None
    acosCondName_ = None
    acosCond_ = None
    acosCondVal_ = None
    lastAt_ = None
    aclDone_ = False
    fieldsNamesUnlock_ = None
    idAc_ = 0
    idAcos_ = 0
    idCond_ = 0
    id_ = "000"

    """ Uso interno """
    isQuery_ = None
    isSysTable_ = None
    mapCalcFields_ = []
    rawValues_ = None

    md5Tuples_ = None

    countRefCursor = None

    _model = None

    _currentregister = None
    editionStates_ = None

    filter_ = None

    _current_changed = QtCore.pyqtSignal(int)

    FlagStateList = None
    FlagState = None

    def __init__(self):
        super(FLSqlCursorPrivate, self).__init__()
        self.metadata_ = None
        self.countRefCursor = 0
        self._currentregister = -1
        self.acosCondName_ = None
        self.buffer_ = None
        self.editionStates_ = None
        self.activatedCheckIntegrity_ = True
        self.askForCancelChanges_ = True
        self.transactionsOpened_ = []
        self.cursorRelation_ = None
        self.idAc_ = 0
        self.idAcos_ = 0
        self.idCond_ = 0
        self.id_ = "000"
        self.aclDone_ = False

    def __del__(self):

        if self.metadata_:
            self.undoAcl()

        if self.bufferCopy_:
            del self.bufferCopy_

        if self.relation_:
            del self.relation_

        if self.acTable_:
            del self.acTable_

        if self.editionStates_:
            del self.editionStates_
            # logger.trace("AQBoolFlagState count %s", self.count_)

        if self.browseStates_:
            del self.browseStates_
            # logger.trace("AQBoolFlagState count %s", self.count_)
        if self.transactionsOpened_:
            del self.transactionsOpened_

    def doAcl(self):
        if not self.acTable_:
            self.acTable_ = FLAccessControlFactory().create("table")
            self.acTable_.setFromObject(self.metadata_)
            self.acosBackupTable_ = self.acTable_.getAcos()
            self.acPermBackupTable_ = self.acTable_.perm()
            self.acTable_.clear()

        if self.modeAccess_ == FLSqlCursor.Insert or (not self.lastAt_ == -1 and self.lastAt_ == self.cursor_.at()):
            return

        if self.acosCondName_ is not None:
            condTrue_ = False

            if self.acosCond_ == FLSqlCursor.Value:
                condTrue_ = (self.cursor_.value(
                    self.acosCondName_) == self.acosCondVal_)
            elif self.acosCond_ == FLSqlCursor.RegExp:
                condTrue_ = str(QRegExp(str(self.acosCondVal_)).exactMatch(
                    str(self.cursor_.value(self.acosCondName_))))
            elif self.acosCond_ == FLSqlCursor.Function:
                fn = eval(self.acosCondName_, pineboolib.qsaglobals.__dict__)
                condTrue_ = fn(self.cursor_) == self.acosCondVal_

            if condTrue_:
                if not self.acTable_.name() == self.id_:
                    self.acTable_.clear()
                    self.acTable_.setName(self.id_)
                    self.acTable_.setPerm(self.acPermTable_)
                    self.acTable_.setAcos(self.acosTable_)
                    self.acTable_.processObject(self.metadata_)
                    self.aclDone_ = True

                return

            elif self.cursor_.isLocked() or (self.cursorRelation_ and self.cursorRelation_.isLocked()):
                if not self.acTable_.name() == self.id_:
                    self.acTable_.clear()
                    self.acTable_.setName(self.id_)
                    self.acTable_.setPerm("r-")
                    self.acTable_.processObject(self.metadata_)
                    self.aclDone_ = True

                return

        self.undoAcl()

    def undoAcl(self):
        if self.acTable_ and self.aclDone_:
            self.aclDone_ = False
            self.acTable_.clear()
            self.acTable_.setPerm(self.acPermBackupTable_)
            self.acTable_.setAcos(self.acosBackupTable_)
            self.acTable_.processObject(self.metadata_)

    @decorators.NotImplementedWarn
    def needUpdate(self):
        return False

        if self.isQuery_:
            return False

        md5Str = str(self.db_.md5TuplesStateTable(self.curName_))

        if md5Str.isEmpty():
            return False

        if self.md5Tuples_.isEmpty():
            self.md5Tuples_ = md5Str
            return True

        need = False

        if not md5Str == self.md5Tuples_:
            need = True

        self.md5Tuples_ = md5Str
        return need

    def msgBoxWarning(self, msg, throwException=False):
        logger.message(msg)
        if not throwException:
            QtWidgets.QMessageBox.warning(
                QtWidgets.QApplication.focusWidget(), "Pineboo", msg)


# ###############################################################################
# ###############################################################################
# ######
# ######
# ######                         FLSqlCursor
# ######
# ######
# ###############################################################################
# ###############################################################################


class FLSqlCursor(ProjectClass):

    """
    Insertar, en este modo el buffer se prepara para crear un nuevo registro
    """
    Insert = 0

    """
    Edición, en este modo el buffer se prepara para editar el registro activo
    """
    Edit = 1

    """
    Borrar, en este modo el buffer se prepara para borrar el registro activo
    """
    Del = 2

    """
    Navegacion, en este modo solo se puede visualizar el buffer
    """
    Browse = 3

    """
    evalua un valor fijo
    """
    Value = 0

    """
    evalua una expresion regular
    """
    RegExp = 1

    """
    evalua el valor devuelto por una funcion de script
    """
    Function = 2

    _selection = None

    _refreshDelayedTimer = None

    def __init__(self, name, autopopulate=True, connectionName_or_db=None, cR=None, r=None, parent=None):
        super(FLSqlCursor, self).__init__()
        self._valid = False
        self.d = FLSqlCursorPrivate()
        self.d.cursor_ = self
        self.d.nameCursor_ = "%s_%s" % (
            name, QtCore.QDateTime.currentDateTime().toString("dd.MM.yyyyThh:mm:ss.zzz"))

        if connectionName_or_db is None:
            self.d.db_ = self._prj.conn
        # elif isinstance(connectionName_or_db, QString) or
        # isinstance(connectionName_or_db, str):
        elif isinstance(connectionName_or_db, str):
            self.d.db_ = self._prj.conn.useConn(connectionName_or_db)
        else:
            self.d.db_ = connectionName_or_db

        # for module in self._prj.modules:
        #    for action in module.actions:
        #        if action.name == name:
        #            self.d.action_ = action
        #            break
        self.init(name, autopopulate, cR, r)

    """
    Código de inicialización común para los constructores
    """

    def init(self, name, autopopulate, cR, r):
        # logger.trace("FLSqlCursor(%s): Init() %s (%s, %s)" % (name, self, cR, r))

        # if self.d.metadata_ and not self.d.metadata_.aqWasDeleted() and not
        # self.d.metadata_.inCache():

        self.d.curName_ = name
        if self.setAction(self.d.curName_):
            self.d.countRefCursor = self.d.countRefCursor + 1
        else:
            # logger.trace("FLSqlCursor(%s).init(): ¿La tabla no existe?" % name)
            return None

        self.d.modeAccess_ = FLSqlCursor.Browse

        if name:
            if not self.db().manager().existsTable(name):
                self.d.metadata_ = self.db().manager().createTable(name)
        else:
            self.d.metadata_ = self.db().manager().metadata(name)
        self.d.cursorRelation_ = cR
        if r:  # FLRelationMetaData
            if self.d.relation_ and self.d.relation_.deref():
                del self.d.relation_

            # r.ref()
            self.d.relation_ = r
        else:
            self.d.relation_ = None

        if not self.d.metadata_:
            return

        self.fieldsNamesUnlock_ = self.d.metadata_.fieldsNamesUnlock()

        self.d.isQuery_ = self.metadata().isQuery()
        if (name[len(name) - 3:]) == "sys" or self.db().manager().isSystemTable(name):
            self.d.isSysTable_ = True
        else:
            self.d.isSysTable_ = False

        # if self.d.isQuery_:
        #     qry = self.d.db_.manager().query(self.d.metadata_.query(), self)
        #     self.d.query_ = qry.sql()
        #     if qry and self.d.query_:
        #         self.exec_(self.d.query_)
        #     if qry:
        #         self.qry.deleteLater()
        # else:
        #     self.setName(self.metadata().name(), autopopulate)
        self.setName(self.metadata().name(), autopopulate)

        self.d.modeAccess_ = self.Browse
        if cR and r:
            try:
                cR.bufferChanged.disconnect(self.refresh)
                cR.d._current_changed.disconnect(self.refresh)
            except Exception:
                pass
            cR.bufferChanged.connect(self.refresh)
            cR.d._current_changed.connect(self.refresh)
            try:
                cR.newBuffer.disconnect(self.clearPersistentFilter)
            except Exception:
                pass
            cR.newBuffer.connect(self.clearPersistentFilter)
        else:
            self.seek(None)

        if self.d.timer_:
            del self.d.timer_

        self.refreshDelayed()
        # self.d.md5Tuples_ = self.db().md5TuplesStateTable(self.d.curName_)
        # self.first()

    def conn(self):
        return self.d.db_

    def table(self):
        m = self.metadata()
        if m:
            return m.name()
        else:
            return None

    def __getattr__(self, name):
        return DefFun(self, name)

    def setName(self, name, autop):
        self.name = name
        # autop = autopopulate para que??

    """
    Para obtener los metadatos de la tabla.

    @return Objeto FLTableMetaData con los metadatos de la tabla asociada al cursor
    """

    def metadata(self):
        if not self.d.metadata_:
            logger.trace("FLSqlCursor(%s) Esta devolviendo un metadata vacio", self.curName())
            return None
        return self.d.metadata_

    """
    Para obtener el modo de acceso actual del cursor.

    @return Constante FLSqlCursor::Mode que define en que modo de acceso esta preparado
        el buffer del cursor
    """

    def modeAccess(self):
        return self.d.modeAccess_

    """
    Para obtener el filtro principal del cursor.

    @return Cadena de texto con el filtro principal
    """

    def mainFilter(self):
        if getattr(self.d._model, "where_filters", None):
            return self.d._model.where_filters["main-filter"]
        else:
            return None

    """
    Para obtener la accion asociada al cursor.

    @return  Objeto FLAction
    """

    def action(self):
        action = FLAction(self._action)
        return str(action.name())

    def actionName(self):
        return self.d.curName_

    """
    Establece la accion asociada al cursor.

    @param a Objeto FLAction
    """

    def setAction(self, a):
        # if isinstance(a, str) or isinstance(a, QString):

        # a = str(a) # FIXME: Quitar cuando se quite QString

        if isinstance(a, str):
            # logger.trace("FLSqlCursor(%s): setAction(%s)" % (self.d.curName_, a))
            self._action = XMLStruct()
            try:
                self._action = self._prj.actions[str(a)]
            except KeyError:
                # logger.notice("FLSqlCursor.setAction(): Action no encontrada. Usando %s como action.table" % a)
                self._action.table = a
                # logger.notice("setAction(): Action no encontrada %s en %s actions. Es posible que la tabla no exista" % (a, len(self._prj.actions)))
                # return False
            # self._action = self._prj.actions["articulos"]

            if getattr(self._action, "table", None):
                self.d._model = CursorTableModel(
                    self._action, self._prj, self.conn())
                if not self.d._model:
                    return None

                self._selection = QtCore.QItemSelectionModel(self.model())
                self._selection.currentRowChanged.connect(
                    self.selection_currentRowChanged)
                self._currentregister = self._selection.currentIndex().row()
                self.d.metadata_ = self.db().manager().metadata(self._action.table)
            else:
                return False

            self.d.activatedCheckIntegrity_ = True
            self.d.activatedCommitActions_ = True
            return True
        else:
            self.d.action_ = str(a)

    """
    Establece el filtro principal del cursor.

    @param f Cadena con el filtro, corresponde con una clausura WHERE
    @param doRefresh Si TRUE tambien refresca el cursor
    """

    def setMainFilter(self, f, doRefresh=True):
        # if f == "":
        #    f = "1 = 1"

        # logger.trace("--------------------->Añadiendo filtro",  f)
        if self.d._model and getattr(self.d._model, "where_filters", None):
            self.d._model.where_filters["main-filter"] = f
            if doRefresh:
                self.refresh()

    """
    Establece el modo de acceso para el cursor.

    @param m Constante FLSqlCursor::Mode que indica en que modo de acceso
    se quiere establecer el cursor
    """

    def setModeAccess(self, m):
        self.d.modeAccess_ = m

    """
    Devuelve el nombre de la conexión que el cursor usa

    @return Nombre de la conexión
    """

    def connectionName(self):
        return self.d.db_.connectionName()

    """
    Establece el valor de un campo del buffer de forma atómica y fuera de transacción.

    Invoca a la función, cuyo nombre se pasa como parámetro, del script del contexto del cursor
    (ver FLSqlCursor::ctxt_) para obtener el valor del campo. El valor es establecido en el campo de forma
    atómica, bloqueando la fila durante la actualización. Esta actualización se hace fuera de la transacción
    actual, dentro de una transacción propia, lo que implica que el nuevo valor del campo está inmediatamente
    disponible para las siguientes transacciones.

    @param fN Nombre del campo
    @param functionName Nombre de la función a invocar del script
    """

    def setAtomicValueBuffer(self, fN, functionName):
        if not self.d.buffer_ or not fN or not self.d.metadata_:
            return

        field = self.d.metadata_.field(fN)

        if not field:
            logger.message("setAtomicValueBuffer(): No existe el campo %s:%s", self.d.metadata_.name(), fN)
            return

        if not self.d.db_.dbAux():
            return

        type = field.type()
        # fltype = FLFieldMetaData.FlDecodeType(type)
        pK = self.d.metadata_.primaryKey()
        v = None

        if self.d.cursorRelation_ and self.d.modeAccess_ == self.Browse:
            self.d.cursorRelation_.commit(False)

        if pK and not self.d.db_.db() == self.d.db_.dbAux():
            pKV = self.d.buffer_.value(pK)
            self.d.db_.dbAux().transaction()

            arglist = []
            arglist.append(fN)
            arglist.append(self.d.buffer_.value(fN))
            v = self._prj.call(functionName, arglist, self.d.ctxt_)

            q = FLSqlQuery(None, self.d.db_.dbAux())
            ret = q.exec_("UPDATE  %s SET %s = %s WHERE %s" % (
                self.d.metadata_.name(), fN, self.d.db_.manager().formatValue(type, v),
                self.d.db_.manager().formatAssignValue(self.d.metadata_.field(pK), pKV)))
            if ret:
                self.d.db_.dbAux().commit()
            else:
                self.d.db_.dbAux().rollback()
        else:
            logger.warn("No se puede actualizar el campo de forma atómica, porque no existe clave primaria")

        self.d.buffer_.setValue(fN, v)
        self.bufferChanged.emit()

    """
    Establece el valor de un campo del buffer con un valor.

    @param fN Nombre del campo
    @param v Valor a establecer para el campo
    """

    def setValueBuffer(self, fN, v):
        if not self.buffer() or not fN or not self.metadata():
            return

        field = self.metadata().field(fN)
        if not field:
            logger.warn("setValueBuffer(): No existe el campo %s:%s", self.curName(), fN)
            return

        if not self.buffer().hasChanged(fN, v):
            return

        # if not self.d.buffer_:  # Si no lo pongo malo....
        #    self.primeUpdate()

        if not fN or not self.d.metadata_:
            return

        field = self.d.metadata_.field(fN)
        if not field:
            logger.warn("FLSqlCursor::setValueBuffer() : No existe el campo %s:%s", self.d.metadata_.name(), fN)
            return

        type_ = field.type()
        # fltype = field.flDecodeType(type_)
        vv = v

        if vv and type_ == "pixmap":
            vv = self.d.db_.normalizeValue(vv)
            largeValue = self.d.db_.manager().storeLargeValue(self.d.metadata_, vv)
            if largeValue:
                vv = largeValue
        if field.outTransaction() and self.d.db_.dbAux() and not self.d.db_.db() is self.d.db_.dbAux() and not self.d.modeAccess_ == self.Insert:
            pK = self.d.metadata_.primaryKey()

            if self.d.cursorRelation_ and not self.d.modeAccess_ == self.Browse:
                self.d.cursorRelation_.commit(False)

            if pK:
                pKV = self.d.buffer_.value(pK)
                q = FLSqlQuery(None, "Aux")

                q.exec_("UPDATE %s SET %s = %s WHERE %s;" % (self.metadata().name(), fN, self.db().manager(
                ).formatValue(type_, vv), self.db().manager().formatAssignValue(self.metadata().field(pK), pKV)))
            else:
                FLUtil.tr(
                    "FLSqlCursor : No se puede actualizar el campo fuera de transaccion, porque no existe clave primaria")

        else:
            self.d.buffer_.setValue(fN, vv)

        # logger.trace("(%s)bufferChanged.emit(%s)" % (self.curName(),fN))
        self.bufferChanged.emit(fN)

    """
    Devuelve el valor de un campo del buffer.

    @param fN Nombre del campo
    """

    def valueBuffer(self, fN):
        fN = str(fN)
        if self.d.rawValues_:
            return self.valueBufferRaw(fN)

        if not self.metadata():
            return None

        # if not self.d.buffer_ or self.d.buffer_.isEmpty() or not
        # self.metadata():
        if (self.model().rows > 0 and not self.modeAccess() == FLSqlCursor.Insert) or not self.d.buffer_:
            if not self.d.buffer_:
                # logger.trace("solicitando rb de", self.curName(), self.modeAccess(), self.d._currentregister, self.model().rows)
                return None

            if not self.d.buffer_:
                # logger.trace("ERROR: FLSqlCursor(%s): aún después de refresh, no tengo buffer." % self.curName())
                return None

        field = self.metadata().field(fN)
        if not field:
            logger.warn("valueBuffer(): No existe el campo %s:%s en la tabla %s", self.curName(), fN, self.metadata().name())
            return None

        type_ = field.type()

        v = None
        if field.outTransaction() and self.d.db_.dbAux() and not self.d.db_.db() == self.d.db_.dbAux() and not self.d.modeAccess_ == self.Insert:
            pK = self.d.metadata_.primaryKey()
            if pK:
                pKV = self.d.buffer_.value(pK)
                # q = FLSqlQuery()
                q = FLSqlQuery(None, "Aux")
                sql_query = "SELECT %s FROM %s WHERE %s" % (fN, self.d.metadata_.name(
                ), self.d.db_.manager().formatAssignValue(self.d.metadata_.field(pK), pKV))
                # q.exec_(self.d.db_.dbAux(), sql_query)
                q.exec_(sql_query)
                if q.next():
                    v = q.value(0)
            else:
                logger.warn("No se puede obtener el campo fuera de transacción porque no existe clave primaria")

        else:
            v = self.d.buffer_.value(fN)

        # Por compatibilidad con Eneboo no devolvemos None nunca
        if type_ in ("string", "stringlist") and v is None:
            v = ""
        elif type_ in ("double", "int", "uint") and v is None:
            v = 0

        if v and type_ == "pixmap":
            vLarge = self.d.db_.manager().fetchLargeValue(v)
            if vLarge:
                return vLarge

        return v

    def fetchLargeValue(self, value):
        return self.d.db_.manager().fetchLargeValue(value)

    """
    Devuelve el valor de un campo del buffer copiado antes de sufrir cambios.

    @param fN Nombre del campo
    """

    def valueBufferCopy(self, fN):
        if not self.d.bufferCopy_ and fN is None or not self.d.metadata_:
            return None

        field = self.d.metadata_.field(fN)
        if not field:
            FLUtil.tr("FLSqlCursor::valueBufferCopy() : No existe el campo ") + \
                self.d.metadata_.name() + ":" + fN
            return None

        type_ = field.type()
        if self.d.bufferCopy_.isNull(fN):
            if type_ == "double" or type_ == "int" or type_ == "uint":
                return 0

        v = self.d.bufferCopy_.value(fN)

        # v.cast(fltype)

        if v and type_ == "pixmap":
            vl = self.d.db_.manager().fetchLargeValue(v)
            if vl.isValid():
                return vl

        return v

    """
    Establece el valor de FLSqlCursor::edition.

    @param b TRUE o FALSE
    """

    def setEdition(self, b, m=None):

        if not m:
            self.d.edition_ = b
            return

        stateChanges = (not b == self.d.edition_)

        if stateChanges and not self.d.editionStates_:
            self.d.editionStates_ = AQBoolFlagStateList()

        if not self.d.editionStates_:
            return

        i = self.d.editionStates_.find(m)
        if not i and stateChanges:
            i = AQBoolFlagState()
            i. modifier_ = m
            i.prevValue_ = self.d.edition_
            self.d.editionStates_.append(i)
        elif i:
            if stateChanges:
                self.d.editionStates_.pushOnTop(i)
                i.prevValue_ = self.d.edition_
            else:
                self.d.editionStates_.erase(i)

        if stateChanges:
            self.d.edition_ = b

    def restoreEditionFlag(self, m):

        if not getattr(self.d, "editionStates_", None):
            return

        i = self.d.editionStates_.find(m)

        if i and i == self.d.editionStates_.cur_:
            self.d.edition_ = i.prevValue_

        if i:
            self.d.editionStates_.erase(i)

    """
    Establece el valor de FLSqlCursor::browse.

    @param b TRUE o FALSE
    """

    def setBrowse(self, b, m=None):
        if not m:
            self.d.browse_ = b
            return

        stateChanges = (not b == self.d.browse_)

        if stateChanges and not self.d.borwseStates_:
            self.d.browseStates_ = AQBoolFlagStateList()

        if not self.d.browseStates_:
            return

        i = self.d.browseStates_.find(m)
        if not i and stateChanges:
            i = AQBoolFlagState()
            i. modifier_ = m
            i.prevValue_ = self.d.browse_
            self.d.browseStates_.append(i)
        elif i:
            if stateChanges:
                self.d.browseStates_.pushOnTop(i)
                i.prevValue_ = self.d.browse_
            else:
                self.d.browseStates_.erase(i)

        if stateChanges:
            self.d.browse_ = b

    def restoreBrowseFlag(self, m):
        if not getattr(self.d, "browseStates_", None):
            return

        i = self.d.browseStates_.find(m)

        if i and i == self.d.browseStates_.cur_:
            self.d.browse_ = i.prevValue_

        if i:
            self.d.browseStates_.erase(i)

    """
    Establece el contexto de ejecución de scripts

    Ver FLSqlCursor::ctxt_.

    @param c Contexto de ejecucion
    """

    def setContext(self, c):
        if c:
            self.d.ctxt_ = weakref.ref(c)

    """
    Para obtener el contexto de ejecución de scripts.

    Ver FLSqlCursor::ctxt_.

    @return Contexto de ejecución
    """

    def context(self):
        if self.d.ctxt_:
            return self.d.ctxt_()
        else:
            logger.debug("%s.context(). No hay contexto" % self.curName())
            return None

    """
    Dice si un campo está deshabilitado.

    Un campo estará deshabilitado, porque esta clase le dará un valor automáticamente.
    Estos campos son los que están en una relación con otro cursor, por lo que
    su valor lo toman del campo foráneo con el que se relacionan.

    @param fN Nombre del campo a comprobar
    @return TRUE si está deshabilitado y FALSE en caso contrario
    """

    def fieldDisabled(self, fN):
        if self.d.modeAccess_ == self.Insert or self.d.modeAccess_ == self.Edit:
            if self.d.cursorRelation_ and self.d.relation_:
                if not self.d.cursorRelation_.metadata():
                    return False
                    if str(self.d.relation_.field()).lower() == str(fN).lower():
                        return True
                    else:
                        return False
            else:
                return False
        else:
            return False

    """
    Indica si hay una transaccion en curso.

    @return TRUE si hay una transaccion en curso, FALSE en caso contrario
    """

    def inTransaction(self):
        if self.d.db_:
            if self.d.db_.transaction_ > 0:
                return True
            else:
                return False

    """
    Inicia un nuevo nivel de transacción.

    Si ya hay una transacción en curso simula un nuevo nivel de anidamiento de
    transacción mediante un punto de salvaguarda.

    @param  lock Actualmente no se usa y no tiene ningún efecto. Se mantiene por compatibilidad hacia atrás
    @return TRUE si la operación tuvo exito
    """

    def transaction(self, lock=False):
        if not self.d.db_ and not self.d.db_.db():
            logger.warn("ransaction(): No hay conexión con la base de datos")
            return False

        return self.d.db_.doTransaction(self)

    """
    Deshace las operaciones de una transacción y la acaba.

    @return TRUE si la operación tuvo exito
    """

    def rollback(self):
        if not self.d.db_ and not self.d.db_.db():
            logger.warn("rollback(): No hay conexión con la base de datos")
            return False

        return self.d.db_.doRollback(self)

    """
    Hace efectiva la transacción y la acaba.

    @param notify Si TRUE emite la señal cursorUpdated y pone el cursor en modo BROWSE,
          si FALSE no hace ninguna de estas dos cosas y emite la señal de autoCommit
    @return TRUE si la operación tuvo exito
    """

    def commit(self, notify=True):
        if not self.d.db_ and not self.d.db_.db():
            logger.warn("commit(): No hay conexión con la base de datos")
            return False

        r = self.d.db_.doCommit(self, notify)
        if r:
            self.commited.emit()

        return r

    def size(self):
        return self.d._model.rowCount()

    """
    Abre el formulario asociado a la tabla origen en el modo indicado.

    @param m Modo de apertura (FLSqlCursor::Mode)
    @param cont Indica que se abra el formulario de edición de registros con el botón de
         aceptar y continuar
    """

    def openFormInMode(self, m, cont=True):
        if not self.d.metadata_:
            return
        # util = FLUtil()
        if (not self.isValid() or self.size() <= 0) and not m == self.Insert:
            if not self.size():
                QtWidgets.QMessageBox.warning(QtWidgets.QApplication.focusWidget(), self.tr(
                    "Aviso"), self.tr("No hay ningún registro seleccionado"))
                return
            self.first()

        if m == self.Del:
            res = QtWidgets.QMessageBox.warning(QtWidgets.QApplication.focusWidget(), self.tr("Aviso"), self.tr(
                "El registro activo será borrado. ¿ Está seguro ?"), QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.No)
            if res == QtWidgets.QMessageBox.No:
                return

            self.transaction()
            self.d.modeAccess_ = self.Del
            if not self.refreshBuffer():
                self.commit()
            else:
                if not self.commitBuffer():
                    self.rollback()
                else:
                    self.commit()

            return

        self.d.modeAccess_ = m
        if self.d.buffer_:
            self.d.buffer_.clearValues(True)

        # if not self.d._action:
            # self.d.action_ = self.d.db_.manager().action(self.metadata().name())

        if not self._action:
            logger.warn("Para poder abrir un registro de edición se necesita una acción asociada al cursor, "
                        "o una acción definida con el mismo nombre que la tabla de la que procede el cursor.")
            return

        if not self._action.formRecord():
            QtWidgets.QMessageBox.warning(QtWidgets.QApplication.focusWidget(), self.tr("Aviso"), self.tr(
                "No hay definido ningún formulario para manejar\nregistros de esta tabla : %s" % self.curName()))
            return

        if self.refreshBuffer():  # Hace doTransaction antes de abrir formulario y crear savepoint
            if m != self.Insert:
                self.updateBufferCopy()

            self._action.openDefaultFormRecord(self)
            # if m != self.Insert and self.refreshBuffer():
            #     self.updateBufferCopy()

    def isNull(self, fN):
        return self.d.buffer_.isNull(fN)

    """
    Copia el contenido del FLSqlCursor::buffer_ actual en FLSqlCursor::bufferCopy_.

    Al realizar esta copia se podra comprobar posteriormente si el buffer actual y la copia realizada
    difieren mediante el metodo FLSqlCursor::isModifiedBuffer().
    """

    def updateBufferCopy(self):
        if not self.d.buffer_:
            return None

        self.d.bufferCopy_ = PNBuffer(self)
        for field in self.d.buffer_.fieldsList():
            self.d.bufferCopy_.setValue(
                field.name, self.d.buffer_.value(field.name), False)

    """
    Indica si el contenido actual del buffer difiere de la copia guardada.

    Ver FLSqlCursor::bufferCopy_ .

    @return TRUE si el buffer y la copia son distintas, FALSE en caso contrario
    """

    def isModifiedBuffer(self):
        if not self.d.buffer_:
            return False

        modifiedFields = self.d.buffer_.modifiedFields()
        if modifiedFields:
            return True
        else:
            return False

    """
    Establece el valor de FLSqlCursor::askForCancelChanges_ .

    @param a Valor a establecer (TRUE o FALSE)
    """

    def setAskForCancelChanges(self, a):
        self.d.askForCancelChanges_ = a

    """
    Activa o desactiva los chequeos de integridad referencial.

    @param a TRUE los activa y FALSE los desactiva
    """

    def setActivatedCheckIntegrity(self, a):
        self.d.activatedCheckIntegrity_ = a

    def activatedCheckIntegrity(self):
        return self.d.activatedCheckIntegrity_

    """
    Activa o desactiva las acciones a realizar antes y después de un commit

    @param a TRUE las activa y FALSE las desactiva
    """

    def setActivatedCommitActions(self, a):
        self.d.activatedCommitActions_ = a

    def activatedCommitActions(self):
        return self.d.activatedCommitActions_

    """
    Se comprueba la integridad referencial al intentar borrar, tambien se comprueba la no duplicidad de
    claves primarias y si hay nulos en campos que no lo permiten cuando se inserta o se edita.
    Si alguna comprobacion falla devuelve un mensaje describiendo el fallo.
    """

    def msgCheckIntegrity(self):
        msg = ""
        if not self.d.buffer_ or not self.d.metadata_:
            msg = "\nBuffer vacío o no hay metadatos"
            return msg

        if self.d.modeAccess_ == self.Insert or self.d.modeAccess_ == self.Edit:
            if not self.isModifiedBuffer() and self.d.modeAccess_ == self.Edit:
                return msg
            fieldList = self.metadata().fieldList()
            checkedCK = False

            if not fieldList:
                return msg

            for field in fieldList:

                fiName = field.name()
                if not self.d.buffer_.isGenerated(fiName):
                    continue

                s = None
                if not self.d.buffer_.isNull(fiName):
                    s = self.d.buffer_.value(fiName)

                fMD = field.associatedField()
                if fMD and s is not None:
                    if not field.relationM1():
                        # msg = msg + "\n" + (FLUtil.tr(
                        #       "FLSqlCursor : Error en metadatos, el campo %1 tiene un campo asociado pero no existe relación muchos a uno"
                        #       ).arg(self.d.metadata_.name()) + ":" + fiName)
                        msg = msg + "\n" + \
                            "FLSqlCursor : Error en metadatos, el campo %s tiene un campo asociado pero no existe relación muchos a uno:%s" % (
                                self.d.metadata_.name(), fiName)
                        continue

                    r = field.relationM1()
                    if not r.checkIn():
                        continue
                    tMD = self.d.db_.manager().metadata(field.relationM1().foreignTable())
                    if not tMD:
                        continue
                    fmdName = fMD.name()
                    ss = None
                    if not self.d.buffer_.isNull(fmdName):
                        ss = self.d.buffer_.value(fmdName)
                        # if not ss:
                        #     ss = None
                    if ss:
                        filter = "%s AND %s" % (self.d.db_.manager().formatAssignValue(field.associatedFieldFilterTo(
                        ), fMD, ss, True), self.d.db_.manager().formatAssignValue(field.relationM1().foreignField(), field, s, True))
                        q = FLSqlQuery(None, self.d.db_.connectionName())
                        q.setTablesList(tMD.name())
                        q.setSelect(field.associatedFieldFilterTo())
                        q.setFrom(tMD.name())
                        q.setWhere(filter)
                        q.setForwardOnly(True)
                        q.exec_()
                        if not q.next():
                            # msg = msg + "\n" + self.d.metadata_.name() + ":" + field.alias() + FLUtil.tr(" : %1 no pertenece a %2").arg(s, ss)
                            msg = msg + "\n" + self.d.metadata_.name() + ":" + field.alias() + \
                                " : %s no pertenece a %s" % (s, ss)
                        else:
                            self.d.buffer_.setValue(fmdName, q.value(0))

                    else:
                        # msg = msg + "\n" + self.d.metadata_.name() + ":" + field.alias() + FLUtil.tr(" : %1 no se puede asociar a un valor NULO").arg(s)
                        msg = msg + "\n" + self.d.metadata_.name() + ":" + field.alias() + \
                            " : %s no se puede asociar a un valor NULO" % s
                    if not tMD.inCache():
                        del tMD

                if self.d.modeAccess_ == self.Edit:
                    if self.d.buffer_ and self.d.bufferCopy_:
                        if self.d.buffer_.value(fiName) == self.d.bufferCopy_.value(fiName):
                            continue

                if self.d.buffer_.isNull(fiName) and not field.allowNull() and not field.type() == FLFieldMetaData.Serial:
                    # msg = msg + "\n" + self.d.metadata_.name() + ":" + field.alias() + FLUtil.tr(" : No puede ser nulo")
                    msg = msg + "\n" + self.d.metadata_.name() + ":" + field.alias() + \
                        " : No puede ser nulo"

                if field.isUnique():
                    pK = self.d.metadata_.primaryKey()
                    if not self.d.buffer_.isNull(pK) and s is not None:
                        pKV = self.d.buffer_.value(pK)
                        q = FLSqlQuery(None, self.d.db_.connectionName())
                        q.setTablesList(self.d.metadata_.name())
                        q.setSelect(fiName)
                        q.setFrom(self.d.metadata_.name())
                        q.setWhere("%s AND %s <> %s" % (self.d.db_.manager().formatAssignValue(field, s, True), self.d.metadata_.primaryKey(
                            self.d.isQuery_), self.d.db_.manager().formatValue(self.d.metadata_.fieldType(pK), pKV)))
                        q.setForwardOnly(True)
                        q.exec_()
                        if (q.next()):
                            # msg = (msg + "\n" + self.d.metadata_.name() + ":" + field.alias()
                            #       + FLUtil.tr(" : Requiere valores únicos, y ya hay otro registro con el valor %1 en este campo").arg(str(s)))
                            msg = msg + "\n" + self.d.metadata_.name() + ":" + field.alias() + \
                                " : Requiere valores únicos, y ya hay otro registro con el valor %s en este campo" % s

                if field.isPrimaryKey() and self.d.modeAccess_ == self.Insert and s is not None:
                    q = FLSqlQuery(None, self.d.db_.connectionName())
                    q.setTablesList(self.d.metadata_.name())
                    q.setSelect(fiName)
                    q.setFrom(self.d.metadata_.name())
                    q.setWhere(
                        self.d.db_.manager().formatAssignValue(field, s, True))
                    q.setForwardOnly(True)
                    q.exec_()
                    if q.next():
                        # msg = msg + "\n" + self.d.metadata_.name() + ":" + field.alias() + FLUtil.tr(
                        #       " : Es clave primaria y requiere valores únicos, y ya hay otro registro con el valor %1 en este campo").arg(str(s))
                        msg = msg + "\n" + self.d.metadata_.name() + ":" + field.alias() + \
                            " : Es clave primaria y requiere valores únicos, y ya hay otro registro con el valor %s en este campo" % s

                if field.relationM1() and s:
                    if field.relationM1().checkIn() and not field.relationM1().foreignTable() == self.d.metadata_.name():
                        r = field.relationM1()
                        tMD = self.d.db_.manager().metadata(r.foreignTable())
                        if not tMD:
                            continue
                        q = FLSqlQuery(None, self.d.db_.connectionName())
                        q.setTablesList(tMD.name())
                        q.setSelect(r.foreignField())
                        q.setFrom(tMD.name())
                        q.setWhere(self.d.db_.manager().formatAssignValue(
                            r.foreignField(), field, s, True))
                        q.setForwardOnly(True)
                        logger.debug("SQL linea = %s conn name = %s", q.sql(), str(pineboolib.project.conn.connectionName()))
                        q.exec_()
                        if not q.next():
                            # msg = msg + "\n" + self.d.metadata_.name() + ":" + field.alias() +
                            #           FLUtil.tr(" : El valor %1 no existe en la tabla %2").arg(str(s), r.foreignTable())
                            msg = msg + "\n" + self.d.metadata_.name() + ":" + field.alias() + \
                                " : El valor %s no existe en la tabla %s" % (
                                    s, r.foreignTable())
                        else:
                            self.d.buffer_.setValue(fiName, q.value(0))

                        if not tMD.inCache():
                            del tMD

                fieldListCK = self.metadata().fieldListOfCompoundKey(fiName)
                if fieldListCK and not checkedCK and self.d.modeAccess_ == self.Insert:
                    if fieldListCK:
                        filter = None
                        field = None
                        valuesFields = None
                        for fieldCK in fieldListCK:
                            sCK = self.d.buffer_.value(fieldCK.name())
                            if filter is None:
                                filter = self.d.db_.manager().formatAssignValue(fieldCK, sCK, True)
                            else:
                                filter = "%s AND %s" % (
                                    filter, self.d.db_.manager().formatAssignValue(fieldCK, sCK, True))
                            if field is None:
                                field = fieldCK.alias()
                            else:
                                field = "%s+%s" % (field, fieldCK.alias())
                            if valuesFields is None:
                                valuesFields = str(sCK)
                            else:
                                valuesFields = "%s+%s" % (valuesFields,
                                                          str(sCK))

                        q = FLSqlQuery(None, self.d.db_.connectionName())
                        q.setTablesList(self.d.metadata_.name())
                        q.setSelect(fiName)
                        q.setFrom(self.d.metadata_.name())
                        q.setWhere(filter)
                        q.setForwardOnly(True)
                        q.exec_()
                        if q.next():
                            # msg = msg + "\n" + fields + FLUtil.tr(" : Requiere valor único, y ya hay otro registro con el valor %1").arg(valuesFields)
                            msg = msg + \
                                "\n%s : Requiere valor único, y ya hay otro registro con el valor %s" % (
                                    field, valuesFields)

                        checkedCK = True

        elif self.d.modeAccess_ == self.Del:
            fieldList = self.d.metadata_.fieldList()
            fiName = None
            s = None

            for field in fieldList:
                # fiName = field.name()
                if not self.d.buffer_.isGenerated(field.name()):
                    continue

                s = None

                if not self.d.buffer_.isNull(field.name()):
                    s = self.d.buffer_.value(field.name())
                    # if s:
                    #    s = None

                if s is None:
                    continue

                relationList = field.relationList()

                if not relationList:
                    continue

                if relationList:
                    for r in relationList:
                        if not r.checkIn():
                            continue
                        mtd = self.d.db_.manager().metadata(r.foreignTable())
                        if not mtd:
                            continue
                        f = mtd.field(r.foreignField())
                        if f:
                            if f.relationM1():
                                if f.relationM1().deleteCascade():
                                    if not mtd.inCache():
                                        del mtd
                                    continue
                                if not f.relationM1().checkIn():
                                    if not mtd.inCache():
                                        del mtd
                                    continue
                            else:
                                if not mtd.inCache():
                                    del mtd
                                continue

                        else:
                            # msg = msg + "\n" + FLUtil.tr("FLSqlCursor : Error en metadatos, %1.%2 no es válido.\nCampo relacionado con %3.%4."
                            #           ).arg(mtd.name(), r.foreignField(), self.d.metadata_.name(), field.name())
                            msg = msg + "\n" + "FLSqlCursor : Error en metadatos, %s.%s no es válido.\nCampo relacionado con %s.%s." % (
                                mtd.name(), r.foreignField(), self.d.metadata_.name(), field.name())
                            if not mtd.inCache():
                                del mtd
                            continue

                        q = FLSqlQuery(None, self.d.db_.connectionName())
                        q.setTablesList(mtd.name())
                        q.setSelect(r.foreignField())
                        q.setFrom(mtd.name())
                        q.setWhere(self.d.db_.manager().formatAssignValue(
                            r.foreignField(), field, s, True))
                        q.setForwardOnly(True)
                        q.exec_()
                        if q.next():
                            # msg = msg + "\n" + self.d.metadata_.name() + ":" + field.alias() +
                            #           FLUtil.tr(" : Con el valor %1 hay registros en la tabla %2:%3").arg(str(s), mtd.name(), mtd.alias())
                            msg = msg + "\n" + self.d.metadata_.name() + ":" + field.alias() + \
                                " : Con el valor %s hay registros en la tabla %s:%s" % (
                                    s, mtd.name(), mtd.alias())

                        if not mtd.inCache():
                            del mtd

        return msg

    """
    Realiza comprobaciones de intregidad.

    Se comprueba la integridad referencial al intentar borrar, tambien se comprueba la no duplicidad de
    claves primarias y si hay nulos en campos que no lo permiten cuando se inserta o se edita.
    Si alguna comprobacion falla muestra un cuadro de diálogo con el tipo de fallo encontrado y el metodo
    devuelve FALSE.

    @param showError Si es TRUE muestra el cuadro de dialogo con el error que se produce al no
           pasar las comprobaciones de integridad
    @return TRUE si se ha podido entregar el buffer al cursor, y FALSE si ha fallado alguna comprobacion
      de integridad
    """

    def checkIntegrity(self, showError=True):
        if not self.d.buffer_ or not self.d.metadata_:
            return False
        if not self.d.activatedCheckIntegrity_:
            return True
        msg = self.msgCheckIntegrity()
        if msg:
            if showError:
                if self.d.modeAccess_ == self.Insert or self.d.modeAccess_ == self.Edit:
                    # self.d.msgBoxWarning(FLUtil.tr("No se puede validad el registro actual:\n") + msg)
                    self.d.msgBoxWarning(
                        "No se puede validad el registro actual:\n" + msg)
                elif self.d.modeAccess_ == self.Del:
                    # self.d.msgBoxWarning(FLUtil.tr("No se puede borrar registro:\n") + msg)
                    self.d.msgBoxWarning(
                        "No se puede borrar registro:\n" + msg)
            return False
        return True

    """
    Devuelve el cursor relacionado con este.
    """

    def cursorRelation(self):
        return self.d.cursorRelation_

    def relation(self):
        return self.d.relation_

    """
    Desbloquea el registro actual del cursor.

    @param fN Nombre del campo
    @param v Valor para el campo unlock
    """

    def setUnLock(self, fN, v):
        if not self.metadata() or not self.modeAccess() == self.Browse:
            return
        if not self.metadata().fieldType(fN) == FLFieldMetaData.Unlock:
            logger.warn("setUnLock sólo permite modificar campos del tipo Unlock")
            return
        self.d.buffer_ = self.primeUpdate()
        self.setModeAccess(self.Edit)
        self.d.buffer_.setValue(fN, v)
        self.update()
        self.refreshBuffer()

    """
    Para comprobar si el registro actual del cursor está bloqueado.

    @return TRUE si está bloqueado, FALSE en caso contrario.
    """

    def isLocked(self):
        if not self.d.modeAccess_ == self.Insert and self.fieldsNamesUnlock_ and self.d.buffer_ and self.d.buffer_.value(self.d.metadata_.primaryKey()):
            for field in self.fieldsNamesUnlock_:
                if self.d.buffer_.value(field) is False:
                    return True

        return False

    """
    Devuelve el contenido del buffer
    """

    def buffer(self):
        if self.d.buffer_:
            return self.d.buffer_
        else:
            return None

    """
    Devuelve el contenido del bufferCopy
    """

    def bufferCopy(self):
        if self.d.bufferCopy_:
            return self.d.bufferCopy_
        else:
            return None

    """
    Devuelve si el contenido de un campo en el buffer es nulo.

    @param pos_or_name Nombre o pos del campo en el buffer
    """

    def bufferIsNull(self, pos_or_name):

        if self.d.buffer_:
            return self.d.buffer_.isNull(pos_or_name)
        return True

    """
    Establece que el contenido de un campo en el buffer sea nulo.

    @param pos_or_name Nombre o pos del campo en el buffer
    """

    def bufferSetNull(self, pos_or_name):

        if self.d.buffer_:
            self.d.buffer_.setNull(pos_or_name)

    """
    Devuelve si el contenido de un campo en el bufferCopy en nulo.

    @param pos_or_name Nombre o pos del campo en el bufferCopy
    """

    def bufferCopyIsNull(self, pos_or_name):

        if self.d.bufferCopy_:
            return self.d.bufferCopy_.isNull(pos_or_name)
        return True

    """
    Establece que el contenido de un campo en el bufferCopy sea nulo.

    @param pos_or_name Nombre o pos del campo en el bufferCopy
    """

    def bufferCopySetNull(self, pos_or_name):

        if self.d.bufferCopy_:
            self.d.bufferCopy_.setNull(pos_or_name)

    """
    Obtiene la posición del registro actual, según la clave primaria contenida en el buffer.

    La posición del registro actual dentro del cursor se calcula teniendo en cuenta el
    filtro actual ( FLSqlCursor::curFilter() ) y el campo o campos de ordenamiento
    del mismo ( QSqlCursor::sort() ).
    Este método es útil, por ejemplo, para saber en que posición dentro del cursor
    se ha insertado un registro.

    @return Posición del registro dentro del cursor, o 0 si no encuentra coincidencia.
    """

    def atFrom(self):
        if not self.d.buffer_ or not self.d.metadata_:
            return 0

        pKN = self.d.metadata_.primaryKey()
        pKValue = self.valueBuffer(pKN)

        pos = -99

        if pos == -99:
            # q = FLSqlQuery(None, self.d.db_.db()) FIXME
            # q = FLSqlQuery()
            q = FLSqlQuery(None, self.d.db_.connectionName())
            sql = self.curFilter()
            sqlIn = self.curFilter()
            cFilter = self.curFilter()
            field = self.d.metadata_.field(pKN)

            sqlPriKey = None
            sqlFrom = None
            sqlWhere = None
            sqlPriKeyValue = None
            sqlOrderBy = None

            if not self.d.isQuery_ or "." in pKN:
                sqlPriKey = pKN
                sqlFrom = self.d.metadata_.name()
                sql = "SELECT %s FROM %s" % (sqlPriKey, sqlFrom)
            else:
                qry = self.d.db_.manager().query(self.d.metadata_.query(), self)
                if qry:
                    sqlPriKey = "%s.%s" % (self.d.metadata_.name(), pKN)
                    sqlFrom = qry.from_()
                    sql = "SELECT %s FROM %s" % (sqlPriKey, sqlFrom)
                    del qry
                else:
                    logger.error("atFrom Error al crear la consulta")
                    self.seek(self.at())
                    if self.isValid():
                        pos = self.at()
                    else:
                        pos = 0
                    return pos

            if cFilter:
                sqlWhere = cFilter
                sql = "%s WHERE %s" % (sql, sqlWhere)
            else:
                sqlWhere = "1=1"

            if field:
                sqlPriKeyValue = self.d.db_.manager().formatAssignValue(field, pKValue, True)
                if cFilter:
                    sqlIn = "%s AND %s" % (sql, sqlPriKeyValue)
                else:
                    sqlIn = "%s WHERE %s" % (sql, sqlPriKeyValue)
                # q.exec_(self.d.db_, sqlIn)
                q.exec_(sqlIn)
                if not q.next():
                    self.seek(self.at())
                    if self.isValid():
                        pos = self.at()
                    else:
                        pos = 0
                    return pos

            if self.d.isQuery_ and self.d.queryOrderBy_:
                sqlOrderBy = self.d.queryOrderBy_
                sql = "%s ORDERBY %s" % (sql, sqlOrderBy)
            elif self.sort() and len(self.sort()) > 0:
                sqlOrderBy = self.sort()
                sql = "%s ORDERBY %s" % (sql, sqlOrderBy)

            # FIXME: solo compatible con PostgreSQL!
            # if sqlPriKeyValue and self.d.db_.canOverPartition():
            #     posEqual = sqlPriKeyValue.index("=")
            #     leftSqlPriKey = sqlPriKeyValue[0:posEqual]
            #     # sqlRowNum = (
            #     #     "SELECT rownum FROM ("
            #     #     "SELECT row_number() OVER (ORDER BY %s) as rownum, %s as %s FROM %s WHERE %s ORDER BY %s) as subnumrow where"
            #     #     % (sqlOrderBy, sqlPriKey, leftSqlPriKey, sqlFrom, sqlWhere, sqlOrderBy))
            #     # if q.exec_(sqlRowNum) and q.next():
            #     #     pos = int(q.value(0)) - 1
            #     #     if pos >= 0:
            #     #         return pos

            found = False
            q.exec_(sql)

            pos = 0
            if q.first():
                if not q.value(0) == pKValue:
                    pos = q.size()
                    if q.last() and pos > 1:
                        pos = pos - 1
                        if not q.value(0) == pKValue:
                            while q.prev() and pos > 1:
                                pos = pos - 1
                                if q.value(0) == pKValue:
                                    found = True
                                    break

                        else:
                            found = True

                    else:
                        found = True

            if not found:
                self.seek(self.at())
                if self.isValid():
                    pos = self.at()
                else:
                    pos = 0

        return pos

    """
    Obtiene la posición dentro del cursor del primer registro que en el campo indicado
    empieze con el valor solicitado. Supone que los registros están ordenados por dicho
    campo, para realizar una búsqueda binaria.

    La posición del registro actual dentro del cursor se calcula teniendo en cuenta el
    filtro actual ( FLSqlCursor::curFilter() ) y el campo o campos de ordenamiento
    del mismo ( QSqlCursor::sort() ).
    Este método es útil, por ejemplo, para saber en que posición dentro del cursor
    se encuentra un registro con un cierto valor en un campo.

    @param  fN  Nombre del campo en el que buscar el valor
    @param  v   Valor a buscar ( mediante like 'v%' )
    @param  orderAsc TRUE (por defecto) si el orden es ascendente, FALSE si es descendente
    @return Posición del registro dentro del cursor, o 0 si no encuentra coincidencia.
    """
    def atFromBinarySearch(self, fN, v, orderAsc=True):

        ret = -1
        ini = 0
        fin = self.size() - 1
        mid = None
        comp = None
        midVal = None

        while ini <= fin:
            mid = int((ini + fin) / 2)
            midVal = str(self.model().value(mid, fN))
            if v == midVal:
                ret = mid
                break

            if orderAsc:
                comp = v < midVal
            else:
                comp = v > midVal

            if not comp:
                ini = mid + 1
            else:
                fin = mid - 1
            ret = ini

        return ret

    """
    Redefinido por conveniencia
    """
    @decorators.NotImplementedWarn
    def exec_(self, query):
        # if query:
        #    logger.debug("ejecutando consulta " + query)
        #    QSqlQuery.exec(self, query)

        return True

    def setNull(self, name):
        if self.d.buffer_.setNull(name):
            self.bufferChanged.emit(name)

    """
    Para obtener la base de datos sobre la que trabaja
    """

    def db(self):
        return self.d.db_

    """
    Para obtener el nombre del cursor (generalmente el nombre de la tabla)
    """

    def curName(self):
        return self.d.curName_

    """
    Para obtener el filtro por defecto en campos asociados

    @param  fieldName Nombre del campo que tiene campos asociados.
                    Debe ser el nombre de un campo de este cursor.
    @param  tableMD   Metadatos a utilizar como tabla foránea.
                    Si es cero usa la tabla foránea definida por la relación M1 de 'fieldName'
    """

    def filterAssoc(self, fieldName, tableMD=None):
        fieldName = fieldName

        mtd = self.d.metadata_
        if not mtd:
            return None

        field = mtd.field(fieldName)
        if not field:
            return None

        # ownTMD = False

        if not tableMD:
            # ownTMD = True
            tableMD = self.d.db_.manager().metadata(field.relationM1().foreignTable())

        if not tableMD:
            return None

        fieldAc = field.associatedField()
        if not fieldAc:
            # if ownTMD and not tableMD.inCache():
                # del tableMD
            return None

        fieldBy = field.associatedFieldFilterTo()

        if not self.buffer():
            return

        if not tableMD.field(fieldBy) or self.d.buffer_.isNull(fieldAc.name()):
            # if ownTMD and not tableMD.inCache():
                # del tableMD
            return None

        vv = self.d.buffer_.value(fieldAc.name())
        if vv:
            # if ownTMD and not tableMD.inCache():
                # del tableMD
            return self.d.db_.manager().formatAssignValue(fieldBy, fieldAc, vv, True)

        # if ownTMD and not tableMD.inCache():
            # del rableMD

        return None

    @decorators.BetaImplementation
    def aqWasDeleted(self):
        return False

    """
    Redefinida
    """
    @decorators.NotImplementedWarn
    def calculateField(self, name):
        return True

    """
    Redefinicion del método afterSeek() de QSqlCursor.
    """

    def afterSeek(self):
        self.d.doAcl()
        return True

    def model(self):
        return self.d._model

    def selection(self):
        return self._selection

    @QtCore.pyqtSlot(QtCore.QModelIndex, QtCore.QModelIndex)
    @QtCore.pyqtSlot(int, int)
    @QtCore.pyqtSlot(int)
    def selection_currentRowChanged(self, current, previous=None):
        if self.d._currentregister == current.row():
            return False
        self.d._currentregister = current.row()
        self.d._current_changed.emit(self.at())
        # agregado para que FLTableDB actualice el buffer al pulsar.
        self.refreshBuffer()
        logger.debug("cursor:%s , row:%s:: %s", self._action.table, self.d._currentregister, self)

    def selection_pk(self, value):

        if value is None:
            return False

        i = 0
        while i <= self.model().rowCount():
            if self.model().value(i, self.buffer().pK()) == value:
                return self.move(i)

            i = i + 1

        return False

    def at(self):
        if not self.d._currentregister:
            row = 0
        else:
            row = self.d._currentregister

        if row < 0:
            return -1
        if row >= self.model().rows:
            return -2
        # logger.debug("%s.Row %s ----> %s" % (self.curName(), row, self))
        return row

    def isValid(self):
        if self.at() >= 0:
            return True
        else:
            return False

    """
    public slots:
    """

    """
    Refresca el contenido del cursor.

    Si no se ha indicado cursor relacionado obtiene el cursor completo, segun la consulta
    por defecto. Si se ha indicado que depende de otro cursor con el que se relaciona,
    el contenido del cursor dependerá del valor del campo que determina la relación.
    Si se indica el nombre de un campo se considera que el buffer sólo ha cambiado en ese
    campo y así evitar repeticiones en el refresco.

    @param fN Nombre del campo de buffer que ha cambiado
    """
    @QtCore.pyqtSlot()
    @QtCore.pyqtSlot(str)
    def refresh(self, fN=None):
        if not self.d.metadata_:
            return

        if self.d.cursorRelation_ and self.d.relation_:
            self.d.persistentFilter_ = None
            if not self.d.cursorRelation_.metadata():
                return
            if self.d.cursorRelation_.metadata().primaryKey() == fN and self.d.cursorRelation_.modeAccess() == self.Insert:
                return

            if not fN or self.d.relation_.foreignField() == fN:
                self.refreshDelayed()
                return
        else:
            self.select()
            pos = self.atFrom()
            if pos > self.size():
                pos = self.size() - 1

            # if not self.seek(pos, False, True):
            #    self.d.buffer_ = None
            #    self.newBuffer.emit()
        self.afterSeek()

    """
    Actualiza el conjunto de registros con un retraso.

    Acepta un lapsus de tiempo en milisegundos, activando el cronómetro interno para
    que realize el refresh definitivo al cumplirse dicho lapsus.

    @param msec Cantidad de tiempo del lapsus, en milisegundos.
    """
    @QtCore.pyqtSlot()
    def refreshDelayed(self, msec=50):

        if self.d.buffer_ is not None:
            return

        # if not self._refreshDelayedTimer:
        #     time = QtCore.QTimer()
        #     time.singleShot(msec, self.refreshDelayed)
        #     self._refreshDelayedTimer = True
        #     return

        self._refreshDelayedTimer = False

        # if not self.d.timer_:
        #    return
        # self.d.timer_.start(msec)
        # cFilter = self.filter()
        # self.setFilter(None)
        # if cFilter == self.filter() and self.isValid():
        #    return

        self.select()
        pos = self.atFrom()
        if not self.seek(pos, False, True):
            self.newBuffer.emit()
        else:
            if self.d.cursorRelation_ and self.d.relation_ and self.d.cursorRelation_.metadata():
                v = self.valueBuffer(self.d.relation_.field())
                foreignFieldValueBuffer = self.d.cursorRelation_.valueBuffer(
                    self.d.relation_.foreignField())
                if (foreignFieldValueBuffer != v and foreignFieldValueBuffer is not None):
                    self.d.cursorRelation_.setValueBuffer(
                        self.d.relation_.foreignField(), v)

    def primeInsert(self):
        if not self.buffer():
            self.d.buffer_ = PNBuffer(self)

        self.buffer().primeInsert()

    def primeUpdate(self):
        if not self.buffer():
            self.d.buffer_ = PNBuffer(self)

        self.buffer().primeUpdate(self.at())
        return self.buffer()

    def editBuffer(self, b=None):
        # if not self.d.buffer_:
            # self.d.buffer_ = PNBuffer(self.d)
        return self.primeUpdate()

    """
    Refresca el buffer segun el modo de acceso establecido.

    Lleva informacion del cursor al buffer para editar o navegar, o prepara el buffer para
    insertar o borrar.

    Si existe un campo contador se invoca a la función "calculateCounter" del script del
    contexto (ver FLSqlCursor::ctxt_) establecido para el cursor. A esta función se le pasa
    como argumento el nombre del campo contador y debe devolver el valor que debe contener
    ese campo.

    @return TRUE si se ha podido realizar el refresco, FALSE en caso contrario
    """
    @QtCore.pyqtSlot()
    def refreshBuffer(self):
        if not self.d.metadata_:
            return False

        if not self.isValid() and not self.d.modeAccess_ == self.Insert:
            return False

        if self.d.modeAccess_ == self.Insert:

            if not self.commitBufferCursorRelation():
                return False

            if not self.d.buffer_:
                self.d.buffer_ = PNBuffer(self)
            self.setNotGenerateds()

            fieldList = self.metadata().fieldList()
            if fieldList:
                for field in fieldList:
                    fiName = field.name()
                    self.d.buffer_.setNull(fiName)
                    if not self.d.buffer_.isGenerated(fiName):
                        continue
                    type_ = field.type()
                    # fltype = FLFieldMetaData.flDecodeType(type_)
                    # fltype = self.metadata().field(fiName).flDecodeType(type_)
                    defVal = field.defaultValue()
                    if defVal:
                        # defVal.cast(fltype)
                        self.d.buffer_.setValue(fiName, defVal)

                    if type_ == "serial":
                        self.d.buffer_.setValue(fiName, "%u" % self.d.db_.nextSerialVal(
                            self.d.metadata_.name(), fiName))

                    if field.isCounter():
                        siguiente = None
                        try:
                            # siguiente = self.context().calculateCounter()
                            functionCounter = self.actionName() + ".widget.calculateCounter"
                            siguiente = self._prj.call(functionCounter, None, self.context(), True)
                        except Exception:
                            util = FLUtil()
                            siguiente = util.nextCounter(
                                field.name(), self)

                        if siguiente:
                            self.d.buffer_.setValue(
                                field.name(), siguiente)

            if self.d.cursorRelation_ and self.d.relation_ and self.d.cursorRelation_.metadata():
                self.setValueBuffer(self.d.relation_.field(
                ), self.d.cursorRelation_.valueBuffer(self.d.relation_.foreignField()))

            self.d.undoAcl()
            self.updateBufferCopy()
            self.newBuffer.emit()

        elif self.d.modeAccess_ == self.Edit:
            if not self.commitBufferCursorRelation():
                return False

            if self.isLocked() and not self.d.acosCondName_:
                self.d.modeAccess_ = self.Browse

            # if not self.d.buffer_:
                # self.d.buffer_ = PNBuffer(self.d)

            self.primeUpdate()

            self.setNotGenerateds()
            self.updateBufferCopy()
            self.newBuffer.emit()

        elif self.d.modeAccess_ == self.Del:

            if self.isLocked():
                self.d.msgBoxWarning(
                    "Registro bloqueado, no se puede eliminar")
                self.d.modeAccess_ = self.Browse
                return False

            if self.d.buffer_:

                # self.d.buffer_.primeDelete()
                self.setNotGenerateds()
                self.updateBufferCopy()

        elif self.d.modeAccess_ == self.Browse:
            self.editBuffer(True)
            self.setNotGenerateds()
            self.newBuffer.emit()

        else:
            logger.error("refreshBuffer(). No hay definido modeAccess()")

        return True

    """
    Pasa el cursor a modo Edit

    @return True si el cursor está en modo Edit o estaba en modo Insert y ha pasado con éxito a modo Edit
    """
    @QtCore.pyqtSlot()
    def setEditMode(self):
        if self.d.modeAccess_ == self.Insert:
            if not self.commitBuffer():
                return False
            self.refresh()
            self.setModeAccess(self.Edit)
        elif self.d.modeAccess_ == self.Edit:
            return True

        return False

    """
    Redefinicion del método seek() de QSqlCursor.

    Este método simplemente invoca al método seek() original de QSqlCursor() y refresca
    el buffer con el metodo FLSqlCursor::refreshBuffer().

    @param emit Si TRUE emite la señal FLSqlCursor::currentChanged()
    """
    @QtCore.pyqtSlot()
    def seek(self, i, relative=None, emite=None):

        # if self.d.modeAccess_ == self.Del:
        #    return False

        b = False

        if self.buffer():
            b = True

        if b and emite:
            self.currentChanged.emit(self.at())

        if b:
            return self.refreshBuffer()

        # else:
            # logger.trace("FLSqlCursor.seek(): buffer principal =", self.d.buffer_.md5Sum())

        return False

    """
    Redefinicion del método next() de QSqlCursor.

    Este método simplemente invoca al método next() original de QSqlCursor() y refresca el
    buffer con el metodo FLSqlCursor::refreshBuffer().

    @param emit Si TRUE emite la señal FLSqlCursor::currentChanged()
    """
    @QtCore.pyqtSlot()
    @QtCore.pyqtSlot(bool)
    def next(self, emite=True):
        # if self.d.modeAccess_ == self.Del:
        #    return False

        b = self.moveby(1)
        if b and emite:
            self.d._current_changed.emit(self.at())

        if b:
            return self.refreshBuffer()

        return b

    def moveby(self, pos):
        if self.d._currentregister:
            pos += self.d._currentregister

        return self.move(pos)

    """
    Redefinicion del método prev() de QSqlCursor.

    Este método simplemente invoca al método prev() original de QSqlCursor() y refresca
    el buffer con el metodo FLSqlCursor::refreshBuffer().

    @param emit Si TRUE emite la señal FLSqlCursor::currentChanged()
    """
    @QtCore.pyqtSlot()
    @QtCore.pyqtSlot(bool)
    def prev(self, emite=True):
        # if self.d.modeAccess_ == self.Del:
        #    return False

        b = self.moveby(-1)

        if b and emite:
            self.d._current_changed.emit(self.at())

        if b:
            return self.refreshBuffer()

        return b

    """
    Mueve el cursor por la tabla:
    """

    def move(self, row):

        if not self.model():
            return False

        if row < 0:
            row = -1
        if row >= self.model().rows:
            row = self.model().rows
        if self.d._currentregister == row:
            return False
        topLeft = self.model().index(row, 0)
        bottomRight = self.model().index(row, self.model().cols - 1)
        new_selection = QtCore.QItemSelection(topLeft, bottomRight)
        self._selection.select(
            new_selection, QtCore.QItemSelectionModel.ClearAndSelect)
        self.d._currentregister = row
        # self.d._current_changed.emit(self.at())
        if row < self.model().rows and row >= 0:
            return True
        else:
            return False

    """
    Redefinicion del método first() de QSqlCursor.

    Este método simplemente invoca al método first() original de QSqlCursor() y refresca el
    buffer con el metodo FLSqlCursor::refreshBuffer().

    @param emit Si TRUE emite la señal FLSqlCursor::currentChanged()
    """

    @QtCore.pyqtSlot()
    @QtCore.pyqtSlot(bool)
    def first(self, emite=True):
        # if self.d.modeAccess_ == self.Del:
        #    return False
        if not self.d._currentregister == 0:
            b = self.move(0)
        else:
            b = True

        if b and emite:
            self.d._current_changed.emit(self.at())

        if b:
            return self.refreshBuffer()

        return b

    """
    Redefinicion del método last() de QSqlCursor.

    Este método simplemente invoca al método last() original de QSqlCursor() y refresca el
    buffer con el metodo FLSqlCursor::refreshBuffer().

    @param emit Si TRUE emite la señal FLSqlCursor::currentChanged()
    """
    @QtCore.pyqtSlot()
    @QtCore.pyqtSlot(bool)
    def last(self, emite=True):
        # if self.d.modeAccess_ == self.Del:
        #    return False

        b = self.move(self.d._model.rows - 1)

        if b and emite:
            self.d._current_changed.emit(self.at())

        if b:
            return self.refreshBuffer()

        return b

    """
    Redefinicion del método del() de QSqlCursor.

    Este método invoca al método del() original de QSqlCursor() y comprueba si hay borrado
    en cascada, en caso afirmativo borrar también los registros relacionados en cardinalidad 1M.
    """
    @QtCore.pyqtSlot()
    def __del__(self, invalidate=True):
        # logger.trace("FLSqlCursor(%s). Eliminando cursor" % self.curName(), self)
        # delMtd = None
        # if self.metadata():
        #     if not self.metadata().inCache():
        #         delMtd = True

        msg = None
        mtd = self.metadata()

        # FIXME: Pongo que tiene que haber mas de una trasaccion abierta
        if len(self.d.transactionsOpened_) > 0:
            logger.notice("FLSqlCursor(%s).Transacciones abiertas!! %s", self.curName(), self.d.transactionsOpened_)
            t = self.curName()
            if mtd:
                t = mtd.name()
            msg = ("Se han detectado transacciones no finalizadas en la última operación.\n"
                   "Se van a cancelar las transacciones pendientes.\n"
                   "Los últimos datos introducidos no han sido guardados, por favor\n"
                   "revise sus últimas acciones y repita las operaciones que no\n"
                   "se han guardado.\nSqlCursor::~SqlCursor: %s\n" % t)
            self.rollbackOpened(-1, msg)

        # self.d.countRefCursor = self.d.countRefCursor - 1     FIXME

    """
    Redefinicion del método select() de QSqlCursor
    """
    @QtCore.pyqtSlot()
    def select(self, _filter=None, sort=None):  # sort = QtCore.QSqlIndex()
        if not self.metadata():
            return False

        bFilter = self.baseFilter()
        finalFilter = bFilter

        if _filter:
            if bFilter:
                if _filter not in bFilter:
                    finalFilter = "%s AND %s" % (bFilter, _filter)
                else:
                    finalFilter = bFilter

            else:
                finalFilter = _filter

        if self.cursorRelation() and self.cursorRelation().modeAccess() == self.Insert and not self.curFilter():
            finalFilter = "1 = 0"

        if finalFilter:
            self.setFilter(finalFilter)

        self.model().refresh()
        self.d._currentregister = -1

        if self.cursorRelation() and self.modeAccess() == self.Browse:
            self.d._currentregister = self.atFrom()

        self.refreshBuffer()
        # if self.modeAccess() == self.Browse:
        #    self.d._currentregister = -1
        self.newBuffer.emit()

        return True

    """
    Redefinicion del método sort() de QSqlCursor
    """
    @QtCore.pyqtSlot()
    def setSort(self, sort):
        self.d.sort_ = sort

    """
    Obtiene el filtro base
    """
    @QtCore.pyqtSlot()
    def baseFilter(self):
        relationFilter = None
        finalFilter = ""

        if self.d.cursorRelation_ and self.d.relation_ and self.d.metadata_ and self.d.cursorRelation_.metadata():

            fgValue = self.d.cursorRelation_.valueBuffer(
                self.d.relation_.foreignField())
            field = self.d.metadata_.field(self.d.relation_.field())

            if fgValue is None:
                fgValue = ""

            if field and fgValue is not None:
                relationFilter = self.d.db_.manager().formatAssignValue(field, fgValue, True)
                filterAc = self.d.cursorRelation_.filterAssoc(
                    self.d.relation_.foreignField(), self.d.metadata_)

                if filterAc:
                    if not relationFilter:
                        relationFilter = filterAc
                    else:
                        relationFilter = "%s AND %s" % (
                            relationFilter, filterAc)

        if self.mainFilter():
            finalFilter = self.mainFilter()

        if relationFilter:
            if not finalFilter:
                finalFilter = relationFilter
            else:
                if relationFilter not in finalFilter:
                    finalFilter = "%s AND %s" % (finalFilter, relationFilter)

        if self.filter():
            if finalFilter and self.filter() not in finalFilter:
                finalFilter = "%s AND %s" % (finalFilter, self.filter())
            else:
                finalFilter = self.filter()

        return finalFilter

    """
    Obtiene el filtro actual
    """
    @QtCore.pyqtSlot()
    def curFilter(self):
        f = self.filter()
        bFilter = self.baseFilter()
        if f:
            while f.endswith(";"):
                f = f[0:len(f) - 1]

        if not bFilter:
            return f
        else:
            if not f or f in bFilter:
                return bFilter
            else:
                if bFilter in f:
                    return f
                else:
                    return "%s aND %s" % (bFilter, f)

    """
    Redefinicion del método setFilter() de QSqlCursor
    """
    @QtCore.pyqtSlot()
    def setFilter(self, _filter):

        self.d.filter_ = None

        finalFilter = _filter
        bFilter = self.baseFilter()
        if bFilter:
            if not finalFilter:
                finalFilter = bFilter
            elif finalFilter in bFilter:
                finalFilter = bFilter
            elif bFilter not in finalFilter:
                finalFilter = bFilter + " AND " + finalFilter

        if finalFilter and self.d.persistentFilter_ and self.d.persistentFilter_ not in finalFilter:
            finalFilter = finalFilter + " OR " + self.d.persistentFilter_

        self.d._model.where_filters["filter"] = finalFilter

    """
    Abre el formulario de edicion de registro definido en los metadatos (FLTableMetaData) listo
    para insertar un nuevo registro en el cursor.
    """
    @QtCore.pyqtSlot()
    def insertRecord(self):
        logger.trace("insertRecord %s", self._action.name)
        self.openFormInMode(self.Insert)

    """
    Abre el formulario de edicion de registro definido en los metadatos (FLTableMetaData) listo
    para editar el registro activo del cursor.
    """
    @QtCore.pyqtSlot()
    def editRecord(self):
        logger.trace("editRecord %s", self.actionName())
        if self.d.needUpdate():
            pKN = self.d.metadata_.primaryKey()
            pKValue = self.valueBuffer(pKN)
            self.refresh()
            pos = self.atFromBinarySearch(pKN, pKValue)
            if not pos == self.at():
                self.seek(pos, False, False)

        self.openFormInMode(self.Edit)

    """
    Abre el formulario de edicion de registro definido en los metadatos (FLTableMetaData) listo
    para sólo visualizar el registro activo del cursor.
    """
    @QtCore.pyqtSlot()
    def browseRecord(self):
        logger.trace("browseRecord %s", self.actionName())
        if self.d.needUpdate():
            pKN = self.d.metadata_.primaryKey()
            pKValue = self.valueBuffer(pKN)
            self.refresh()
            pos = self.atFromBinarySearch(pKN, pKValue)
            if not pos == self.at():
                self.seek(pos, False, False)
        self.openFormInMode(self.Browse)

    """
    Borra, pidiendo confirmacion, el registro activo del cursor.
    """
    @QtCore.pyqtSlot()
    def deleteRecord(self):
        logger.trace("deleteRecord", self.actionName())
        self.openFormInMode(self.Del)
        # self.d._action.openDefaultFormRecord(self)

    """
    Realiza la accion de insertar un nuevo registro, y copia el valor de los campos del registro
    actual.
    """

    def copyRecord(self):
        return True

    """
    Realiza la acción asociada a elegir un registro del cursor, por defecto se abre el formulario de
    edición de registro,llamando al método FLSqlCursor::editRecord(), si la bandera FLSqlCursor::edition
    indica TRUE, si indica FALSE este método no hace nada
    """
    @QtCore.pyqtSlot()
    @decorators.NotImplementedWarn
    def chooseRecord(self):
        return True

    """
    Manda el contenido del buffer al cursor, o realiza la acción oportuna para el cursor.

    Todos los cambios realizados en el buffer se hacen efectivos en el cursor al invocar este método.
    La manera de efectuar estos cambios viene determinada por el modo de acceso establecido para
    el cursor, ver FLSqlCursor::Mode, si el modo es editar o insertar actualiza con los nuevos valores de
    los campos del registro, si el modo es borrar borra el registro, y si el modo es navegacion no hace nada.
    Antes de nada tambien comprueba la integridad referencial invocando al método FLSqlCursor::checkIntegrity().

    Si existe un campo calculado se invoca a la función "calculateField" del script del
    contexto (ver FLSqlCursor::ctxt_) establecido para el cursor. A esta función se le pasa
    como argumento el nombre del campo calculado y debe devolver el valor que debe contener
    ese campo, p.e. si el campo es el total de una factura y de tipo calculado la función
    "calculateField" debe devolver la suma de lineas de las facturas mas/menos impuestos y
    descuentos.

    @param  emite       True para emitir señal cursorUpdated
    @param  checkLocks  True para comprobar riesgos de bloqueos para esta tabla y el registro actual
    @return TRUE si se ha podido entregar el buffer al cursor, y FALSE si ha fallado la entrega
    """

    @QtCore.pyqtSlot()
    def commitBuffer(self, emite=True, checkLocks=False):
        if not self.d.buffer_ or not self.d.metadata_:
            return False

        if self.d.db_.interactiveGUI() and self.d.db_.canDetectLocks() and (checkLocks or self.d.metadata_.detectLocks()):
            self.checkRisksLocks()
            if self.d.inRisksLocks_:
                ret = QtWidgets.QMessageBox.warning(
                    None, "Bloqueo inminente",
                    "Los registros que va a modificar están bloqueados actualmente.\n"
                    "Si continua hay riesgo de que su conexión quede congelada hasta finalizar el bloqueo.\n"
                    "\n¿ Desa continuar aunque exista riesgo de bloqueo ?",
                    QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.No | QtWidgets.QMessageBox.Default | QtWidgets.QMessageBox.Escape)
                if ret == QtWidgets.QMessageBox.No:
                    return False

        if not self.checkIntegrity():
            return False

        fieldNameCheck = None

        if self.d.modeAccess_ == self.Edit or self.d.modeAccess_ == self.Insert:
            fieldList = self.d.metadata_.fieldList()

            for field in fieldList:
                if field.isCheck():
                    fieldNameCheck = field.name()
                    self.d.buffer_.setGenerated(fieldNameCheck, False)
                    if self.d.bufferCopy_:
                        self.d.bufferCopy_.setGenerated(fieldNameCheck, False)
                    continue

                if not self.d.buffer_.isGenerated(field.name()):
                    continue

                if self.context() and field.calculated():
                    v = None
                    try:
                        v = self.d.ctxt_().calculateField(field.name())
                        # v = self.
                    except Exception:
                        logger.exception("commitBuffer(): Campo calculado %s, pero no se ha calculado nada", field.name())

                    if v:
                        self.setValueBuffer(field.name(), v)

        functionBefore = None
        functionAfter = None
        if not self.d.modeAccess_ == FLSqlCursor.Browse and self.d.activatedCommitActions_:
            idMod = self.d.db_.managerModules().idModuleOfFile(
                "%s.%s" % (self.d.metadata_.name(), "mtd"))

            if idMod:
                functionBefore = "%s.iface.beforeCommit_%s" % (
                    idMod, self.d.metadata_.name())
                functionAfter = "%s.iface.afterCommit_%s" % (
                    idMod, self.d.metadata_.name())
            else:
                functionBefore = "sys.iface.beforeCommit_%s" % self.d.metadata_.name()
                functionAfter = "sys.iface.afterCommit_%s" % self.d.metadata_.name()

            if functionBefore:
                cI = self.context()
                v = self._prj.call(functionBefore, [self], cI, True)
                if v and not isinstance(v, bool):
                    return False

        # if not self.checkIntegrity():
        #    return False

        pKN = self.d.metadata_.primaryKey()
        updated = False
        savePoint = None
        if self.d.modeAccess_ == self.Insert:
            if self.d.cursorRelation_ and self.d.relation_:
                if self.d.cursorRelation_.metadata() and self.d.cursorRelation_.valueBuffer(self.d.relation_.foreignField()):
                    self.setValueBuffer(self.d.relation_.field(
                    ), self.d.cursorRelation_.valueBuffer(self.d.relation_.foreignField()))
                    self.d.cursorRelation_.setAskForCancelChanges(True)

            # pkWhere = self.d.db_.manager().formatAssignValue(self.d.metadata_.field(pKN), self.valueBuffer(pKN))
            self.model().Insert(self)
            # self.update(False)
            self.selection_pk(self.buffer().value(self.buffer().pK()))

            # if not self.d.persistentFilter_:
            #    self.d.persistentFilter_ = pkWhere
            # else:
            #    if not pkWhere in self.d.persistentFilter_:
            #        self.dl.persistentFilter_ = "%s OR %s" % (self.d.persistentFilter_, pkWhere)

            updated = True

        elif self.d.modeAccess_ == self.Edit:
            if not self.d.db_.canSavePoint():
                if self.d.db_.currentSavePoint_:
                    self.d.db_.currentSavePoint_.saveEdit(
                        pKN, self.d.bufferCopy_, self)

            if functionAfter and self.d.activatedCommitActions_:
                if not savePoint:
                    savePoint = FLSqlSavePoint(None)
                savePoint.saveEdit(pKN, self.d.bufferCopy_, self)

            if self.d.cursorRelation_ and self.d.relation_:
                if self.d.cursorRelation_.metadata():
                    self.d.cursorRelation_.setAskForCancelChanges(True)
            logger.trace("commitBuffer -- Edit . 20 . ")
            if self.isModifiedBuffer():
                # i = 0
                # while i < self.d.buffer_.count():
                #    if self.d.buffer_.value(i) == self.d.bufferCopy_.value(i) and self.d.buffer_.isNull(i) and self.d.bufferCopy_.isNull(i):
                #        self.d.buffer_.setGenerated(i, False)

                #    i = i +1

                logger.trace("commitBuffer -- Edit . 22 . ")
                self.update(False)
                # i = 0
                # while i < self.d.buffer_.count():
                #    self.d.buffer_.setGenerated(i, True)
                #    i = i + 1

                logger.trace("commitBuffer -- Edit . 25 . ")

                updated = True
                self.setNotGenerateds()
            logger.trace("commitBuffer -- Edit . 30 . ")

        elif self.d.modeAccess_ == self.Del:

            if self.d.cursorRelation_ and self.d.relation_:
                if self.d.cursorRelation_.metadata():
                    self.d.cursorRelation_.setAskForCancelChanges(True)

            recordDelBefore = "recordDelBefore%s" % self.metadata().name()
            cI = self.context()
            v = self._prj.call(recordDelBefore, [self], cI, False)
            if v and not isinstance(v, bool):
                return False

            fieldList = self.d.metadata_.fieldList()

            for field in fieldList:

                fiName = field.name()
                if not self.buffer().isGenerated(fiName):
                    continue

                s = None
                if not self.buffer().isNull(fiName):
                    s = self.buffer().value(fiName)

                if s is None:
                    continue

                relationList = field.relationList()
                if not relationList:
                    continue
                else:
                    for r in relationList:
                        c = FLSqlCursor(r.foreignTable())
                        if not c.metadata():
                            continue
                        f = c.metadata().field(r.foreignField())
                        if not f:
                            continue
                        if f and f.relationM1() and f.relationM1().deleteCascade():
                            c.setForwardOnly(True)
                            c.select(self.conn().manager().formatAssignValue(
                                r.foreignField(), f, s, True))
                            while(c.next()):
                                c.setModeAccess(self.Del)
                                c.refreshBuffer()
                                if not c.commitBuffer(False):
                                    return False

            self.model().Delete(self)

            recordDelAfter = "recordDelAfter%s" % self.metadata().name()
            cI = self.context()
            v = self._prj.call(recordDelAfter, [self], cI, False)

            updated = True

        if updated and self.lastError():
            # if savePoint == True:
            #    del savePoint
            return False

        if not self.d.modeAccess_ == self.Browse and functionAfter and self.d.activatedCommitActions_:
            # cI = FLSqlCursorInterface::sqlCursorInterface(this) FIXME
            cI = self.context()
            v = self._prj.call(functionAfter, [self], cI, False)
            if v and not isinstance(v, bool):
                # if savePoint == True:
                #    savePoint.undo()
                #    del savePoint

                return False

        if self.modeAccess() in (self.Del, self.Edit):
            self.setModeAccess(self.Browse)

        if self.modeAccess() == self.Insert:
            self.setModeAccess(self.Edit)

        if updated:
            if fieldNameCheck:
                self.d.buffer_.setGenerated(fieldNameCheck, True)
                if self.d.bufferCopy_:
                    self.d.bufferCopy_.setGenerated(fieldNameCheck, True)

            self.setFilter(None)
            self.clearMapCalcFields()

        if updated and emite:
            self.cursorUpdated.emit()

        self.bufferCommited.emit()
        return True

    """
    Manda el contenido del buffer del cursor relacionado a dicho cursor.

    Hace efectivos todos los cambios en el buffer del cursor relacionado posiconándose en el registro
    correspondiente que recibe los cambios.
    """
    @QtCore.pyqtSlot()
    def commitBufferCursorRelation(self):
        ok = True
        activeWid = QtWidgets.QApplication.activeModalWidget()
        if not activeWid:
            activeWid = QtWidgets.QApplication.activePopupWidget()
        if not activeWid:
            activeWid = QtWidgets.QApplication.activeWindow()

        activeWidEnabled = False
        if activeWid:
            activeWidEnabled = activeWid.isEnabled()

        if self.d.modeAccess_ == self.Insert:
            if self.d.cursorRelation_ and self.d.relation_:
                if self.d.cursorRelation_.metadata() and self.d.cursorRelation_.modeAccess() == self.Insert:

                    if activeWid and activeWidEnabled:
                        activeWid.setEnabled(False)

                    if not self.d.cursorRelation_.commitBuffer():
                        self.d.modeAccess_ = self.Browse
                        ok = False
                    else:
                        self.setFilter(None)
                        self.d.cursorRelation_.refresh()
                        self.d.cursorRelation_.setModeAccess(self.Edit)
                        self.d.cursorRelation_.refreshBuffer()

                    if activeWid and activeWidEnabled:
                        activeWid.setEnabled(True)

        elif self.d.modeAccess_ == self.Browse or self.d.modeAccess_ == self.Edit:
            if self.d.cursorRelation_ and self.d.relation_:
                if self.d.cursorRelation_.metadata() and self.d.cursorRelation_.modeAccess() == self.Insert:
                    if activeWid and activeWidEnabled:
                        activeWid.setEnabled(False)

                    if not self.d.cursorRelation_.commitBuffer():
                        self.d.modeAccess_ = self.Browse
                        ok = False
                    else:
                        self.d.cursorRelation_.refresh()
                        self.d.cursorRelation_.setModeAccess(self.Edit)
                        self.d.cursorRelation_.refreshBuffer()

                    if activeWid and activeWidEnabled:
                        activeWid.setEnabled(True)

        return ok

    """
    @return El nivel actual de anidamiento de transacciones, 0 no hay transaccion
    """
    @QtCore.pyqtSlot()
    def transactionLevel(self):
        if self.d.db_:
            return self.d.db_.transactionLevel()
        else:
            return 0

    """
    @return La lista con los niveles de las transacciones que ha iniciado este cursor y continuan abiertas
    """
    @QtCore.pyqtSlot()
    def transactionsOpened(self):
        lista = []
        for it in self.d.transactionsOpened_:
            lista.append(str(it))

        return lista

    """
    Deshace transacciones abiertas por este cursor.

    @param count  Cantidad de transacciones a deshacer, -1 todas.
    @param msg    Cadena de texto que se muestra en un cuadro de diálogo antes de deshacer las transacciones.
                Si es vacía no muestra nada.
    """
    @QtCore.pyqtSlot()
    @decorators.BetaImplementation
    def rollbackOpened(self, count=-1, msg=None):
        ct = None
        if count < 0:
            ct = len(self.d.transactionsOpened_)
        else:
            ct = count

        if ct > 0 and msg:
            t = None
            if self.d.metadata_:
                t = self.d.metadata_.name()
            else:
                t = self.name()

            m = "%sSqLCursor::rollbackOpened: %s %s" % (msg, count, t)
            self.d.msgBoxWarning(m, False)
        elif ct > 0:
            logger.trace("rollbackOpened: %s %s", count, self.name())

        i = 0
        while i < ct:
            logger.trace("Deshaciendo transacción abierta", self.transactionLevel())
            self.rollback()
            i = i + 1

    """
    Termina transacciones abiertas por este cursor.

    @param count  Cantidad de transacciones a terminar, -1 todas.
    @param msg    Cadena de texto que se muestra en un cuadro de diálogo antes de terminar las transacciones.
                Si es vacía no muestra nada.
    """
    @QtCore.pyqtSlot()
    def commitOpened(self, count=-1, msg=None):
        ct = None
        t = None
        if count < 0:
            ct = len(self.d.transactionsOpened_)
        else:
            ct = count

        if self.d.metadata_:
            t = self.d.metadata_.name()
        else:
            t = self.name()

        if ct and msg:
            m = "%sSqlCursor::commitOpened: %s %s" % (msg, str(count), t)
            self.d.msgBoxWarning(m, False)
            logger.message(m)
        elif ct > 0:
            logger.message("SqlCursor::commitOpened: %d %s" % (count, self.name()))

        i = 0
        while i < ct:
            logger.message("Terminando transacción abierta %s", self.transactionLevel())
            self.commit()
            i = i + 1

    """
    Entra en un bucle de comprobacion de riesgos de bloqueos para esta tabla y el registro actual

    El bucle continua mientras existan bloqueos, hasta que se vuelva a llamar a este método con
    'terminate' activado o cuando el usuario cancele la operación.

    @param  terminate True terminará el bucle de comprobaciones si está activo
    """
    @QtCore.pyqtSlot()
    @decorators.NotImplementedWarn
    def checkRisksLocks(self, terminate=False):
        return True

    """
    Establece el acceso global para la tabla, ver FLSqlCursor::setAcosCondition().

    Este será el permiso a aplicar a todos los campos por defecto

    @param  ac Permiso global; p.e.: "r-", "-w"
    """
    @QtCore.pyqtSlot()
    def setAcTable(self, ac):
        self.d.idAc_ = self.d.idAc_ + 1
        self.d.id_ = "%s%s%s" % (self.d.idAc_, self.d.idAcos_, self.d.idCond_)
        self.d.acPermTable_ = ac

    """
    Establece la lista de control de acceso (ACOs) para los campos de la tabla, , ver FLSqlCursor::setAcosCondition().

    Esta lista de textos deberá tener en sus componentes de orden par los nombres de los campos,
    y en los componentes de orden impar el permiso a aplicar a ese campo,
    p.e.: "nombre", "r-", "descripcion", "--", "telefono", "rw",...

    Los permisos definidos aqui sobreescriben al global.

    @param acos Lista de cadenas de texto con los nombre de campos y permisos.
    """
    @QtCore.pyqtSlot()
    def setAcosTable(self, acos):
        self.d.idAcos_ = self.d.idAcos_ + 1
        self.d.id_ = "%s%s%s" % (self.d.idAc_, self.d.idAcos_, self.d.idCond_)
        self.d.acosTable_ = acos

    """
    Establece la condicion que se debe cumplir para aplicar el control de acceso.

    Para cada registro se evalua esta condicion y si se cumple, aplica la regla
    de control de acceso establecida con FLSqlCursor::setAcTable y FLSqlCursor::setAcosTable.

    Ejemplos:

    setAcosCondition( "nombre", VALUE, "pepe" ); // valueBuffer( "nombre" ) == "pepe"
    setAcosCondition( "nombre", REGEXP, "pe*" ); // QRegExp( "pe*" ).exactMatch( valueBuffer( "nombre" ).toString() )
    setAcosCondition( "sys.checkAcos", FUNCTION, true ); // call( "sys.checkAcos" ) == true

    @param  cond      Tipo de evaluacion;
                    VALUE compara con un valor fijo
                    REGEXP compara con una expresion regular
                    FUNCTION compara con el valor devuelto por una funcion de script

    @param  condName  Si es vacio no se evalua la condicion y la regla no se aplica nunca.
                    Para VALUE y REGEXP nombre de un campo.
                    Para FUNCTION nombre de una funcion de script.  A la función se le pasa como
                    argumento el objeto cursor.

    @param  condVal   Valor que hace que la condicion sea cierta
    """
    @QtCore.pyqtSlot()
    def setAcosCondition(self, condName, cond, condVal):
        self.d.idCond_ = self.d.idCond_ + 1
        self.d.id_ = "%s%s%s" % (self.d.idAc_, self.d.idAcos_, self.d.idCond_)
        self.d.acosCondName_ = condName
        self.d.acosCond_ = cond
        self.d.acosCondVal_ = condVal

    """
    Comprueba si hay una colisión de campos editados por dos sesiones simultáneamente.

    @return Lista con los nombres de los campos que colisionan
    """
    @QtCore.pyqtSlot()
    @decorators.NotImplementedWarn
    def concurrencyFields(self):
        return True

    """
    Cambia el cursor a otra conexión de base de datos
    """
    @QtCore.pyqtSlot()
    def changeConnection(self, connName):
        curConnName = self.connectionName()
        if curConnName == connName:
            return

        newDB = self._prj.conn.database(connName)
        if curConnName == newDB.connectionName():
            return

        if self.d.transactionsOpened_:
            mtd = self.d.metadata_
            t = None
            if mtd:
                t = mtd.name()
            else:
                t = self.name()

            msg = FLUtil.tr("Se han detectado transacciones no finalizadas en la última operación.\n"
                            "Se van a cancelar las transacciones pendientes.\n"
                            "Los últimos datos introducidos no han sido guardados, por favor\n"
                            "revise sus últimas acciones y repita las operaciones que no\n"
                            "se han guardado.\n") + "SqlCursor::changeConnection: %s\n" % t
            self.rollbackOpened(-1, msg)

        bufferNoEmpty = (self.d.buffer_ is not None)

        bufferBackup = None
        if bufferNoEmpty:
            bufferBackup = self.d.buffer_
            self.d.buffer_ = None

        # c = FLSqlCursor(None, True, newDB.db())
        self.d.db_ = newDB
        self.init(self.d.curName_, True,
                  self.d.cursorRelation_, self.d.relation_)

        if(bufferNoEmpty):
            # self.d.buffer_ QSqlCursor::edtiBuffer()
            self.d.buffer_ = bufferBackup

        self.connectionChanged.emit()

    """
    Si el cursor viene de una consulta, realiza el proceso de agregar la defición
    de los campos al mismo
    """
    @decorators.NotImplementedWarn
    def populateCursor(self):
        return True

    """
    Cuando el cursor viene de una consulta, realiza el proceso que marca como
    no generados (no se tienen en cuenta en INSERT, EDIT, DEL) los campos del buffer
    que no pertenecen a la tabla principal
    """

    def setNotGenerateds(self):
        if self.metadata() and self.d.isQuery_ and self.buffer():
            for f in self.metadata().fieldList():
                self.buffer().setGenerated(f, False)

    """
    Uso interno
    """
    @decorators.NotImplementedWarn
    def setExtraFieldAttributes(self):
        return True

    def clearMapCalcFields(self):
        self.d.mapCalcFields_ = []

    @decorators.NotImplementedWarn
    def valueBufferRaw(self, fN):
        return True

    def sort(self):
        return self.d.sort_

    @decorators.NotImplementedWarn
    def list(self):
        return None

    def filter(self):
        return self.d.filter_

    """
    Actualiza tableModel con el buffer
    """

    def update(self, notify=True):
        logger.trace("FLSqlCursor.update --- BEGIN")
        if self.modeAccess() == FLSqlCursor.Edit:
            # solo los campos modified
            lista = self.d.buffer_.modifiedFields()
            self.d.buffer_.setNoModifiedFields()
            # TODO: pKVaue debe ser el valueBufferCopy, es decir, el antiguo. Para
            # .. soportar updates de PKey, que, aunque inapropiados deberían funcionar.
            pKValue = self.d.buffer_.value(self.d.buffer_.pK())

            dict_update = dict(
                [(fieldName, self.d.buffer_.value(fieldName)) for fieldName in lista])
            try:
                update_successful = self.model().updateValuesDB(pKValue, dict_update)
            except Exception:
                logger.exception("FLSqlCursor.update:: Unhandled error on model updateRowDB:: ")
                update_successful = False
            # TODO: En el futuro, si no se puede conseguir un update, hay que
            # "tirar atrás" todo.
            if update_successful:
                row = self.model().findPKRow([pKValue])
                if row is not None:
                    if self.model().value(row, self.model().pK()) != pKValue:
                        raise AssertionError("Los indices del CursorTableModel devolvieron un registro erroneo: %r != %r" % (
                            self.model().value(row, self.model().pK()), pKValue))
                    self.model().setValuesDict(row, dict_update)

                else:
                    # Método clásico
                    logger.warn("update :: WARN :: Los indices del CursorTableModel no funcionan o el PKey no existe.")
                    row = 0
                    while row < self.model().rowCount():
                        if self.model().value(row, self.model().pK()) == pKValue:
                            for fieldName in lista:
                                self.model().setValue(row, fieldName, self.d.buffer_.value(fieldName))

                            break

                        row = row + 1

            if notify:
                self.bufferCommited.emit()

        logger.trace("FLSqlCursor.update --- END")

    """
    Indica el último error
    """

    def lastError(self):
        return self.db().lastError()
    """
    signals:
    """

    """
    Indica que se ha cargado un nuevo buffer
    """
    newBuffer = QtCore.pyqtSignal()

    """
    Indica ha cambiado un campo del buffer, junto con la señal se envía el nombre del campo que
    ha cambiado.
    """
    bufferChanged = QtCore.pyqtSignal(str)

    """
    Indica que se ha actualizado el cursor
    """
    cursorUpdated = QtCore.pyqtSignal()

    """
    Indica que se ha elegido un registro, mediante doble clic sobre él o bien pulsando la tecla Enter
    """
    recordChoosed = QtCore.pyqtSignal()

    """
    Indica que la posicion del registro activo dentro del cursor ha cambiado
    """
    currentChanged = QtCore.pyqtSignal(int)

    """
    Indica que se ha realizado un commit automático para evitar bloqueos
    """
    autoCommit = QtCore.pyqtSignal()

    """
    Indica que se ha realizado un commitBuffer
    """
    bufferCommited = QtCore.pyqtSignal()

    """
    Indica que se ha cambiado la conexión de base de datos del cursor. Ver changeConnection
    """
    connectionChanged = QtCore.pyqtSignal()

    """
    Indica que se ha realizado un commit
    """
    commited = QtCore.pyqtSignal()

    """
    private slots:
    """

    """ Uso interno """
    clearPersistentFilter = QtCore.pyqtSignal()
    # def clearPersistentFilter(self):
    #     self.d.persistentFilter_ = None


class AQBoolFlagState(object):

    modified_ = None
    prevValue_ = None
    prev_ = None
    next_ = None
    count_ = False

    def __init__(self):
        self.modified_ = None
        self.prevValue_ = False
        self.prev_ = None
        self.next_ = None

        if not self.count_:
            self.count_ = self.count_ + 1
        logger.trace("---------------->AQBoolFlagState.count_ =%s", self.count_)

    def __del__(self):
        self.count_ = self.count_ - 1

    def dumpDebug(self):
        logger.trace("%s <- (%s : [%s, %s]) -> %s", self.prev_, self, self.modifier_, self.prevValue_, self.next_)


class AQBoolFlagStateList(object):

    cur_ = None

    def __init__(self):
        self.cur_ = AQBoolFlagState()

    def __del__(self):
        self.clear()

    def dumpDebug(self):
        logger.trace("Current %s" % self.cur_)
        while self.cur_:
            self.cur_.dumpDebug()
            self.cur_ = self.cur_.prev

        logger.trace("AQBoolFlagState count %s", self.cur_.count_)

    def clear(self):
        while(self.cur_):
            pv = self.cur_.prev_
            self.cur_ = None
            self.cur_ = pv

    def isEmpty(self):
        return (self.cur_ is None)

    def find(self, m):
        it = self.cur_
        while (it and not it.modified_ == m):
            it = it.prev_

        return it

    def append(self, i):
        if not self.cur_:
            self.cur_ = i
            self.cur_.next_ = None
            self.cur_.prev_ = None
            return

        self.cur_.next_ = i
        i.prev_ = self.cur_
        self.cur_ = i
        self.cur_.next_ = None

    def erase(self, i, del_):
        if not self.cur_:
            return

        if self.cur_ == i:
            if self.cur_.prev_:
                self.cur_ = self.cur_.prev_
                self.cur_.next_ = None
            else:
                self.cur_ = None
        else:
            if i.next_:
                i.next_.prev_ = i.prev_
            if i.prev_:
                i.prev_.next_ = i.next_

        if not del_:
            i.next_ = None
            i.prev_ = None
        else:
            del i

    def pushOnTop(self, i):
        if self.cur_ == i:
            return
        self.erase(i, False)
        self.append(i)
