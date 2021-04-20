# -*- encoding: utf-8 -*-
##############################################################################
#
#    ServerPLM, Open Source Product Lifcycle Management System    
#    Copyright (C) 2011-2015 OmniaSolutions srl (<http://www.omniasolutions.eu>). All Rights Reserved
#    Copyright (C) 2016-2020 Techspell srl (<http://www.techspell.eu>). All Rights Reserved
#    Copyright (C) 2020-2021 Didotech srl (<http://www.didotech.com>). All Rights Reserved
#    
#    Created on : 2016-03-01
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

import logging
from datetime import datetime

from openerp.osv import fields, orm
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

from .common import BOMTYPES, getListIDs, getCleanList, getListedDatas, \
                    isAdministrator, isDraft, isAnyReleased, isReleased, isObsoleted
                    

# To be adequate to plm.document class states
USED_STATES = [('draft', 'Draft'), ('confirmed', 'Confirmed'), ('released', 'Released'), ('undermodify', 'UnderModify'),
               ('obsoleted', 'Obsoleted')]


class plm_component(orm.Model):
    _name = 'product.template'
    _inherit = 'product.template'
    _columns = {
        'state': fields.selection(USED_STATES, 'Status', help="The status of the product in its LifeCycle.",
                                  readonly="True"),
        'engineering_code': fields.char('Part Number',
                                        help="This is engineering reference to manage a different P/N from item Name.",
                                        size=64),
        'engineering_revision': fields.integer('Revision', required=True, help="The revision of the product."),
        'engineering_writable': fields.boolean('Writable'),
        'engineering_material': fields.char('Raw Material', size=128, required=False,
                                            help="Raw material for current product, only description for titleblock."),
        #  'engineering_treatment': fields.char('Treatment',size=64,required=False,help="Thermal treatment for current product"),
        'engineering_surface': fields.char('Surface Finishing', size=128, required=False,
                                           help="Surface finishing for current product, only description for titleblock."),
    }

    _defaults = {
                 'state': lambda *a: 'draft',
                 'engineering_revision': lambda self,cr,uid,ctx:0,
                 'engineering_writable': lambda *a: True,
                 'type': 'product',
                 'standard_price': 0,
                 'volume':0,
                 'weight':0,
                 'cost_method':0,
                 'sale_ok':0,
                 'state':'draft',
                 'mes_type':'fixed',
                 'cost_method':'standard',
    }
    _sql_constraints = [
        ('partnumber_uniq', 'unique (engineering_code,engineering_revision)', _('Part Number has to be unique!'))
    ]

    def init(self, cr):
        cr.execute("""
            -- Index: product_template_engcode_index
             
            DROP INDEX IF EXISTS product_template_engcode_index;
             
            CREATE INDEX product_template_engcode_index
              ON product_template
              USING btree
              (engineering_code);
            """)
 
        cr.execute("""
            -- Index: product_template_engcoderev_index
             
            DROP INDEX IF EXISTS product_template_engcoderev_index;
             
            CREATE INDEX product_template_engcoderev_index
              ON product_template
              USING btree
              (engineering_code, engineering_revision);
            """)

    def write(self, cr, uid, ids, vals, context=None):
        ret=False
        if vals:
            context = context or self.pool['res.users'].context_get(cr, uid)
            for prodItem in self.browse(cr, uid, ids, context=context):
                if not (prodItem.engineering_code):
                    if not vals.get('engineering_code', ''):
                        vals.update({'engineering_code': prodItem.name})
#                 elif not vals.get('engineering_code', ''):
#                         vals.update({'engineering_code': prodItem.name})
                break
            ret=super(plm_component, self).write(cr, uid, ids, vals, context=context)
        return ret

    def create(self, cr, uid, vals, context=None):
        ret=False
        if vals:
            if not vals.get('engineering_code', ''):
                vals['engineering_code'] = vals['name']
            ret=super(plm_component, self).create(cr, uid, vals, context=context)
        return ret


class plm_component_document_rel(orm.Model):
    _name = 'plm.component.document.rel'
    _description = "Component Document Relations"
    _columns = {
        'component_id': fields.many2one('product.product', 'Linked Component', ondelete='cascade'),
        'document_id': fields.many2one('plm.document', 'Linked Document', ondelete='cascade'),
    }

    _sql_constraints = [
        (
            'relation_unique', 'unique(component_id,document_id)',
            _('Component and Document relation has to be unique !')),
    ]
    
    def CleanStructure(self, cr, uid, relations, context=None):
        res = []
        ids=[]
        criteria=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        for document_id, component_id in relations:
            latest = (document_id, component_id)
            if latest in res:
                continue
            res.append(latest)
            if document_id and component_id:
                criteria=[ ('document_id', '=', document_id), ('component_id', '=', component_id) ]
            elif document_id:
                criteria=[ ('document_id', '=', document_id) ]
            elif component_id:
                criteria=[ ('component_id', '=', component_id) ]
            if criteria:
                ids.extend(self.search(cr, uid, criteria, context=context))
        if ids:
            self.unlink(cr, uid, ids, context=context)

    def SaveStructure(self, cr, uid, relations=[], level=0, currlevel=0, context=None):
        """
            Save Document relations
        """
        ret=False
        context = context or self.pool['res.users'].context_get(cr, uid)

        def cleanStructure(relations):
            self.CleanStructure(cr, uid, relations, context=context)

        def saveChild(args):
            """
                save the relation 
            """
            ret=False
            try:
                res = {}
                res['document_id'], res['component_id'] = args
                self.create(cr, uid, res, context=context)
            except:
                logging.error("saveChild : Unable to create a link. Arguments (%s)." % (str(args)))
                ret=True
            return ret

        if relations:      # no relation to save
            cleanStructure(relations)
            for relation in relations:
                ret=saveChild(relation)
        return ret

HELP ="Use a phantom bill of material in raw materials lines that have to be "                                            
HELP+="automatically computed on a production order and not one per level."             
HELP+="If you put \"Phantom/Set\" at the root level of a bill of material "              
HELP+="it is considered as a set or pack: the products are replaced by the components " 
HELP+="between the sale order to the picking without going through the production order." 
HELP+="The normal BoM will generate one production order per BoM level."                   

         
class plm_relation_line(orm.Model):
    _name = 'mrp.bom.line'
    _inherit = 'mrp.bom.line'
    _columns = {
                'create_date': fields.datetime(_('Creation Date'), readonly=True),
                'source_id': fields.many2one('plm.document','name',ondelete='no action', readonly=True,help="This is the document object that declares this BoM."),
                'type': fields.selection(BOMTYPES, _('BoM Type'), required=True, help=_(HELP)),
                 'itemnum': fields.integer(_('CAD Item Position'),help="This is the item reference position into the CAD document that declares this BoM."),
                'itemlbl': fields.char(_('CAD Item Position Label'),size=64)
                }
    _defaults = {
        'product_uom' : 1,
    }
    
    _order = 'itemnum'

    def onchange_plmproduct_id(self,cr, uid, ids, context=None):
        """ Changes UoM if product_id changes.
        @param product_id: Changed product_id
        @return:  Dictionary of changed values
        """
        values = {}
        father_id=False
        product_id=False
        if context and 'product_id' in context and 'father_id' in context and 'father_tmpl_id' in context:
            options=self.pool['plm.config.settings'].GetOptions(cr, uid, context=context)
            prodTypeObj=self.pool['product.product']
            father_id=context['father_id']
            if not father_id:
                fatherObj=prodTypeObj.getFromTemplateID(cr, uid, context['father_tmpl_id'], context=context)
                if fatherObj:
                    father_id=fatherObj.id
            product_id=context['product_id']
            if father_id and product_id:
                prodTypeObj.alreadyListed=[]
                productObj=prodTypeObj.browse(cr, uid, product_id, context=context)
                fatherIDs=prodTypeObj.recurse_father_part_compute(cr, uid, [father_id, product_id], context=context)
                if (father_id == product_id) or (product_id in fatherIDs[father_id]):
                    logging.warning("Writing BoM check: This is a circular reference to: %s - %d." %(productObj.product_tmpl_id.name, productObj.product_tmpl_id.engineering_revision))
                    values.update({'product_id': False})
                if not options.get('opt_duplicatedrowsinbom', True):
                    listed_products=[]
                    if 'parent' in context:
                        if 'bom_line_ids' in context['parent']:
                            mrp_bom_lines=context['parent']['bom_line_ids']
                            for mrp_bom_line in mrp_bom_lines:
                                prod_id=False
                                req, bom_line, vals=mrp_bom_line
                                if req and req!=2:
                                    if bom_line:
                                        prod_id=self.browse(cr, uid, bom_line, context=context).product_id.id
                                else:
                                    if vals and 'product_id' in vals:
                                        prod_id=vals['product_id']
                                if prod_id:
                                    listed_products.append(prod_id)
                        if (product_id in listed_products):
                            logging.warning("Writing BoM check: This is a duplicated line : %s - %d." %(productObj.product_tmpl_id.name, productObj.product_tmpl_id.engineering_revision))
                            values.update({'product_id': False})
                if options.get('opt_autonumbersinbom', False):
                    if 'parent' in context:
                        length=0
                        step=options.get('opt_autostepinbom', 5)
                        if 'bom_line_ids' in context['parent']:
                            mrp_bom_lines=context['parent']['bom_line_ids']
                            length=len(mrp_bom_lines)
                        values.update({'itemnum': step*(length+1) })
                if options.get('opt_autotypeinbom', False):
                    if ('parent' in context) and ('type' in context['parent']):
                        values.update({'type': context['parent']['type'] })
        if values:
            return {'value': values }



class plm_relation(orm.Model):
    _name = 'mrp.bom'
    _inherit = 'mrp.bom'
    _columns = {
        'create_date': fields.datetime(_('Creation Date'), readonly=True),
        'source_id': fields.many2one('plm.document', 'name', ondelete='no action', readonly=True,
                                     help='This is the document object that declares this BoM.'),
        'type': fields.selection(BOMTYPES, _('BoM Type'), required=True, help=_(HELP)),
        'itemnum': fields.integer(_('Cad Item Position')),
        'itemlbl': fields.char(_('Cad Item Position Label'), size=64),
        'weight': fields.float('Weight', digits_compute=dp.get_precision('Stock Weight'),
                                   help="The BoM net weight in Kg."),
    }
    _defaults = {
        'product_uom' : 1,
        'weight' : 0.0,
    }

    def init(self, cr):
        self._packed = []

    def _insertlog(self, cr, uid, ids, changes={}, note={}, context=None):
        newID=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        op_type, op_note=["unknown",""]
        for bomObject in self.browse(cr, uid, getListIDs(ids), context=context):
            if note:
                op_type="{type}".format(type=note['type'])
                op_note="{reason}".format(reason=note['reason'])
            elif changes:
                op_type='change value'
                op_note=self.pool['plm.logging'].getchanges(cr, uid, bomObject, changes, context=context)
            if op_note:
                values={
                        'name': bomObject.product_id.name,
                        'revision': "{major}".format(major=bomObject.product_id.engineering_revision),
                        'type': self._name,
                        'op_type': op_type,
                        'op_note': op_note,
                        'op_date': datetime.now(),
                        'userid': uid,
                        }
                objectItem=self.pool['plm.logging'].create(cr, uid, values, context=context)
                if objectItem:
                    newID=objectItem
        return newID

    def _getinbomidnullsrc(self, cr, uid, pid, context=None):
        counted = []
        bomLType=self.pool['mrp.bom.line']
        context = context or self.pool['res.users'].context_get(cr, uid)
        ids = bomLType.search(cr, uid, [('product_id', '=', pid), ('bom_id', '!=', False),
                                     ('type', 'in', ['ebom', 'normal', 'spbom'])])
        for obj in bomLType.browse(cr, uid, getListIDs(ids), context=context):
            if not obj.bom_id in counted:
                counted.append(obj.bom_id)
        return counted

    def _getinbom(self, cr, uid, pid, sid, context=None):
        counted = []
        context = context or self.pool['res.users'].context_get(cr, uid)
        bomLType=self.pool['mrp.bom.line']
        ids = bomLType.search(cr, uid, [('product_id', '=', pid), ('bom_id', '!=', False), ('source_id', '=', sid),
                                    ('type', 'in', ['ebom', 'normal', 'spbom'])])
        for obj in bomLType.browse(cr, uid, getListIDs(ids), context=context):
            if not obj.bom_id in counted:
                counted.append(obj.bom_id)
        return counted

    def _getbomidnullsrc(self, cr, uid, pid, context=None):
        context = context or self.pool['res.users'].context_get(cr, uid)
        templId=self.pool['product.product'].getTemplateItem(cr, uid, pid, context=context)
        ids = self.search(cr, uid, [('product_tmpl_id', '=', templId.id), ('type', 'in', ['ebom', 'normal', 'spbom'])])
        return self.browse(cr, uid, getListIDs(ids), context=None)
    
    def _getbomid(self, cr, uid, pid, sid, context=None):
        context = context or self.pool['res.users'].context_get(cr, uid)
        ids = self._getidbom(cr, uid, pid, sid)
        return self.browse(cr, uid, getListIDs(ids), context=None)

    def _getidbom(self, cr, uid, pid, sid, context=None):
        context = context or self.pool['res.users'].context_get(cr, uid)
        templId=self.pool['product.product'].getTemplateItem(cr, uid, pid, context=context)
        ids = self.search(cr, uid, [('product_tmpl_id', '=', templId.id), ('type', 'in', ['ebom', 'normal', 'spbom'])])
        return getCleanList(ids)

    def _getpackdatas(self, cr, uid, relDatas, context=None):
        prtDatas = {}
        context = context or self.pool['res.users'].context_get(cr, uid)
        tmpids = getListedDatas(relDatas)
        if len(tmpids) < 1:
            return prtDatas
        compType = self.pool['product.product']
        tmpDatas = compType.read(cr, uid, tmpids)
        for tmpData in tmpDatas:
            for keyData in tmpData.keys():
                if tmpData[keyData]==None:
                    del tmpData[keyData]
            prtDatas[str(tmpData['id'])] = tmpData
        return prtDatas

    def _getpackreldatas(self, cr, uid, relDatas, prtDatas, context=None):
        relids = {}
        relationDatas = {}
        context = context or self.pool['res.users'].context_get(cr, uid)
        tmpids = getListedDatas(relDatas)
        if len(tmpids) < 1:
            return prtDatas
        for keyData in prtDatas.keys():
            tmpData = prtDatas[keyData]
            if len(tmpData['bom_ids']) > 0:
                relids[keyData] = tmpData['bom_ids'][0]

        if len(relids) < 1:
            return relationDatas
        setobj = self.pool['mrp.bom']
        for keyData in relids.keys():
            relationDatas[keyData] = setobj.read(cr, uid, relids[keyData])
        return relationDatas

    def _bomid(self, cr, uid, pid, sid=None, context=None):
        context = context or self.pool['res.users'].context_get(cr, uid)
        if not sid:
            return self._getbomidnullsrc(cr, uid, pid, context=context)
        else:
            return self._getbomid(cr, uid, pid, sid, context=context)

    def _inbomid(self, cr, uid, pid, sid=None, context=None):
        context = context or self.pool['res.users'].context_get(cr, uid)
        if not sid:
            return self._getinbomidnullsrc(cr, uid, pid, context=context)
        else:
            return self._getinbom(cr, uid, pid, sid, context=context)

    def GetWhereUsed(self, cr, uid, ids, context=None):
        """
            Return a list of all fathers of a Part (all levels)
        """
        self._packed = []
        context = context or self.pool['res.users'].context_get(cr, uid)
        relDatas = []
        if len(ids) < 1:
            return None
        sid = False
        if len(ids) > 1:
            sid = ids[1]
        oid = ids[0]
        relDatas.append(oid)
        relDatas.append(self._implodebom(cr, uid, self._inbomid(cr, uid, oid, sid)))
        prtDatas = self._getpackdatas(cr, uid, relDatas)
        return (relDatas, prtDatas, self._getpackreldatas(cr, uid, relDatas, prtDatas))

    def GetExplose(self, cr, uid, ids, context=None):
        """
            Returns a list of all children in a Bom (all levels)
        """
        self._packed = []
        context = context or self.pool['res.users'].context_get(cr, uid)
        relDatas = [ids[0], self._explodebom(cr, uid, self._bomid(cr, uid, ids[0]), False)]
        prtDatas = self._getpackdatas(cr, uid, relDatas)
        return (relDatas, prtDatas, self._getpackreldatas(cr, uid, relDatas, prtDatas))

    def _explodebom(self, cr, uid, bomObjects, check=True, context=None):
        """
            Explodes a BoM entity in a structured list ( check=False : all levels, check=True : one level )
        """
        output=[]
        context = context or self.pool['res.users'].context_get(cr, uid)
        for bomObject in bomObjects:
            for bom_line in bomObject.bom_line_ids:
                if check and (bom_line.product_id.id in self._packed):
                    continue
                innerids=self._explodebom(cr, uid, self._bomid(cr, uid, bom_line.product_id.id, context=context), check)
                self._packed.append(bom_line.product_id.id)
                output.append([bom_line.product_id.id, innerids])
        return(output)

    def explodebom(self, cr, uid, bomObjects, check=True, context=None):
        """
            Explodes a BoM entity in a flat list ( check=False : all levels, check=True : one level )
        """
        output=[]
        context = context or self.pool['res.users'].context_get(cr, uid)
        for bomObject in bomObjects:
            for bom_line in bomObject.bom_line_ids:
                if bom_line.product_id.id in self._packed:
                    continue
                if check:
                    continue
                innerids=self.explodebom(cr, uid, self._bomid(cr, uid, bom_line.product_id.id, context=context), check)
                self._packed.append(bom_line.product_id.id)
                output.append(bom_line.product_id.id)
                output.extend(innerids)
        return(output)

    def GetExploseSum(self, cr, uid, ids, context=None):
        """
            Return a list of all children in a Bom taken once (all levels)
        """
        self._packed = []
        context = context or self.pool['res.users'].context_get(cr, uid)
        relDatas = [ids[0], self._explodebom(cr, uid, self._bomid(cr, uid, ids[0]), True)]
        prtDatas = self._getpackdatas(cr, uid, relDatas)
        return (relDatas, prtDatas, self._getpackreldatas(cr, uid, relDatas, prtDatas))

    def _implodebom(self, cr, uid, bomObjects, context=None):
        """
            Executed implosion for a a BoM object, returning a structured list.
        """
        parentIDs=[]
        for bomObject in bomObjects:
            if not bomObject.product_id:
                continue
            if bomObject.product_id.id in self._packed:
                continue
            self._packed.append(bomObject.product_id.id)
            context = context or self.pool['res.users'].context_get(cr, uid)
            innerids=self._implodebom(cr, uid, self._inbomid(cr, uid, bomObject.product_id.id, context=context))
            parentIDs.append((bomObject.product_id.id,innerids))
        return (parentIDs)

    def implodebom(self, cr, uid, bomObjects, context=None):
        """
            Executes implosion for a a BoM object, returning a flat list.
        """
        parentIDs=[]
        for bomObject in bomObjects:
            if not bomObject.product_id:
                continue
            innerids=self.implodebom(cr, uid, self._inbomid(cr, uid, bomObject.product_id.id, context=context))
            parentIDs.append(bomObject.product_id.id)
            parentIDs.extend(innerids)
        return (getListIDs(parentIDs))

    def GetWhereUsedSum(self, cr, uid, ids, context=None):
        """
            Return a list of all fathers of a Part (all levels)
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
        self._packed = []
        relDatas = []
        if len(ids) < 1:
            return None
        sid = False
        if len(ids) > 1:
            sid = ids[1]
        oid = ids[0]
        relDatas.append(oid)
        relDatas.append(self._implodebom(cr, uid, self._inbomid(cr, uid, oid, sid)))
        prtDatas = self._getpackdatas(cr, uid, relDatas)
        return (relDatas, prtDatas, self._getpackreldatas(cr, uid, relDatas, prtDatas))

    def SaveStructure(self, cr, uid, relations=[], level=0, currlevel=0, context=None):
        """
            Save EBom relations
        """
        ret=False
        listedParent=[]
        context = context or self.pool['res.users'].context_get(cr, uid)
        bomLType=self.pool['mrp.bom.line']
        context.update({'internal_process':True, 'internal_writing':True})
        modelFields=self.pool['plm.config.settings'].GetFieldsModel(cr, uid,self._name)

        def cleanStructure(parentID=None, sourceID=None):
            """
                Cleans relations having sourceID (in mrp.bom.line)
            """
            bomIDs=[]
            if not parentID==None:
                for bom_id in self.search(cr, uid, [('type','=','ebom'),('product_id','=',parentID)], context=context):
                    if not sourceID==None:
                        for bomLine in bomLType.search(cr, uid, [('source_id','=',sourceID),('bom_id','=',bom_id)], context=context):
                            bomIDs.append(bomLine)
                        bomLType.unlink(cr, uid, getListIDs(bomIDs), context=context)                              # Cleans mrp.bom.line
                    for objBom in self.browse(cr, uid, getListIDs(bom_id), context=context):
                        if not objBom.bom_line_ids:
                            self.unlink(cr, uid, [objBom.id], context=context)                                     # Cleans mrp.bom

        def toCleanRelations(relations):
            """
                Processes relations  
            """
            listedSource = []
            for _, parentID, _, _, sourceID, _ in relations:
                if not(sourceID in listedSource):
                    cleanStructure(parentID,sourceID)
                    listedSource.append(sourceID)
            return False

        def toSaveRelations(relations):
            ret=[]
            for parentName, parentID, childName, childID, sourceID, relArgs in relations:
                ret.append(toCompute(parentName, relations))
            return sum(ret)>0
        
        def toCompute(parentName, relations, yetSaved=[]):
            """
                Processes relations  
            """
            bomID=False
            subRelations=[(a, b, c, d, e, f) for a, b, c, d, e, f in relations if a == parentName]
            if len(subRelations)>0: # no relation to save 
                parentName, parentID, _, _, sourceID, _=subRelations[0]
                if not parentID in listedParent:
                    listedParent.append(parentID)
                    thislist=list(set(yetSaved))            # Save listed parents to check under different branches
                    thislist.append(parentID)
                    bomID=getParent(parentName, parentID, kindBom='ebom')

                    if bomID:                               # Save children only if parent make sense as BoM.
                        for parentName, parentID, childName, childID, sourceID, relArgs in subRelations:
                            if childID in thislist:         # Avoids to create circular loops.
                                logging.error("toCompute : In '{}' child '{}' is generating a circular loop.".format(parentName,childName))
                            else:
                                saveChild(childName, childID, sourceID, bomID, kindBom='ebom', args=relArgs)
                            toCompute(childName, relations, thislist) # Try to evaluate & save ANY children BoM on following levels.
                        self.RebaseProductWeight(cr, uid, bomID, self.RebaseBomWeight(cr, uid, bomID, context=context), context=context)
            return bomID

        def getParent(name, partID=None, kindBom='ebom'):
            """
                Gets the father of relation ( parent side in mrp.bom )
            """
            ret=False
            if partID:
                try:
                    objTempl=self.pool['product.product'].getTemplateItem(cr, uid, partID, context=context)
                    res={
                         'type': kindBom,
                         'product_id': partID,
                         'name': name,
                         'product_tmpl_id': objTempl.id,
                         }
                                             
                    criteria=[('product_tmpl_id','=',res['product_tmpl_id']),
                              ('type','=',res['type'])]
                    ids=self.search(cr, uid, criteria, context=context)
                    if ids:
                        ret=ids[0]                                          # Gets Existing one
                    else:
                        ret=self.create(cr, uid, res, context=context)      # Creates a new one
                except Exception as msg:
                    logging.error("[getParent] :  Unable to create a BoM for part '{name}'.".format(name=name))
                    logging.error("Exception raised was : {msg}.".format(msg=msg))
            return ret

        def saveChild(name, partID=None, sourceID=None, bomID=None, kindBom='ebom', args=None):
            """
                Saves the relation ( child side in mrp.bom.line )
            """
            ret=False
            if bomID and partID:
                try:
                    res={
                         'type': kindBom,
                         'product_id': partID,
                         'bom_id': bomID,
                         }
                    if sourceID:
                        res.update({'source_id': sourceID})
 
                    if args!=None and isinstance(args, dict):
                        for arg in args.keys():
                            if arg in modelFields:
                                res.update({arg : args[arg]})
                    if ('product_qty' in res):
                        if isinstance(res['product_qty'], float) and (res['product_qty']<1e-6):
                            res.update({'product_qty': 1.0})
                    ret=bomLType.create(cr, uid, res, context=context)
                except Exception as msg:
                    logging.error("[saveChild] :  Unable to create a relation for part '{name}' with source ({src})."\
                                  .format(name=name, src=sourceID))
                    logging.error("Exception raised was : {msg}.".format(msg=msg))
            return ret
        
        if relations: # no relation to save 
            toCleanRelations(relations)
            if not toSaveRelations(relations):
                ret=True
        return ret

    def IsChild(self, cr, uid, ids, typebom=None, context=None):
        """
            Checks if a Product is child in a BoM relation.
        """
        ret=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        for idd in getListIDs(ids):
            criteria=[('product_id', '=', idd)]
            if typebom:
                criteria.append(('type', '=', typebom))
            if self.pool['mrp.bom.line'].search(cr, uid, criteria, context=context):
                ret=ret|True
        return ret

    def _sumBomWeight(self, bomObj):
        """
            Evaluates net weight for assembly, based on BoM object
        """
        weight = 0.0
        for bom_line in bomObj.bom_line_ids:
            weight += (bom_line.product_qty * bom_line.product_id.product_tmpl_id.weight)
        return weight

    def RebaseProductWeight(self, cr, uid, parentBomID, weight=0.0, context=None):
        """
            Evaluates net weight for assembly, based on product ID
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
        for bomObj in self.browse(cr, uid, getListIDs(parentBomID), context=None):
            if bomObj.product_id.engineering_writable:
                self.pool['product.product'].write(cr, uid, [bomObj.product_id.id], {'weight_net': weight}, context=context)

    def RebaseBomWeight(self, cr, uid, bomID, context=None):
        """
            Evaluates net weight for assembly, based on BoM ID
        """
        context = context or self.pool['res.users'].context_get(cr, uid)
        weight = 0.0
        for bomId in self.browse(cr, uid, getListIDs(bomID), context=context):
            if bomId.bom_line_ids:
                weight = self._sumBomWeight(bomId)
                super(plm_relation, self).write(cr, uid, [bomId.id], {'weight': weight}, context=context)
        return weight

    def checkwrite(self, cr, uid, bomIDs, context=None):
        """
            Avoids to save an edited Engineering Bom
        """
        ret=False
        productType=self.pool['product.product']
        context = context or self.pool['res.users'].context_get(cr, uid)
        options=self.pool['plm.config.settings'].GetOptions(cr,uid)

        for bomObject in self.browse(cr, uid, getListIDs(bomIDs), context=context):
            prodItem=productType.getFromTemplateID(cr, uid, bomObject.product_tmpl_id.id, context=context)
            if prodItem:
                if not options.get('opt_editbom', False):
                    if not isDraft(productType,cr, uid, prodItem.id, context=context):
                        ret=True
                        break
                if not options.get('opt_editreleasedbom', False):
                    if isAnyReleased(productType,cr, uid, prodItem.id, context=context):
                        ret=True
                        break
        return ret
    
    def checkcreation(self, cr, uid, vals, fatherIDs=[], context=None):
        ret={}
        thisID=vals.get('product_id',False)
        if thisID:
            self._packed=[]
            exploded=self.explodebom(cr, uid, self._bomid(cr, uid, thisID, context=context), False, context=context)
            imploded=self.implodebom(cr, uid, self._inbomid(cr, uid, thisID, context=context))
            checklist1=list(set(exploded).intersection(fatherIDs))
            if not(thisID in fatherIDs) and not checklist1 and not(thisID in imploded):
                newIDs=getCleanList(fatherIDs)
                newIDs.append(thisID)
                bomLines=vals.get('bom_line_ids',[])
                if bomLines:
                    theseLines=[]                
                    for status, value, bom_line in bomLines:
                        thisLine=self.checkcreation(cr, uid, bom_line, newIDs, context=context)
                        if thisLine:
                            theseLines.append([status, value, thisLine])
                    vals['bom_line_ids']=theseLines
                ret=vals
            else:
                logging.warning("[mrp.bom::checkcreation] : Discharged relation creating circular reference.")
        return ret

    def validatecreation(self, cr, uid, fatherID, vals, context=None):
        fatherIDs=[fatherID]
        bomLines=vals.get('bom_line_ids',[])
        if bomLines:
            theseLines=[]                
            for operation, productID, bom_line in bomLines:
                thisLine=self.checkcreation(cr, uid, bom_line, fatherIDs, context=context)
                if thisLine:
                    theseLines.append([operation, productID, thisLine])
            vals['bom_line_ids']=theseLines
        ret=vals
        return ret

    def validatechanges(self, cr, uid, bomID, vals, context=None):
        ret={}
        for father in self.browse(cr, uid, getListIDs(bomID), context=context):
            fatherIDs=[father.product_id.id]
            bomLines=vals.get('bom_line_ids',[])
            if bomLines:
                theseLines=[]                
                for operation, productID, bom_line in bomLines:
                    if operation==0:
                        thisLine=self.checkcreation(cr, uid, bom_line, fatherIDs, context=context)
                        if thisLine:
                            theseLines.append([operation, productID, thisLine])
                    else:
                        theseLines.append([operation, productID, bom_line])
                vals['bom_line_ids']=theseLines
            ret=vals
        return ret

    def logcreate(self, cr, uid, productID, vals, context=None):
        for product in self.pool['product.product'].browse(cr, uid, getListIDs(productID), context=context):
            values={
                    'name': product.name,
                    'revision': product.engineering_revision,
                    'type': self._name,
                    'op_type': 'creation',
                    'op_note': 'Create new BoM relation on database',
                    'op_date': datetime.now(),
                    'userid': uid,
                    }
            self.pool['plm.logging'].create(cr, uid, values, context=context)
  
#   Overridden methods for this entity
#     def create(self, cr, uid, vals, context=None):
#         ret=False
#         if vals:
#             context = context or self.pool['res.users'].context_get(cr, uid)
#             productID=vals.get('product_id',False)
#             if not productID:
#                 templID=vals.get('product_tmpl_id',False)
#                 prodItem=self.pool['product.product'].getFromTemplateID(cr, uid, templID, context=None)
#                 if prodItem:
#                     productID=prodItem.id
#             result=self.validatecreation(cr, uid, productID, vals, context=None)
#             if result:
#                 try:
#                     self.logcreate(cr, uid, productID, vals, context=context)
#                     ret=super(plm_relation,self).create(cr, uid, result, context=context)
#                 except Exception as ex:
#                     raise Exception(" (%r). It has tried to create with values : (%r)."%(ex, result))
#         return ret

    def write(self, cr, uid, ids, vals, context=None):
        """
            Avoids to save an edited Engineering Bom
        """
        ret=False
        if vals:
            context = context or self.pool['res.users'].context_get(cr, uid)
            check=context.get('internal_writing', False)
            bomIDs=getListIDs(ids)
            if not check and self.checkwrite(cr, uid, bomIDs, context=context):
                raise orm.except_orm(_('Writing check'), 
                                     _("Current Bill of Material of product isn't modifiable."))

            self._insertlog(cr, uid, bomIDs, changes=vals, context=context)
            result=self.validatechanges(cr, uid, bomIDs, vals, context=None)
            ret=super(plm_relation,self).write(cr, uid, bomIDs, result, context=context)
            self.RebaseBomWeight(cr, uid, bomIDs, context=context)
        return ret

    def copy(self, cr, uid, oid, default={}, context=None):
        """
            Return new object copied (removing SourceID)
        """
        compType = self.pool['product.product']
        bomLType=self.pool['mrp.bom.line']
        context = context or self.pool['res.users'].context_get(cr, uid)
        context.update({'internal_writing':True})
        update_flag=context.get('update_latest_revision', False)
        note={
                'type': 'copy object',
                'reason': "Copied a new BoM for the product.",
             }
        self._insertlog(cr, uid, oid, note=note, context=context)
        newId = super(plm_relation, self).copy(cr, uid, oid, default, context=context)
        if newId:
            newOid = self.browse(cr, uid, newId, context=context)
            self.write(cr, uid, [newId], 
                        {
                            'name': newOid.product_tmpl_id.name
                        }, context=context)
            if update_flag:
                for bom_line in newOid.bom_line_ids:
                    lateRevIdC = compType.GetLatestIds(cr, uid, [(bom_line.product_id.engineering_code, False, False)],
                                                       context=context)  # Get Latest revision of each Part
                    bomLType.write(cr, uid, [bom_line.id], 
                            {
                                'product_id': lateRevIdC[0],
                                'name': bom_line.product_id.name
                            }, context=context)
        return newId

    def unlink(self, cr, uid, ids, context=None):
        ret=False
        processIds=[]
        context = context or self.pool['res.users'].context_get(cr, uid)
        check=context.get('internal_writing', False)
        if not check:
            isAdmin = isAdministrator(self, cr, uid, context=context)
    
            for bomID in self.browse(cr, uid, getListIDs(ids), context=context):
                if not self.IsChild(cr, uid, bomID.product_id.id, typebom=bomID.type, context=context):
                    checkApply=False
                    if isReleased(self.pool['product.product'], cr, uid, bomID.product_id.id, context=context):
                        if isAdmin:
                            checkApply=True
                    elif isDraft(self.pool['product.product'], cr, uid, bomID.product_id.id, context=context):
                        checkApply=True

                    if not checkApply:
                        continue            # Apply unlink only if have respected rules.
                    processIds.append(bomID)
        else:
            processIds=self.browse(cr, uid, getListIDs(ids), context=context)
        note={
                'type': 'unlink object',
                'reason': "Removed entity from database.",
             }
        for processId in processIds:
            self._insertlog(cr, uid, processId.id, note=note, context=context)
            item=super(plm_relation, self).unlink(cr, uid, [processId.id], context=context)
            if item:
                ret=ret | item
        return ret

    def _check_product(self, cr, uid, ids, context=None):
        """
            Override original one, to allow to have multiple lines with same Part Number
        """
        return True

    _constraints = [
        (_check_product, 'BoM line product should not be same as BoM product.', ['product_id']),
    ]

plm_relation()


class plm_material(orm.Model):
    _name = "plm.material"
    _description = "Materials"
    _columns = {
        'name': fields.char('Designation', size=128, required=True),
        'description': fields.char('Description', size=128),
        'sequence': fields.integer('Sequence',
                                   help="Gives the sequence order when displaying a list of product categories."),
    }
    #    _defaults = {
    #        'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'plm.material'),
    #    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', _('Raw Material has to be unique !')),
    ]


class plm_finishing(orm.Model):
    _name = "plm.finishing"
    _description = "Surface Finishing"
    _columns = {
        'name': fields.char('Specification', size=128, required=True),
        'description': fields.char('Description', size=128),
        'sequence': fields.integer('Sequence',
                                   help="Gives the sequence order when displaying a list of product categories."),
    }
    #    _defaults = {
    #        'name': lambda obj, cr, uid, context: obj.pool.get('ir.sequence').get(cr, uid, 'plm.finishing'),
    #    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', _('Raw Material has to be unique !')),
    ]


class plm_codelist(orm.Model):
    _name = "plm.codelist"
    _description = "Code List"
    _columns = {
        'name': fields.char('Part Number', size=128, required=True),
        'description': fields.char('Description', size=128),
        'sequence_id': fields.many2one('ir.sequence', 'name', ondelete='no action', 
                                     help='This is the sequence object related to this P/N rule.'),
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', _('Part Number Rule has to be unique !')),
    ]

class plm_doculist(orm.Model):
    _name = "plm.doculist"
    _description = "Document Code List"
    _columns = {
        'name': fields.char('Document Number', size=128, required=True),
        'description': fields.char('Description', size=128),
        'sequence_id': fields.many2one('ir.sequence', 'name', ondelete='no action', 
                                     help='This is the sequence object related to this P/N rule.'),
    }
    _sql_constraints = [
        ('name_uniq', 'unique(name)', _('Document Number Rule has to be unique !')),
    ]

class plm_temporary(orm.TransientModel):
    _name = "plm.temporary"
    _description = "Temporary Class"

    _columns = {
        'name': fields.char('Temp', size=128),
        'revflag': fields.boolean('Update revisions', help='Use latest product revisions evaluating new BoM.', default=False),
    }

    _defaults = {
                 'revflag': False,
    }

    def action_create_normalBom(self, cr, uid, ids, context=None):
        """
            Create a new Spare BoM if doesn't exist (action callable from views)
        """
        ret=False
        context = context or self.pool['res.users'].context_get(cr, uid)
        if 'active_ids' in context:
            context.update({ "update_latest_revision": self.browse(cr,uid,ids[0]).revflag })
            self.pool['product.product'].action_create_normalBom_WF(cr, uid, context['active_ids'], context=context)
            ret={
                'name': _('Bill of Materials'),
                'view_type': 'form',
                "view_mode": 'tree,form',
                'res_model': 'mrp.bom',
                'type': 'ir.actions.act_window',
                'domain': "[('product_id','in', [" + ','.join(map(str, context['active_ids'])) + "])]",
                }
        return ret
    
    def action_NewRevision(self, cr, uid, ids, context=None):
        """
            Call for NewRevision method
        """
        ret=False
        revised=[]
        context = context or self.pool['res.users'].context_get(cr, uid)
        active_ids=context.get('active_ids', [])
        active_model=context.get('active_model', None)
        if active_ids and active_model:
            objectType=self.pool[active_model]
            for thisId in active_ids:
                if isAnyReleased(objectType, cr, uid, thisId, context=context):
                    newID, newIndex=objectType.NewRevision(cr, uid, getListIDs(thisId), context=context)
                    #TODO: To be implemented management by server options.
#                     objectType.processedIds=[]
#                     objectType._copyProductBom(cr, uid, thisId, newID, context=context)
                    revised.append(newID)
            if revised:
                ret={
                    'name': _('New Revisions'),
                    'view_type': 'form',
                    "view_mode": 'tree,form',
                    'res_model': active_model,
                    'type': 'ir.actions.act_window',
                    'domain': "[('id','in', [" + ','.join(map(str, revised)) + "])]",
                    }
                        
        return ret

    def action_NewDocRevision(self, cr, uid, ids, context=None):
        """
            Call for NewRevision method
        """
        ret=False
        revised=[]
        context = context or self.pool['res.users'].context_get(cr, uid)
        active_ids=context.get('active_ids', [])
        active_model=context.get('active_model', None)
        if active_ids and active_model:
            objectType=self.pool[active_model]
            for thisId in active_ids:
                if isAnyReleased(objectType, cr, uid, thisId, context=context):
                    newID, newIndex=objectType.NewRevision(cr, uid, (getListIDs(thisId),"",""), context=context)
                    #TODO: To be implemented management by server options.
#                     objectType.processedIds=[]
#                     objectType._copyProductBom(cr, uid, thisId, newID, context=context)
                    revised.append(newID)
            if revised:
                ret={
                    'name': _('New Revisions'),
                    'view_type': 'form',
                    "view_mode": 'tree,form',
                    'res_model': active_model,
                    'type': 'ir.actions.act_window',
                    'domain': "[('id','in', [" + ','.join(map(str, revised)) + "])]",
                    }
                        
        return ret
    