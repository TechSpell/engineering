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
import base64, logging

from openerp import api, models, _, osv
from openerp.report.interface import report_int
from openerp.report.render import render

try:
    from PyPDF2 import PdfFileWriter, PdfFileReader
except Exception as msg:
    logging.error("This module requires PyPDF2. Please contact your system administrator to install it.")

class external_pdf(render):

    """ Generate External PDF """

    def __init__(self, pdf):
        render.__init__(self)
        self.pdf = pdf
        self.output_type = 'pdf'

    def _render(self):
        return self.pdf

class checkout_custom_report(report_int):
    """
        Return a pdf report of each printable document.
    """
    def create(self, cr, uid, ids, datas, context=None):
        ret=(False, '')
        env = api.Environment(cr, uid, context or {})
        try:
            output=PdfFileWriter()
        except Exception as msg:
            raise osv.except_osv(_("This module requires PyPDF2. Please contact your system administrator to install it."))
        packed=[]
        document=None
        checkouts=env['plm.checkout'].browse(ids)
        for checkout in checkouts:
            document=checkout.documentid
            if document.printout:
                if not document.id in packed:   
                    input1 = PdfFileReader(StringIO.StringIO(base64.decodestring(document.printout)))
                    output.addPage(input1.getPage(0))
                    packed.append(document.id)
        if document!=None:
            pdf_string = StringIO.StringIO()
            output.write(pdf_string)
            self.obj=external_pdf(pdf_string.getvalue())
            self.obj.render()
            pdf_string.close()
            ret=(self.obj.pdf, 'pdf')
        return ret

checkout_custom_report('report.plm.checkout.pdf')