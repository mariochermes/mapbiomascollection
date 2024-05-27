# -*- coding: utf-8 -*-
"""
/***************************************************************************
Name                 : MapBiomas Collection Official
Description          : This plugin enables the acquisition of use and coverage maps from MapBiomas Project (http://mapbiomas.org/).
Date                 : may, 2024
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
__author__ = 'Luiz Cortinhas, Luiz Motta, Mário Hermes'
__date__ = '2024-05-27'
__copyright__ = '(C) 2024, Luiz Cortinhas, Luiz Motta and Mário Hermes'
__revision__ = '$Format:%H$'

import os

from qgis.PyQt.QtCore import QObject, pyqtSlot 
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from .mapbiomascollection import MapBiomasCollection

def classFactory(iface):
  return MapbiomasCollectionPlugin( iface )

class MapbiomasCollectionPlugin(QObject):
  def __init__(self, iface=None):
    super().__init__()
    self.iface = iface
    self.name = u"&MapbiomasCollectionOfficial"
    self.mbc = MapBiomasCollection( iface )

  def initGui(self):
    name = "Mapbiomas Collection Official"
    about = 'Add a MapBiomas collection'
    icon = QIcon( os.path.join( os.path.dirname(__file__), 'mapbiomas.svg' ) )
    self.action = QAction( icon, name, self.iface.mainWindow() )
    self.action.setObjectName( name.replace(' ', '') )
    self.action.setWhatsThis( about )
    self.action.setStatusTip( about )
    self.action.triggered.connect( self.run )

    self.iface.addToolBarIcon( self.action )
    self.iface.addPluginToMenu( self.name, self.action )

    self.mbc.register()

  def unload(self):
    self.iface.removeToolBarIcon( self.action )
    self.iface.removePluginMenu( self.name, self.action )
    del self.action
    if not self.mbc:
      del self.mbc

  @pyqtSlot()
  def run(self):
      self.mbc.run()
 