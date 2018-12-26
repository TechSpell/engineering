# -*- encoding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2016-2018 TechSpell srl (<http://techspell.eu>). All Rights Reserved
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
from .common import usefulInfos, emptyDocument

class report_plm_document(models.AbstractModel):
    _name = 'report.pdm.document_pdf'
    _description = 'Report PDF Document'

    @api.model
    def get_pdf_content(self, documents=None):
        ret = emptyDocument
        if len(documents)>0:
            docRepository, bookCollector = usefulInfos(self.env)
            documentContent=packDocuments(docRepository, documents, bookCollector)
            if len(documentContent)>0:
                ret=documentContent[0]
        return ret

    @api.model
    def render_qweb_pdf(self, documents=None, data=None):
        content = self.get_pdf_content(documents)
        byteString = b"data:application/pdf;base64," + base64.encodebytes(content)
        return byteString.decode('UTF-8')

    @api.model
    def get_report_values(self, docids, data=None):
        documents = self.env['plm.document'].browse(docids)
        return {'docs': documents,
                'get_content': self.render_qweb_pdf}
