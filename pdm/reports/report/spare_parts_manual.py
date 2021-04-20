# -*- encoding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2011-2015 OmniaSolutions srl (<http://www.omniasolutions.eu>). All Rights Reserved
#    Copyright (C) 2016-2020 Techspell srl (<http://www.techspell.eu>). All Rights Reserved
#    Copyright (C) 2020-2021 Didotech srl (<http://www.didotech.com>). All Rights Reserved
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
import logging
import time
from io import BytesIO


from odoo import _, api, models

from .common import getLinkedDocument, getPDFStream, moduleName, usefulInfos

#constant
FIRST_LEVEL=0
BOM_SHOW_FIELDS=['Position','Code','Description','Quantity']


thisModuleName=moduleName()

docRepository=""


class report_spare_parts_header(models.AbstractModel):
    _name = 'report.pdm.spare_bom_header'
    _description = "Report Spare Bom Header"

    def _get_report_values(self, docids, data=None):
        products = self.env['product.product'].browse(docids)
        return {'docs': products,
                'time': time,
                'getLinkedDocument': getLinkedDocument}


class report_spare_parts_document(models.AbstractModel):
    """
        Evaluates the BoM structure spare parts manual
    """
    _name = 'report.pdm.spare_pdf_one'
    _description = "Report Spare Bom One Level"

    @api.model
    def pdfcreate(self, components):
        ret=(False, '')
        recursion=True
        if self._name == 'report.pdm.spare_pdf_one':
            recursion=False
        componentType=self.env['product.product']
        bomType=self.env['mrp.bom']
        _, bookCollector = usefulInfos(self.env)
        for component in components:
            self.processedObjs = []
            buf = self.getFirstPage([component.id])
            bookCollector.addPage(buf)
            self.getSparePartsPdfFile(component, bookCollector, componentType, bomType, recursion)
        if not(bookCollector is None):
            pdf_string = BytesIO()
            bookCollector.collector.write(pdf_string)
            output= pdf_string.getvalue()
            pdf_string.close()
            byteString = b"data:application/pdf;base64," + base64.b64encode(output)
            ret=byteString.decode('UTF-8')
        else:
            logging.warning('Unable to create PDF')
        return ret

    def getSparePartsPdfFile(self, product, bookCollector, componentTemplate, bomTemplate, recursion):
        if not(product in self.processedObjs):
            packedObjs = []
            bomObjs = bomTemplate.search([('product_id', '=', product.id), ('type', '=', 'spbom')])
            if len(bomObjs) < 1:
                bomObjs = bomTemplate.search([('product_tmpl_id', '=', product.product_tmpl_id.id), ('type', '=', 'spbom')])

            if not(bomObjs==None) and (len(bomObjs)>0):
                self.processedObjs.append(product)
                pdf = self.env.ref('pdm.bom_structure_one').render_qweb_pdf([bomObjs.id])[0]
                if not(pdf==None):
                    pageStream = BytesIO()
                    pageStream.write(pdf)
                    bookCollector.addPage(pageStream)
                    for pageStream, status in self.getSparePdfbyProduct(bomObjs.product_id):
                        bookCollector.addPage(pageStream, status)
                        
                for bom_line in bomObjs.bom_line_ids:
                    packedObjs.append(bom_line.product_id)
                if recursion and (len(packedObjs) > 0):
                    for packedObj in list(set(packedObjs).difference(set(self.processedObjs))):
                        self.getSparePartsPdfFile(packedObj, bookCollector, componentTemplate, bomTemplate, recursion)

    def getSparePdfbyProduct(self, product):
        ret=[]
        for objDocument in getLinkedDocument(product, checkStatus=False, used4Spare=True):
            value=getPDFStream(docRepository, objDocument)
            if value:
                ret.append((value, _(objDocument.state)))
        return ret

    def getFirstPage(self, ids):
        strbuffer = BytesIO()
        pdf = self.env.ref('pdm.report_pdm_product_spare_parts_header').render_qweb_pdf(ids)[0]
        strbuffer.write(pdf)
        return strbuffer

    @api.model
    def _get_report_values(self, docids, data=None):
        documents = self.env['product.product'].browse(docids)
        return {'docs': documents,
                'get_content': self.pdfcreate}


class ReportSpareDocumentAll(report_spare_parts_document):
    _name = 'report.pdm.spare_pdf_all'
    _description = "Report Spare Bom All Levels"

