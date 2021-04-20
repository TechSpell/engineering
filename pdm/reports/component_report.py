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

from odoo        import models, fields, api
from odoo.tools import drop_view_if_exists

class report_plm_component(models.Model):
    _name = "report.plm_component"
    _description = "Report Component"
    _auto = False
            
    count_component_draft       =   fields.Integer('Draft', readonly=True)
    count_component_confirmed   =   fields.Integer('Confirmed', readonly=True)
    count_component_released    =   fields.Integer('Released', readonly=True)
    count_component_modified    =   fields.Integer('Under Modify', readonly=True)
    count_component_obsoleted   =   fields.Integer('Obsoleted', readonly=True)


    @api.model_cr
    def init(self):
        cr = self._cr
        drop_view_if_exists(cr, 'report_plm_component')
        cr.execute("""
            CREATE OR REPLACE VIEW report_plm_component AS (
                SELECT
                    (SELECT count(id)+1 FROM product_template) as id,
                    (SELECT count(*) FROM product_template WHERE state = 'draft') AS count_component_draft,
                    (SELECT count(*) FROM product_template WHERE state = 'confirmed') AS count_component_confirmed,
                    (SELECT count(*) FROM product_template WHERE state = 'released') AS count_component_released,
                    (SELECT count(*) FROM product_template WHERE state = 'undermodify') AS count_component_modified,
                    (SELECT count(*) FROM product_template WHERE state = 'obsoleted') AS count_component_obsoleted
             )
        """)


class report_plm_component_year(models.Model):
    _name = "report.plm_component.year"
    _description = "Report Component Status by Year"
    _auto = False
            
    year        =   fields.Char('Year', size=64,readonly=True)
    state       =   fields.Char('Status', size=24,readonly=True)
    nbr         =   fields.Integer('# of Products', readonly=True)


    @api.model_cr
    def init(self):
        cr = self._cr
        drop_view_if_exists(cr, 'report_plm_component_year')
        cr.execute("""
            create or replace view report_plm_component_year as (
                select min(f.id) as id,
                    EXTRACT(YEAR FROM f.create_date) as year,
                    f.state as state,
                    count(*) as nbr
                from product_template f
                group by EXTRACT(YEAR FROM f.create_date), f.state
              )
        """)

