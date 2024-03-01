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

import re
import json

from odoo import api, models, _
from odoo.tools import float_round

def remove_html_tags(text):
    """Remove html tags from a string"""
    ret = ""
    if isinstance(text, (str, bytes)):
        clean = re.compile('<.*?>')
        ret = re.sub(clean, '', text)
    return ret

class ReportBomStructure(models.AbstractModel):
    _inherit = 'report.mrp.report_bom_structure'

    def _add_engineering_void_data(self, operations):
        """                            
            Maintains coherence column showing data.
        """                            
        for line in operations:        
            line['description'] = ""   
            line['engineering_revision'] = ""
            line['state'] = ""         
        return operations              
                                       
### OVERRIDDEN STANDARD METHODS        
                                       
    @api.model                         
    def _get_component_data(self, parent_bom, parent_product, warehouse, bom_line, line_quantity, level, index, product_info, ignore_stock=False):
        component =  super(ReportBomStructure, self)._get_component_data(parent_bom, parent_product, warehouse, bom_line, line_quantity, level, index, product_info, ignore_stock=ignore_stock)
        product_id = component.get('product', False)
        component['engineering_revision'] = 0 
        component['state'] = ''        
        component['bom_line_id'] = bom_line.id if bom_line else False
        component['bom_type'] = bom_line.type if bom_line else False
        
        if product_id:                 
            description = remove_html_tags(product_id.description)
            component['engineering_revision'] = product_id.engineering_revision
            component['state'] = product_id.state
            component['description'] = description
        return component               
                                       
    @api.model                         
    def _get_bom_data(self, bom, warehouse, product=False, line_qty=False, bom_line=False, level=0, parent_bom=False, parent_product=False, index=0, product_info=False, ignore_stock=False):
        component = super(ReportBomStructure, self)._get_bom_data(bom, warehouse, product=product, line_qty=line_qty, bom_line=bom_line, level=level, parent_bom=parent_bom, parent_product=parent_product, index=0, product_info=product_info, ignore_stock=ignore_stock)
        product_id = component.get('product', False)
        component['engineering_revision'] = 0
        component['state'] = ''
        component['bom_line_id'] = bom_line.id if bom_line else False
        component['bom_type'] = bom_line.type if bom_line else False

        if product_id:                 
            description = remove_html_tags(product_id.description)
            component['engineering_revision'] = product_id.engineering_revision
            component['state'] = product_id.state
            component['description'] = description
        return component               
                                       
    @api.model                         
    def _get_bom_array_lines(self, data, level, unfolded_ids, unfolded, parent_unfolded=True):
        bom_lines = data['components'] 
        lines = []                     
        for bom_line in bom_lines:     
            line_unfolded = ('bom_' + str(bom_line['index'])) in unfolded_ids
            line_visible = level == 1 or unfolded or parent_unfolded
            description = remove_html_tags(bom_line['description'])
            lines.append({             
                'bom_id': bom_line['bom_id'],
                'bom_line_id': bom_line['bom_line_id'],
                'bom_type': bom_line['bom_type'],
                'type': bom_line['type'],
                'name': bom_line['name'],
                'quantity': bom_line['quantity'],
                'quantity_available': bom_line['quantity_available'],
                'quantity_on_hand': bom_line['quantity_on_hand'],
                'producible_qty': bom_line.get('producible_qty', False),
                'engineering_revision': bom_line['engineering_revision'],
                'state': bom_line['state'],
                'description': description,
                'prod_revi': bom_line['engineering_revision'],
                'prod_stat': bom_line['state'],
                'prod_desc': description,
                'uom': bom_line['uom_name'],
                'prod_cost': bom_line['prod_cost'],
                'bom_cost': bom_line['bom_cost'],
                'route_name': bom_line['route_name'],
                'route_detail': bom_line['route_detail'],
                'lead_time': bom_line['lead_time'],
                'level': bom_line['level'],
                'code': bom_line['code'],
                'availability_state': bom_line['availability_state'],
                'availability_display': bom_line['availability_display'],
                'visible': line_visible,
            })                         
            if bom_line.get('components'):
                lines += self._get_bom_array_lines(bom_line, level + 1, unfolded_ids, unfolded, line_visible and line_unfolded)
                                       
        if data['operations']:         
            lines.append({             
                'name': _('Operations'),
                'type': 'operation',   
                'quantity': data['operations_time'],
                'uom': _('minutes'),   
                'bom_cost': data['operations_cost'],
                'level': level,        
                'visible': parent_unfolded,
            })                         
            operations_unfolded = unfolded or (parent_unfolded and ('operations_' + str(data['index'])) in unfolded_ids)
            for operation in data['operations']:
                lines.append({         
                    'name': operation['name'],
                    'type': 'operation',
                    'quantity': operation['quantity'],
                    'uom': _('minutes'),
                    'bom_cost': operation['bom_cost'],
                    'level': level + 1,
                    'visible': operations_unfolded,
                })                     
        if data['byproducts']:         
            lines.append({             
                'name': _('Byproducts'),
                'type': 'byproduct',   
                'uom': False,          
                'quantity': data['byproducts_total'],
                'bom_cost': data['byproducts_cost'],
                'level': level,
                'visible': parent_unfolded,
            })
            byproducts_unfolded = unfolded or (parent_unfolded and ('byproducts_' + str(data['index'])) in unfolded_ids)
            for byproduct in data['byproducts']:
                lines.append({
                    'name': byproduct['name'],
                    'type': 'byproduct',
                    'quantity': byproduct['quantity'],
                    'uom': byproduct['uom'],
                    'prod_cost': byproduct['prod_cost'],
                    'bom_cost': byproduct['bom_cost'],
                    'level': level + 1,
                    'visible': byproducts_unfolded,
                })
        return lines

    def _get_operation_line(self, product, bom, qty, level, index):
        data = super(ReportBomStructure, self)._get_operation_line(product, bom, qty, level, index)
        self._add_engineering_void_data(data)
        return data
 
    @api.model
    def _get_report_values(self, docids, data=None):
        data['childs']=False
        data['quantity']=1
        if data.get('unfolded_ids'):
            if not list(set(json.loads(data.get('unfolded_ids')))):
                data.pop('unfolded_ids')
        return super(ReportBomStructure, self)._get_report_values(docids, data)

### OVERRIDDEN STANDARD METHODS 

