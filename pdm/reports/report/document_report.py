# -*- coding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2011-2015 OmniaSolutions srl (<http://www.omniasolutions.eu>). All Rights Reserved
#    Copyright (C) 2016-2020 Techspell srl (<http://www.techspell.eu>). All Rights Reserved
#    Copyright (C) 2020-2021 Didotech srl (<http://www.didotech.com>). All Rights Reserved
#    
#    Created on : 2016-03-01
#    Author : Fabio Colognesi
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

from book_collector     import BookCollector,packDocuments
import time

from openerp.report.interface import report_int
from openerp import pooler

def create_report(cr, uid, ids, datas, context=None):
    pool = pooler.get_pool(cr.dbname)
    docType=pool['plm.document']
    docRepository=docType._get_filestore(cr)
    documents = docType.browse(cr, uid, ids, context=context)
    userType=pool.get('res.users')
    user=userType.browse(cr, uid, uid, context=context)
    msg = "Printed by "+str(user.name)+" : "+ str(time.strftime("%d/%m/%Y %H:%M:%S"))
    output  = BookCollector(jumpFirst=False,customTest=(False,msg),bottomHeight=10)
    return packDocuments(docRepository,documents,output)

class document_custom_report(report_int):
    def create(self, cr, uid, ids, datas, context=None):
        self.pool = pooler.get_pool(cr.dbname)
        docType=self.pool['plm.document']
        docRepository=docType._get_filestore(cr)
        documents = docType.browse(cr, uid, ids, context=context)
        userType=self.pool['res.users']
        user=userType.browse(cr, uid, uid, context=context)
        msg = "Printed by "+str(user.name)+" : "+ str(time.strftime("%d/%m/%Y %H:%M:%S"))
        output  = BookCollector(jumpFirst=False,customTest=(False,msg),bottomHeight=10)
        return packDocuments(docRepository,documents,output)
    
document_custom_report('report.plm.document.pdf')