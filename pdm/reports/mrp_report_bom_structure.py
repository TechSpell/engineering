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

from odoo import api, models, _
from odoo.tools import float_round

class ReportBomStructure(models.AbstractModel):
    _inherit = 'report.mrp.report_bom_structure'

    def _add_engineering_data(self, components):
        for line in components:
            line['prod_desc'] = ""
            line['prod_revi'] = ""
            line['prod_stat'] = ""
            prod_id = line.get('prod_id')
            if prod_id:
                prod_id = self.env['product.product'].browse(prod_id)
                line['prod_desc'] = prod_id.description
                line['prod_revi'] = prod_id.engineering_revision
                line['prod_stat'] = prod_id.state

        return True

    def _add_engineering_void_data(self, operations):
        """
            Maintains coherence column showing data.
        """
        for line in operations:
            line['desc'] = ""
            line['revi'] = ""
            line['stat'] = ""
        return operations
   
### OVERRIDDEN STANDARD METHODS 

    def _get_bom_lines(self, bom, bom_quantity, product, line_id, level):
        components, total = super(ReportBomStructure, self)._get_bom_lines(bom, bom_quantity, product, line_id, level)
        self._add_engineering_data(components)
        return components, total

    def _get_pdf_line(self, bom_id, product_id=False, qty=1, child_bom_ids=[], unfolded=False):
        data = super(ReportBomStructure, self)._get_pdf_line(bom_id, product_id, qty, child_bom_ids, unfolded)
        self._add_engineering_data(data['lines'])
        return data

    def _get_operation_line(self, bom, qty, level):
        data = super(ReportBomStructure, self)._get_operation_line(bom, qty, level)
        self._add_engineering_void_data(data)
        return data
 
    @api.model
    def _get_report_values(self, docids, data=None):
        data['childs']=False
        data['quantity']=1
        return super(ReportBomStructure, self)._get_report_values(docids, data)

### OVERRIDDEN STANDARD METHODS 

