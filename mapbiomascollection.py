# -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : MapBiomas Collection Official
Description          : This plugin enables the acquisition of use and coverage maps from MapBiomas Project (http://mapbiomas.org/).
Date                 : February, 2024
copyright            : (C) 2019 by Luiz Motta, Updated by Luiz Cortinhas (2020) and Mário Hermes (2024)
email                : contato@mapbiomas.org

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

import urllib.parse
import urllib.request, json

from osgeo import gdal

from qgis.PyQt.QtCore import (
    Qt, QSettings, QLocale,
    QObject, pyqtSlot,
    
)
from qgis.PyQt.QtWidgets import (
    QWidget, QDockWidget, QPushButton, QTreeView,
    QSlider, QLabel,
    QSizePolicy,
    QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QHBoxLayout, QSplitter
)
from qgis.PyQt.QtGui import (
    QColor, QPixmap, QIcon
)

from qgis.core import (
    QgsApplication, Qgis, QgsProject,
    QgsRasterLayer,
    QgsTask,
    QgsDataSourceUri
)
from qgis.gui import QgsGui, QgsMessageBar, QgsLayerTreeEmbeddedWidgetProvider, QgsMapCanvas
from qgis.utils import iface

class MapBiomasCollectionWidget(QWidget):
    legend_codes = {}
    enabled_classes_list = {}
    year = 2022
    
    @staticmethod
    def getParentColor(item, legend_code, id):
        if item['parent'] == '0' and item['status'] == False:
            return 'FFFFFF'
        if item['status']:
            return item['color']
        else:
            return MapBiomasCollectionWidget.getParentColor(MapBiomasCollectionWidget.legend_codes[legend_code]['classParents'][item['parent']], legend_code, item['parent'])

    @staticmethod
    def getUrl(url, legend_codes, enabled_classes_list, year):
        MapBiomasCollectionWidget.legend_codes = legend_codes
        MapBiomasCollectionWidget.enabled_classes_list = enabled_classes_list
        MapBiomasCollectionWidget.year = year
        
        geoserver_layers = []
        geoserver_styles = []
        env = ''

        for k, v in legend_codes.items():
            if k == 'Chile' or k == 'Argentina':
                continue
            if year not in range(v['metadata']['years']['min'], v['metadata']['years']['max'] + 1):
                print(f"Selected year for {k} not available")
                continue
            
            style_name = f"solved:mapbiomas_{k.lower().replace(' ', '_')}_legend_v16"
            layer_name = f"mapbiomas_{k.lower().replace(' ', '_')}_{str(year)}"
            geoserver_styles.append(style_name)
            geoserver_layers.append(layer_name)

            for item in v['classParents'].keys():
                MapBiomasCollectionWidget.legend_codes[k]['classParents'][item]['status'] = False

            for k2, v2 in enabled_classes_list.items():
                for item in v2:
                    if item in MapBiomasCollectionWidget.legend_codes[k2]['classParents']:
                        MapBiomasCollectionWidget.legend_codes[k2]['classParents'][item]['status'] = True
            
            for item in v['classParents'].keys():
                class_id = f"{k.lower().replace(' ', '_')}_{item}"
                classID_opacity = class_id + '_o'
                opacity = '1'
                color = MapBiomasCollectionWidget.getParentColor(MapBiomasCollectionWidget.legend_codes[k]['classParents'][item], k, item)
                if color == 'FFFFFF':
                    opacity = '0'
                env += f'{class_id}:{color};{classID_opacity}:{opacity};'
                
        xMin, yMin, xMax, yMax = -180, -90, 180, 90  # Example global extent
        params = dict(
            IgnoreGetFeatureInfoUrl = 1,
            IgnoreGetMapUrl = 1,
            service = 'WMS',
            version = '1.1.1',
            request = 'GetMap',
            layers = ','.join(geoserver_layers),
            styles = ','.join(geoserver_styles),
            bbox = f"{xMin},{yMin},{xMax},{yMax}",
            width = '1024',
            height = '768',
            crs = 'EPSG:4326',
            format = 'image/png',
            transparent = 'TRUE',
            url = 'http://azure.solved.eco.br:8080/geoserver/solved/wms'
        )

        layers_param = "&".join([f"layers={layer}" for layer in geoserver_layers])
        styles_param = "&".join([f"styles={style}" for style in geoserver_styles])
        wms_params = '&'.join([f"{k}={v}" for k, v in params.items()])

        parsed_params = urllib.parse.quote(f"&transparent=true&tiled=true&version=1.1.1&crs=EPSG:4326&LAYERS={','.join(geoserver_layers)}&exceptions=application/vnd.ogc.se_inimage&env={env}")

        wms_url = f"IgnoreGetFeatureInfoUrl=1&IgnoreGetMapUrl=1&service=WMS&{styles_param}&request=GetMap&format=image/png&{layers_param}&crs=EPSG:4326&url=http://azure.solved.eco.br:8080/geoserver/solved/wms?{parsed_params}"
        
        return wms_url
    

    def __init__(self, layer, metadata, legend_codes):
        def getYearClasses():
            def getYear():
                values = [ item for item in paramsSource if item.find('years=') > -1]
                return self.maxYear if not len( values ) == 1 else int( values[0].split('=')[1] )

            def getClasses():
                values = [ item for item in paramsSource if item.find('classification_ids=') > -1 ]
                if (not len( values ) == 1) or (values[0] == 'classification_ids='):
                    return [] 
                else :
                    return [ int( item ) for item in values[0].split('=')[1].split(',') ]
            paramsSource = urllib.parse.unquote( self.layer.source() ).split('&')
            return getYear(), getClasses()

        def setGui(legend_codes):
            def createLayoutYear():
                lytYear = QHBoxLayout()
                lblTitleYear = QLabel( 'Year:', self )
                lblYear = QLabel( str( self.year ), self )
                lytYear.addWidget( lblTitleYear  )
                lytYear.addWidget( lblYear )
                return lytYear, lblYear

            def createLayoutSlider():
                def createButtonLimit(limitYear, sFormat, objectName):
                    label = sFormat.format( limitYear )
                    pb = QPushButton( label, self )
                    width = pb.fontMetrics().boundingRect( label ).width() + 7
                    pb.setMaximumWidth( width )
                    pb.setObjectName( objectName )
                    return pb

                def createSlider():
                    slider = QSlider( Qt.Horizontal, self )
                    #slider.setTracking( False ) # Value changed only released mouse
                    slider.setMinimum( self.minYear )
                    slider.setMaximum( self.maxYear )
                    slider.setSingleStep(1)
                    slider.setValue( self.year )
                    interval = int( ( self.maxYear - self.minYear) / 10 )
                    slider.setTickInterval( interval )
                    slider.setPageStep( interval)
                    slider.setTickPosition( QSlider.TicksBelow )
                    return slider

                lytSlider = QHBoxLayout()
                pbMin = createButtonLimit( self.minYear, "{} <<", 'minYear' )
                lytSlider.addWidget( pbMin )
                slider = createSlider()
                lytSlider.addWidget( slider )
                pbMax = createButtonLimit( self.maxYear, ">> {}", 'maxYear' )
                lytSlider.addWidget( pbMax )
                return lytSlider, slider, pbMin, pbMax

            def createTree(legend_codes):
                def populateTreeJson(classes, itemRoot, enabled_classes):
                    def createIcon(color):
                        color = QColor( color['r'], color['g'], color['b'] )
                        pix = QPixmap(16, 16)
                        pix.fill( color )
                        return QIcon( pix )

                    def createItem(itemRoot, name, class_id, flags, icon):
                        # WidgetItem
                        item = QTreeWidgetItem( itemRoot )
                        item.setText(0, name )
                        item.setData(0, Qt.UserRole, class_id )
                        checkState = Qt.Checked if str(class_id) in enabled_classes else Qt.Unchecked
                        item.setCheckState(0, checkState )
                        item.setFlags( flags )
                        item.setIcon(0, icon )
                        return item

                    flags = itemRoot.flags() | Qt.ItemIsUserCheckable
                    for k in classes:
                        class_id = classes[ k ]['id']
                        icon = createIcon( classes[ k ]['color'] )
                        itemClass = createItem( itemRoot, k, class_id, flags, icon )
                        if 'classes' in classes[ k ]:
                            populateTreeJson( classes[ k ]['classes'], itemClass, enabled_classes )
                            
                def expandTreeBasedOnCheckState(item):
                    if item.childCount() == 0:
                        return
                    for i in range(item.childCount()):
                        childItem = item.child(i)
                        if childItem.checkState(0) == Qt.Checked:
                            childItem.parent().setExpanded( True )
                        expandTreeBasedOnCheckState(childItem)
                        
                tree = QTreeWidget( self )
                tree.setSelectionMode( tree.NoSelection )
                tree.setHeaderHidden( True )
                itemRoot = QTreeWidgetItem( tree )
                itemRoot.setText(0, 'Initiative')
                for legend_code in legend_codes:
                    legend_code_node = QTreeWidgetItem( itemRoot )
                    legend_code_node.setText(0, legend_code)
                    
                    checkState = Qt.Checked if str(0) in self.enabled_classes_list[legend_code] else Qt.Unchecked
                    
                    if self.year not in range(  self.legend_codes[legend_code]['metadata']['years']['min'], 
                                                self.legend_codes[legend_code]['metadata']['years']['max'] + 1):
                        checkState = Qt.Unchecked
                        legend_code_node.setFlags(legend_code_node.flags() & ~Qt.ItemIsUserCheckable & ~Qt.ItemIsSelectable)
                        legend_code_node.setChildIndicatorPolicy(QTreeWidgetItem.DontShowIndicator)
                        legend_code_node.setText(0, legend_code + ' (not available for this year)')
                        legend_code_node.setForeground(0, QColor(Qt.gray))
                        
                    legend_code_node.setCheckState(0, checkState)
                    legend_code_node.setData(0, Qt.UserRole, 0)
                    populateTreeJson( legend_codes[legend_code]['classes'], legend_code_node, self.enabled_classes_list[legend_code] )
                expandTreeBasedOnCheckState(itemRoot)                
                
                return tree, itemRoot

            def createLayoutUnselect():
                lytUnselect = QHBoxLayout()
                btnUnselect = QPushButton( 'Unselect all', self )
                width = btnUnselect.fontMetrics().boundingRect( 'Unselect' ).width() + 40
                btnUnselect.setMaximumWidth( width )
                lytUnselect.addWidget( btnUnselect )
                return btnUnselect, lytUnselect

            lytYear, lblYear  = createLayoutYear()
            lytSlider, slider, pbMin, pbMax = createLayoutSlider( )
            tree, itemClasses = createTree( legend_codes )
            unselectBtn, unselectLayout = createLayoutUnselect()
            itemClasses.setExpanded( True )

            # Layout
            layers_panel = iface.mainWindow().findChild(QDockWidget, 'Layers')
            layer_tree_view = layers_panel.findChild(QTreeView)
            layer_tree_view_height = layer_tree_view.height()
            self.setMinimumHeight( layer_tree_view_height - 100 )
            
            # splitter = QSplitter( Qt.Vertical, self )
            # dummy_widget = QWidget( self )
            # dummy_widget.resize( 0, 0 )
            # splitter.addWidget( tree )
            # splitter.addWidget( dummy_widget )
            
            lyt = QVBoxLayout()
            lyt.addLayout( lytYear )
            lyt.addLayout( lytSlider )
            lyt.addWidget( tree )
            lyt.addLayout( unselectLayout )
            msgBar = QgsMessageBar(self)
            lyt.addWidget( msgBar )
            self.setLayout( lyt )        

            return {
                'msgBar': msgBar,
                'lblYear': lblYear,
                'slider': slider,
                'pbMin': pbMin,
                'pbMax': pbMax,
                'tree': tree,
                'unselectBtn': unselectBtn,
                'itemClasses': itemClasses
            }

        super().__init__()
        self.layer = layer
        
        self.url = metadata['url']
        self.minYear = metadata['years']['min']
        self.maxYear = metadata['years']['max']

        self.project = QgsProject.instance()
        self.root = self.project.layerTreeRoot()

        # self.year, self.l_class_id = getYearClasses() # Depend self.maxYear
                
        self.valueYearLayer = self.year

        r = setGui( legend_codes )
        self.msgBar = r['msgBar']
        self.lblYear = r['lblYear']
        self.slider = r['slider']
        self.pbMin = r['pbMin']
        self.pbMax = r['pbMax']
        self.tree = r['tree']
        self.unselectBtn = r['unselectBtn']
        self.itemClasses = r['itemClasses']
        self.unselect_all_clicked = False

        # Connections
        self.slider.valueChanged.connect( self.on_yearChanged )
        self.slider.sliderReleased.connect( self.on_released )
        self.pbMin.clicked.connect( self.on_limitYear )
        self.pbMax.clicked.connect( self.on_limitYear )
        self.tree.itemChanged.connect( self.on_classChanged )
        self.unselectBtn.clicked.connect( self.on_unselect_all )

    def _uploadSource(self):
        def checkDataSource():
            url = self.getUrl( self.url, self.legend_codes, self.enabled_classes_list, self.year )
            name = f"Mapbiomas Collection - {self.year}"
            args = [ url, name, self.layer.providerType() ]
            layer = QgsRasterLayer( *args )
            if not layer.isValid():
                msg = f"Error server {self.url}"
                return { 'isOk': False, 'message': msg }
            args += [ self.layer.dataProvider().ProviderOptions() ]
            return { 'isOk': True, 'args': args }

        self.setEnabled( False )
        r = checkDataSource()
        if not r['isOk']:
            self.msgBar.pushMessage( r['message'], Qgis.Critical, 4 )
            self.setEnabled( True )
            return
        self.layer.setDataSource( *r['args'] ) # The Widget will be create agai

    @pyqtSlot()
    def on_released(self):
        if self.valueYearLayer == self.year:
            return

        self._uploadSource()

    @pyqtSlot(int)
    def on_yearChanged(self, value):
        if value == self.year:
            return

        self.yearChanged = True
        self.year = value
        self.lblYear.setText( str( value ) )
        if not self.slider.isSliderDown(): # Keyboard
            self.valueYearLayer = self.year
            self._uploadSource()

    @pyqtSlot(bool)
    def on_limitYear(self, checked):
        year = self.maxYear if self.sender().objectName() == 'maxYear' else self.minYear
        if year == self.year:
            return

        self.year = year
        self.lblYear.setText( str( self.year ) )
        self.valueYearLayer = self.year
        self._uploadSource()

    @pyqtSlot(bool)
    def on_unselect_all(self):
        def unselectChildren(item):
            """Recursively unselects all child items of the given item."""
            if not item:
                return  # Handle the case where the item is None

            # Iterate through all child items
            for i in range(item.childCount()):
                child_item = item.child(i)

                # Uncheck the child item
                child_item.setCheckState(0, Qt.Unchecked)

                # Recursively call the function on child items
                unselectChildren(child_item)
                
        self.unselect_all_clicked = True
        
        # Get the root item from the actual tree widget
        root_item = self.tree.invisibleRootItem().child(0)

        # Call the unselectChildren function with the root item
        unselectChildren(root_item)
        
        self.enabled_classes_list = { k: list() for k, v in self.legend_codes.items() }
        self._uploadSource()
        self.unselect_all_clicked = False
            
    @pyqtSlot(QTreeWidgetItem, int)
    def on_classChanged(self, item, column):
        if self.unselect_all_clicked:
            return
        def getTreeRootItemText(item):
            current_item = item
            # Traverse up until we find 'Initiative' or reach a top-level item
            while current_item.parent() is not None:
                if current_item.parent().text(0) == 'Initiative':
                    return current_item.text(0)  # Return the current item if its parent's text is 'Initiative'
                current_item = current_item.parent()
            return None  # Return None if 'Initiative' is not found in the hierarchy
        
        def removeChildClasses(item):
            if item.childCount() != 0:
                for i in range( item.childCount() ):
                    removeChildClasses( item.child(i) )

            child_value = item.data( column, Qt.UserRole)
            if str(child_value) in self.enabled_classes_list[parent_legend_code]:
                self.enabled_classes_list[parent_legend_code].remove( str(child_value) )

        value = item.data( column, Qt.UserRole)
        color = item.data( column, Qt.UserRole)
        status = item.checkState( column ) == Qt.Checked
        parent_legend_code = getTreeRootItemText(item)
        
        if status:
            if str(value) not in self.enabled_classes_list[parent_legend_code]:
                self.enabled_classes_list[parent_legend_code].append( str(value) )
            if value == 0:
                for i in range( item.childCount() ):
                    self.enabled_classes_list[parent_legend_code].append( str(item.child(i).data( column, Qt.UserRole)) )
        else:
            removeChildClasses( item )
    
        self._uploadSource()


class LayerMapBiomasCollectionWidgetProvider(QgsLayerTreeEmbeddedWidgetProvider):
    def __init__(self, metadata, legend_codes):
        super().__init__()
        self.metadata = metadata
        self.legend_codes = legend_codes

    def id(self):
        return 'mapbiomascollection'

    def name(self):
        return "Layer MapBiomas Collection"

    def createWidget(self, layer, widgetIndex):
        return MapBiomasCollectionWidget( layer, self.metadata, self.legend_codes )

class MapBiomasCollection(QObject):
    MODULE = 'MapBiomasCollection'
    def __init__(self, iface):
        def getConfig():
            def readUrlJson(locale):
                f_name = f"http://azure.solved.eco.br:90/mapbiomascollection_{locale}_v16.json"
                isOk = True
                try:
                    name = f_name.format( locale=locale )
                    with urllib.request.urlopen(name) as url:
                        data = json.loads( url.read().decode() )
                    # name = f_name
                    # with open(name, 'r') as file:
                    #     data = json.load(file)
                except Exception as e:
                    print("Error:", e)
                    isOk = False
                
                r = { 'isOk': isOk }
                ( key, value ) = ( 'data', data )  if isOk else ( 'message', f"Missing file '{name}'" )
                r[ key ] = value
                
                return r

            # overrideLocale = QSettings().value('locale/overrideFlag', False, type=bool)
            # locale = QLocale.system().name() if not overrideLocale else QSettings().value('locale/userLocale', '')
            r = readUrlJson('en_US')
            if r['isOk']:
                return r['data']

            # if not r['isOk'] and locale == 'en_US':
            #     self.messageError = r['message']
            #     return None

            # r = readUrlJson('en_US')
            # if r['isOk']:
            #     return r['data']

            self.messageError = r['message']
            return None
        
        def setInitialEnabledClasses(legend_codes):
            enabled_classes_list = {k: list(v['initiallyEnabledClasses'].keys()) for k, v in legend_codes.items()}
            
            return enabled_classes_list

        super().__init__()        
        self.msgBar = iface.messageBar()
        self.root = QgsProject.instance().layerTreeRoot()
        self.taskManager = QgsApplication.taskManager()
        self.messageError = ''
        self.data = getConfig() # If error, return None and set self.messageError
        self.metadata = self.data['metadata']
        self.legend_codes = self.data['legend_codes']
        self.enabled_classes_list = setInitialEnabledClasses(self.legend_codes)
        self.widgetProvider = None

    def register(self):
        self.widgetProvider = LayerMapBiomasCollectionWidgetProvider(self.metadata, self.legend_codes)
        registry = QgsGui.layerTreeEmbeddedWidgetRegistry()
        if not registry.provider( self.widgetProvider.id() ) is None:
            registry.removeProvider( self.widgetProvider.id() )
        registry.addProvider( self.widgetProvider )

    def run(self):
        def createLayer(task, year):
            args = (self.metadata['url'], self.legend_codes, self.enabled_classes_list, year)
            url = MapBiomasCollectionWidget.getUrl( *args )
            return ( url, f"Mapbiomas Collection - {year}", 'wms' )

        def finished(exception, result=None):
            self.msgBar.clearWidgets()
            if not exception is None:
                msg = f"Error: Exception: {exception}"
                self.msgBar.pushMessage( self.MODULE, msg, Qgis.Critical, 4 )
                return

            layer = QgsRasterLayer( *result )
            if not layer.isValid():
                print("error summary:", layer.error().summary())
                source = urllib.parse.unquote( layer.source() ).split('&')
                url = [ v for v in source if v.split('=')[0] == 'url' ][0]
                msg = f"!!!Error server: Get {url}"
                self.msgBar.pushCritical( self.MODULE, msg )
                return

            project = QgsProject.instance()
            totalEW = int( layer.customProperty('embeddedWidgets/count', 0) )
            layer.setCustomProperty('embeddedWidgets/count', totalEW + 1 )
            layer.setCustomProperty(f"embeddedWidgets/{totalEW}/id", self.widgetProvider.id() )
            project.addMapLayer(layer)
            root = project.layerTreeRoot()
            ltl = root.findLayer( layer )
            ltl.setExpanded(True)
            return

        if self.metadata is None:
            self.msgBar.pushMessage( self.MODULE, self.messageError, Qgis.Critical, 0 )
            return

        msg = f"Adding layer collection from {self.metadata['url']}"
        self.msgBar.pushMessage( self.MODULE, msg, Qgis.Info, 0 )
        # Task
        args = {
            'description': self.MODULE,
            'function': createLayer,
            'year': self.metadata['years']['max'],
            'on_finished': finished
        }
        task = QgsTask.fromFunction( **args )
        self.taskManager.addTask( task )
