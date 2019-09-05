# -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : MapBiomas Collection
Description          : This plugin lets you get collection of mapping from MapBiomas Project(http://mapbiomas.org/).
Date                 : August, 2019
copyright            : (C) 2019 by Luiz Motta
email                : motta.luiz@gmail.com

 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
__author__ = 'Luiz Motta'
__date__ = '2019-08-28'
__copyright__ = '(C) 2019, Luiz Motta'
__revision__ = '$Format:%H$'

import urllib.parse

from qgis.PyQt.QtCore import (
  Qt, QObject, pyqtSlot
)
from qgis.PyQt.QtWidgets import (
  QWidget, QDockWidget,
  QComboBox, QPushButton,
  QRadioButton, QGroupBox,
  QLabel, QListWidget, QListWidgetItem, QAbstractItemView,
  QLayout, QHBoxLayout, QVBoxLayout, QSizePolicy
)
from qgis.PyQt.QtGui import QIcon, QFont, QCursor

from qgis.PyQt.QtXml import QDomDocument

from qgis.core import (
    Qgis, QgsProject, QgsLayerTreeLayer, QgsRasterLayer, QgsReadWriteContext
)


class DockWidgetMapbiomasCollection(QDockWidget):
    def __init__(self, iface):
        def setupUi():
            def addItems(wgtList, labels, selectAll=False):
                for l in labels:
                    wgtList.addItem( l )
                if selectAll:
                    for row in range( len( labels ) ):
                        wgtList.item( row ).setSelected( True )
                else:
                    wgtList.item( 0 ).setSelected( True )

            self.setObjectName('mapbiomascollection_dockwidget')
            wgt = QWidget( self )
            wgt.setAttribute( Qt.WA_DeleteOnClose )
            # Years
            self.listwYears = QListWidget( wgt )
            self.listwYears.setSelectionMode( QAbstractItemView.ExtendedSelection )
            labels = [ str(item) for item in range( 2018, 1984, -1 ) ]
            addItems( self.listwYears, labels )
            self.listwYears.setMaximumWidth( self.listwYears.sizeHintForColumn(0) * 2)
            self.listwYears.setSizePolicy( QSizePolicy.Fixed, QSizePolicy.Expanding )
            # Class
            self.listwClass = QListWidget( wgt )
            self.listwClass.setSelectionMode( QAbstractItemView.ExtendedSelection )
            labels = self.collection_class.keys()
            addItems( self.listwClass, labels, True )
            # Layout Years + Class
            lytList = QHBoxLayout()
            lytList.addWidget( self.listwYears )
            lytList.addWidget( self.listwClass )
            #
            gbAction = QGroupBox('Actions')
            self.rbGroup = QRadioButton('Create Group')
            self.rbGroup.setChecked(True)
            self.rbLayer = QRadioButton('Set Collection Layer')
            self.rbLayer.setEnabled( False)
            lytAction = QHBoxLayout()
            lytAction.addWidget( self.rbGroup )
            lytAction.addWidget( self.rbLayer )
            gbAction.setLayout( lytAction )
            #
            self.btnOk = QPushButton('OK', wgt )
            #
            lyt = QVBoxLayout()
            lyt.addLayout( lytList )
            lyt.addWidget( gbAction )
            lyt.addWidget( self.btnOk )
            lyt.setSizeConstraint( QLayout.SetMaximumSize )
            wgt.setLayout( lyt )
            self.setWidget( wgt )

        super().__init__('MapBiomas Collection 4', iface.mainWindow() )
        self.collection_class = {
            "1. Floresta": 1,
            "1.1. Floresta Natural": 2,
            "1.1.1. Formação Florestal": 3,
            "1.1.2. Formação Savânica": 4,
            "1.1.3. Mangue": 5,
            "1.2. Floresta Plantada": 9,
            "2. Formação Natural não Florestal": 10,
            "2.1. Área Úmida Natural não Florestal": 11,
            "2.2. Formação Campestre (Campo)": 12,
            "2.3. Apicum": 32,
            "2.4. Afloramento Rochoso": 29,
            "2.5. Outra Formação não Florestal": 13,
            "3. Agropecuária": 14,
            "3.1. Pastagem": 15,
            "3.2. Agricultura": 17,
            "3.2.1. Cultura Anual e Perene": 19,
            "3.2.2. Cultura Semi-Perene": 20,
            "3.3 Mosaico de Agricultura ou Pastagem": 21,
            "4. Área não Vegetada": 22,
            "4.1. Infraestrutura Urbana": 24,
            "4.2. Mineração": 30,
            "4.3. Praia e Duna": 23,
            "4.4. Outra Área não Vegetada": 25,
            "5. Corpo D'água": 26,
            "5.1. Rio, Lago e Oceano": 33,
            "5.2. Aquicultura": 31,
            "6. Não Observado": 27
        }
        setupUi()
        self.mc = MapbiomasCollection( iface, self )

    def __del__(self):
        del self.mc


class MapbiomasCollection(QObject):
    nameModulus = "MapbiomasCollection"
    def __init__(self, iface, dockWidget):
        super().__init__()
        self.dockWidget = dockWidget
        self.numGroup = 0
        #
        self.msgBar = iface.messageBar()
        self.view = iface.layerTreeView()
        self.actionDraw = iface.actionDraw()
        self.mapCanvas = iface.mapCanvas()
        self.project = QgsProject.instance()
        self.root = self.project.layerTreeRoot()
        #
        self._connect()

    def __del__(self):
        self._connect( False )

    def _connect(self, isConnect = True):
        signal_slot = (
        { 'signal': self.dockWidget.btnOk.clicked, 'slot': self._runOk },
        { 'signal': self.dockWidget.rbGroup.toggled, 'slot': self._toggledGroup },
        { 'signal': self.view.selectionModel().selectionChanged, 'slot': self._changeLayer }
        )
        if isConnect:
            for item in signal_slot:
                item['signal'].connect( item['slot'] )
        else:
            for item in signal_slot:
                item['signal'].disconnect( item['slot'] )

    def _getUrlBioma(self, year, l_strClass):
        url = 'http://workspace.mapbiomas.org/wms'
        paramsWms = 'IgnoreGetFeatureInfoUrl=1&IgnoreGetMapUrl=1&crs=EPSG:3857&dpiMode=7&format=image/png&layers=coverage&styles='
        paramsQuote = "map=wms/v/4.0/classification/coverage.map&layers=coverage&transparent=true&version=1.1.1&territory_id=10"
        paramsQuote = urllib.parse.quote( "{}&year={}&classification_ids=".format( paramsQuote, year ) )
        paramClassification = ','.join( l_strClass )
        return "{}&url={}?{}{}".format( paramsWms, url, paramsQuote, paramClassification )

    def _addGroup(self):
        def getLayerBiomas(year, l_strClass):
            nameLayer = "Collection {}".format( year )
            return QgsRasterLayer( self._getUrlBioma( year, l_strClass ), nameLayer, 'wms' )

        itemsYear = self.dockWidget.listwYears.selectedItems()
        if len( itemsYear ) == 0:
            msg = 'Need select at least one Year'
            self.msgBar.pushMessage( self.nameModulus, msg, Qgis.Critical )
            return
        else:
            itemsYear = [ item.text() for item in itemsYear ]
        itemsClass = self.dockWidget.listwClass.selectedItems()
        if len( itemsClass ) == 0:
            msg = 'Need select at least one Class'
            self.msgBar.pushMessage( self.nameModulus, msg, Qgis.Critical )
            return
        # Add Group
        self.numGroup += 1
        name = "MapBiomas #{}".format( self.numGroup )
        group = self.root.addGroup( name )
        d = self.dockWidget.collection_class
        l_strClass = [ str( d[ item.data( Qt.DisplayRole ) ] ) for item in itemsClass ]
        for year in itemsYear:
            layer = getLayerBiomas( year, l_strClass )
            if layer.isValid():
                self.project.addMapLayer( layer, addToLegend=False )
                group.addLayer( layer ).setItemVisibilityChecked( False )

    def _setCollection(self):
        def setDataSource(layer, url):
            '''
            Adapted from 'Change DataSource' plugin,(C) 2014 by Enrico Ferreguti
            '''
            XMLDocument = QDomDocument('style')
            XMLMapLayers = XMLDocument.createElement('maplayers')
            XMLMapLayer = XMLDocument.createElement('maplayer')
            context = QgsReadWriteContext()
            layer.writeLayerXml( XMLMapLayer, XMLDocument, context )
            # apply layer definition
            XMLMapLayer.firstChildElement('datasource').firstChild().setNodeValue( url )
            XMLMapLayers.appendChild( XMLMapLayer )
            XMLDocument.appendChild( XMLMapLayers )
            layer.readLayerXml( XMLMapLayer, context )

        # Year
        itemsYear = self.dockWidget.listwYears.selectedItems()
        if len( itemsYear ) > 1:
            msg = 'Please select one year only'
            self.msgBar.pushMessage( self.nameModulus, msg, Qgis.Critical )
            return
        if len( itemsYear ) == 0:
            msg = 'Need select at least one Year'
            self.msgBar.pushMessage( self.nameModulus, msg, Qgis.Critical )
            return
        year = itemsYear[0].text()
        # Class
        itemsClass = self.dockWidget.listwClass.selectedItems()
        if len( itemsClass ) == 0:
            msg = 'Need select at least one Class'
            self.msgBar.pushMessage( self.nameModulus, msg, Qgis.Critical )
            return
        d = self.dockWidget.collection_class
        l_strClass = [ str( d[ item.data( Qt.DisplayRole ) ] ) for item in itemsClass ]
        #
        layer = self.view.currentNode().layer()
        setDataSource( layer, self._getUrlBioma( year, l_strClass ) )
        layer.setName( "Collection {}".format( year ) )
        layer.reload()
        self.actionDraw.trigger()
        self.mapCanvas.refresh()
        self.view.refreshLayerSymbology( layer.id() )


    @pyqtSlot(bool)
    def _toggledGroup(self, checked):
        selection = QAbstractItemView.ExtendedSelection if checked else QAbstractItemView.SingleSelection
        self.dockWidget.listwYears.setSelectionMode( selection )

    @pyqtSlot('QItemSelection,QItemSelection')
    def _changeLayer(self, selected=None, deselected=None):
        def getYearClassLayerBioma(layer):
            source = layer.source()
            if source.find('http://workspace.mapbiomas.org/wms') == -1:
                return { 'isOk': False }
            idx = source.find('year')
            if idx == -1:
                return { 'isOk': False }
            year_class = urllib.parse.unquote( source[ idx: ] ).split('&')
            vreturn = {'isOk': True }
            for item in year_class:
                d = item.split('=')
                vreturn[ d[0] ] = d[1]
            ids_class = [ int( item ) for item in vreturn['classification_ids'].split(',') ]
            del vreturn['classification_ids']
            d = self.dockWidget.collection_class
            l_class = [ k for k in d if d[k] in ids_class ]
            vreturn['class'] = l_class
            return vreturn

        def setEnabledRbLayer(isEnabled):
            self.dockWidget.rbLayer.setEnabled( isEnabled )
            if not isEnabled:
                self.dockWidget.rbGroup.setChecked( True )

        def setListWidget(lstWidget, value ):
            item = lstWidget.findItems( value, Qt.MatchExactly )[0]
            item.setSelected( True )

        node = self.view.currentNode()
        if not isinstance( node, QgsLayerTreeLayer ):
            setEnabledRbLayer( False )
            return
        r = getYearClassLayerBioma( node.layer() )
        if not r['isOk']:
            setEnabledRbLayer( False )
            return
        setEnabledRbLayer( True )
        self.dockWidget.rbLayer.setChecked( True )
        self.dockWidget.listwYears.setSelectionMode( QAbstractItemView.SingleSelection )
        setListWidget( self.dockWidget.listwYears, r['year'] )
        #
        self.dockWidget.listwClass.clearSelection()
        for value in r['class']:
            setListWidget( self.dockWidget.listwClass, value )

    @pyqtSlot()
    def _runOk(self):
        if self.dockWidget.rbLayer.isChecked():
            self._setCollection()
        else:
            self._addGroup()
