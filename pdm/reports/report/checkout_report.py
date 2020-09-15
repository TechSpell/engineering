# -*- encoding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2020-2020 Didotech srl (<http://www.didotech.com>). All Rights Reserved
#    
#    Created on : 2018-03-01
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

import base64

from odoo import api, models

from .book_collector import packDocuments
from .common import usefulInfos, emptyDocument, moduleName

thisModuleName=moduleName()


class report_plm_checkout(models.AbstractModel):
    _template='%s.checkout_pdf' %(thisModuleName)
    _name = "report.%s" %(_template)
    _description = "Base Report Checkout"

    @api.model
    def render_qweb_pdf(self, checkouts=None, data=None):
        documents = []
        processed=[]
        content = emptyDocument()
        docRepository, bookCollector = usefulInfos(self.env)
        for checkout in checkouts:
            if not(checkout.documentid.name in processed):
                documents.append(checkout.documentid)
                processed.append(checkout.documentid.name)

        if len(documents)>0:
            documentContent=packDocuments(docRepository, documents, bookCollector)
            if len(documentContent)>0:
                content=documentContent[0]
                
        byteString = b"data:application/pdf;base64," + base64.encodebytes(content)
        return byteString.decode('UTF-8')

    @api.model
    def _get_report_values(self, docids, data=None):
        checkouts = self.env['plm.checkout'].browse(docids)
        return {'docs': checkouts,
                'get_content': self.render_qweb_pdf}
