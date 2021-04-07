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

from odoo        import models, fields, api
from odoo.tools import drop_view_if_exists
from odoo.exceptions import UserError

from .book_collector import packDocuments
from .common import usefulInfos, getLinkedDocument, emptyDocument, moduleName

thisModuleName=moduleName()

class report_plm_component(models.AbstractModel):
    _name='%s.product_product_pdf' %(thisModuleName)
    _description = "Base PDF Report Component"

    @api.model
    def _render_qweb_pdf(self, products=None, level=0, checkState=False, data=None):
        documents = []
        processed=[]
        content = emptyDocument()
        docRepository, bookCollector = usefulInfos(self.env)
        productObjType=self.env['product.product']

        for product in products:
            if not(product.name  in processed):
                documents.extend(getLinkedDocument(product, checkState))
                processed.append(product.name)
                if level > -1:
                    for childProduct in productObjType.browse(product._getChildrenBom(product, level)):
                        if not(childProduct.name  in processed):
                            documents.extend(getLinkedDocument(childProduct, checkState))
                            processed.append(product.name)
                            
        if len(documents)>0:
            documentContent=packDocuments(docRepository, documents, bookCollector)
            if len(documentContent)>0:
                content=documentContent[0]
                
        byteString = b"data:application/pdf;base64," + base64.encodebytes(content)
        return byteString.decode('UTF-8')

    @api.model
    def _get_report_values(self, docids, data=None):
        products = self.env['product.product'].browse(docids)
        return {'docs': products,
                'get_content': self._render_qweb_pdf}


class ReportProductPdf(report_plm_component):
    _template='%s.product_product_pdf' %(thisModuleName)
    _name = "report.%s" %(_template)


class ReportOneLevelProductPdf(report_plm_component):
    _template='%s.one_product_product_pdf' %(thisModuleName)
    _name = "report.%s" %(_template)


class ReportAllLevelProductPdf(report_plm_component):
    _template='%s.all_product_product_pdf' %(thisModuleName)
    _name = "report.%s" %(_template)


class ReportSpareProductPdf(report_plm_component):
    _template='%s.spare_pdf_all' %(thisModuleName)
    _name = "report.%s" %(_template)


class ReportSpareOneProductPdf(report_plm_component):
    _template='%s.spare_pdf_one' %(thisModuleName)
    _name = "report.%s" %(_template)

