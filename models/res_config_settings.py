# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'
    """
        Extends as enterprise module using the workflow management tool.
    """
    
    module_wkf = fields.Boolean("Advanced Workflow Management")
