 # -*- coding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2016 TechSpell srl (<http://techspell.eu>). All Rights Reserved
#    $Id$
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
import StringIO
import os
import random
import time
import string
from report.interface import report_int
from book_collector import BookCollector,packDocuments

from openerp import pooler

class component_custom_report(report_int):
    """
        Return a pdf report of each printable document attached to given Part ( level = 0 one level only, level = 1 all levels)
    """
    def create(self, cr, uid, ids, datas, context=None):
        self.pool = pooler.get_pool(cr.dbname)
        docRepository=self.pool['plm.document']._get_filestore(cr)
        user = self.pool['res.users'].browse(cr, uid, uid, context=context)
        msg = "Printed by "+str(user.name)+" : "+ str(time.strftime("%d/%m/%Y %H:%M:%S"))
        output = BookCollector(jumpFirst=False, customTest=(False, msg), bottomHeight=10)
        documents=[]
        for component in self.pool['product.product'].browse(cr, uid, ids, context=context):
            documents.extend(component.linkeddocuments)
        return packDocuments(docRepository,list(set(documents)),output)

component_custom_report('report.product.product.pdf')

class component_one_custom_report(report_int):
    """
        Return a pdf report of each printable document attached to children in a Bom ( level = 0 one level only, level = 1 all levels)
    """
    def create(self, cr, uid, ids, datas, context=None):
        self.pool = pooler.get_pool(cr.dbname)
        context = context or self.pool['res.users'].context_get(cr, uid)
        docRepository=self.pool['plm.document']._get_filestore(cr)
        componentType=self.pool['product.product']
        user=self.pool['res.users'].browse(cr, uid, uid, context=context)
        msg = "Printed by "+str(user.name)+" : "+ str(time.strftime("%d/%m/%Y %H:%M:%S"))
        output  = BookCollector(jumpFirst=False,customTest=(False,msg),bottomHeight=10)
        documents=[]
        for component in componentType.browse(cr, uid, ids, context=context):
            documents.extend(component.linkeddocuments)
            idcs=componentType._getChildrenBom(cr, uid, component, 0, context=context)
            for child in componentType.browse(cr, uid, idcs, context=context):
                documents.extend(child.linkeddocuments)
        return packDocuments(docRepository,list(set(documents)),output)

component_one_custom_report('report.one.product.product.pdf')

class component_all_custom_report(report_int):
    """
        Return a pdf report of each printable document attached to children in a Bom ( level = 0 one level only, level = 1 all levels)
    """
    def create(self, cr, uid, ids, datas, context=None):
        self.pool = pooler.get_pool(cr.dbname)
        context = context or self.pool['res.users'].context_get(cr, uid)
        docRepository=self.pool['plm.document']._get_filestore(cr)
        componentType=self.pool['product.product']
        user=self.pool['res.users'].browse(cr, uid, uid, context=context)
        msg = "Printed by "+str(user.name)+" : "+ str(time.strftime("%d/%m/%Y %H:%M:%S"))
        output  = BookCollector(jumpFirst=False,customTest=(False,msg),bottomHeight=10)
        documents=[]
        for component in componentType.browse(cr, uid, ids, context=context):
            documents.extend(component.linkeddocuments)
            idcs=componentType._getChildrenBom(cr, uid, component, 1, context=context)
            for child in componentType.browse(cr, uid, idcs, context=context):
                documents.extend(child.linkeddocuments)
        return packDocuments(docRepository,list(set(documents)),output)

component_all_custom_report('report.all.product.product.pdf')
