# -*- coding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2016 TechSpell srl (<http://techspell.eu>). All Rights Reserved
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

from openerp.osv import orm, fields
import openerp.tools as tools


class report_plm_component(orm.Model):
    _name = "report.plm_component"
    _description = "Report Component"
    _auto = False

    _columns = {
        'count_component_draft': fields.integer('Draft', readonly=True),
        'count_component_confirmed': fields.integer('Confirmed', readonly=True),
        'count_component_released': fields.integer('Released', readonly=True),
        'count_component_modified': fields.integer('Under Modify', readonly=True),
        'count_component_obsoleted': fields.integer('Obsoleted', readonly=True),
    }

    def init(self, cr):
        tools.drop_view_if_exists(cr, 'report_plm_component')
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

