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
import time

from book_collector     import BookCollector,packDocuments

from odoo import api, models
from odoo.report.interface import report_int

def create_report(entity, ids, datas, context=None):
    """
        Used directly from Odoo interface.
    """
    docType=entity.env['plm.document']
    docRepository=docType._get_filestore()
    documents = docType.browse(ids)
    userType=entity.env['res.users']
    user=userType.browse(entity._uid)
    msg="Printed by "+str(user.name)+" : "+ str(time.strftime("%d/%m/%Y %H:%M:%S"))
    output=BookCollector(jumpFirst=False, customTest=(False, msg), bottomHeight=10)
    return packDocuments(docRepository, documents, output)

class document_custom_report(report_int):
    def create(self, cr, uid, ids, datas, context=None):
        env = api.Environment(cr, uid, context or {})
        docType=env['plm.document']
        docRepository=docType._get_filestore()
        documents = docType.browse(ids)
        user=env['res.users'].browse(uid)
        msg="Printed by "+str(user.name)+" : "+ str(time.strftime("%d/%m/%Y %H:%M:%S"))
        output=BookCollector(jumpFirst=False, customTest=(False, msg), bottomHeight=10)
        return packDocuments(docRepository, documents, output)
    
document_custom_report('report.plm.document.pdf')