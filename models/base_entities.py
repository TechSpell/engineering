# -*- encoding: utf-8 -*-
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

import logging
from datetime import datetime

from openerp import models, fields, api, _, osv
import openerp.addons.decimal_precision as dp

from .common import BOMTYPES, getListIDs, getCleanList, \
                    isAdministrator, isDraft, isAnyReleased, isObsoleted
                    

# To be adequate to plm.document class states
USED_STATES = [('draft', 'Draft'), ('confirmed', 'Confirmed'), ('released', 'Released'), ('undermodify', 'UnderModify'),
               ('obsoleted', 'Obsoleted')]


class plm_component(models.Model):
    _inherit = 'product.template'

    state                   =   fields.Selection    (USED_STATES, string=_('Status'),           readonly="True",         default='draft',       help=_("The status of the product in its LifeCycle."))
    engineering_code        =   fields.Char         (             string=_('Part Number'),      size=64,                                        help=_("This is engineering reference to manage a different P/N from item Name."))
    engineering_revision    =   fields.Integer      (             string=_('Revision'),                   required=True, default=0,             help=_("The revision of the product."))
    engineering_writable    =   fields.Boolean      (             string=_('Writable'),                                  default=True)
    engineering_material    =   fields.Char         (             string=_('Raw Material'),     size=128, required=False,                       help=_("Raw material for current product, only description for titleblock."))
#   engineering_treatment   =   fields.Char         (             string=_('Treatment'),        size=64,  required=False,                       help=_("Thermal treatment for current product"))
    engineering_surface     =   fields.Char         (             string=_('Surface Finishing'),size=128, required=False,                       help=_("Surface finishing for current product, only description for titleblock."))

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


class plm_component_document_rel(models.Model):
    _name = 'plm.component.document.rel'
    _description = "Component Document Relations"
    
    component_id    =   fields.Many2one('product.product', string=_('Linked Component'), ondelete='cascade')
    document_id     =   fields.Many2one('plm.document',    string=_('Linked Document'),  ondelete='cascade')

    _sql_constraints = [
        (
            'relation_unique', 'unique(component_id,document_id)',
            _('Component and Document relation has to be unique !')),
    ]
    
    def CleanStructure(self, relations):
        res = []
        criteria=False
        rl_to_delete=self
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
                rl_to_delete |= self.search(criteria)
        rl_to_delete.unlink()

    @api.model
    def SaveStructure(self, relations=[], level=0, currlevel=0):
        """
            Save Document relations
        """
        ret=False

        def cleanStructure(relations):
            self.CleanStructure(relations)

        def saveChild(args):
            """
                save the relation 
            """
            ret=False
            try:
                res = {}
                res['document_id'], res['component_id'] = args
                self.create(res)
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

         
class plm_relation_line(models.Model):
    _inherit = 'mrp.bom.line'
    
    create_date = fields.Datetime   (             string=_('Creation Date'),     readonly=True)
    source_id   = fields.Many2one   ('plm.document','name',ondelete='no action', readonly=True, help=_("This is the document object that declares this BoM."))
    type        = fields.Selection  (BOMTYPES, string=_('BoM Type'),             required=True, help=_(HELP))
    itemnum     = fields.Integer    (          string=_('CAD Item Position'),                   help=_("This is the item reference position into the CAD document that declares this BoM."))
    itemlbl     = fields.Char       (          string=_('Cad Item Position Label'), size=64,    help=_("This is the item reference position into the CAD document that declares this BoM (As literal)."))

    _defaults = {
        'product_uom' : 1,
    }
    
    _order = 'itemnum'

    @api.onchange('product_id')
    def onchange_plmproduct_id(self):
        """ Changes UoM if product_id changes.
        @param product_id: Changed product_id
        @return:  Dictionary of changed values
        """
        father_id=False
        product_id=False
        if self._context and 'product_id' in self._context and 'father_id' in self._context and 'father_tmpl_id' in self._context:
            options=self.env['plm.config.settings'].GetOptions()
            prodTypeObj=self.env['product.product']
            father_id=self._context['father_id']
            if not father_id:
                fatherObj=prodTypeObj.getFromTemplateID(self._context['father_tmpl_id'])
                father_id=fatherObj.id if fatherObj else False 
            product_id=self._context['product_id']
            if father_id and product_id:
                prodTypeObj.alreadyListed=[]
                productObj=prodTypeObj.browse(product_id)
                fatherIDs=prodTypeObj.recurse_father_part_compute([father_id, product_id])
                if (father_id == product_id) or (product_id in fatherIDs[father_id]):
                    logging.warning("Writing BoM check: This is a circular reference to: %s - %d." %(productObj.product_tmpl_id.name, productObj.product_tmpl_id.engineering_revision))
                    self.product_id=False
                if not options.get('opt_duplicatedrowsinbom', True):
                    listed_products=[]
                    if 'parent' in self._context:
                        if 'bom_line_ids' in self._context['parent']:
                            mrp_bom_lines=self._context['parent']['bom_line_ids']
                            for mrp_bom_line in mrp_bom_lines:
                                prod_id=False
                                req, bom_line, vals=mrp_bom_line
                                if req and req!=2:
                                    if bom_line:
                                        prod_id=self.browse(bom_line).product_id.id
                                else:
                                    if vals and 'product_id' in vals:
                                        prod_id=vals['product_id']
                                if prod_id:
                                    listed_products.append(prod_id)
                        if (product_id in listed_products):
                            logging.warning("Writing BoM check: This is a duplicated line : %s - %d." %(productObj.product_tmpl_id.name, productObj.product_tmpl_id.engineering_revision))
                            self.product_id=False
                if options.get('opt_autonumbersinbom', False):
                    if 'parent' in self._context:
                        length=0
                        step=options.get('opt_autostepinbom', 5)
                        if 'bom_line_ids' in self._context['parent']:
                            mrp_bom_lines=self._context['parent']['bom_line_ids']
                            length=len(mrp_bom_lines)
                        self.itemnum=step*(length+1)
                if options.get('opt_autotypeinbom', False):
                    if ('parent' in self._context) and ('type' in self._context['parent']):
                        self.type=self._context['parent']['type']

class plm_relation(models.Model):
    _inherit = 'mrp.bom'

    _packed = []
    
    create_date = fields.Datetime   (          string=_('Creation Date'),    readonly=True)
    type        = fields.Selection  (BOMTYPES, string=_('BoM Type'),         required=True,                           help=_(HELP))
    weight      = fields.Float      (          string=_('Weight') ,          digits_compute=dp.get_precision('Stock Weight'), help=_("The BoM net weight in Kg."))

    _defaults = {
        'product_uom' : 1,
        'weight' : 0.0,
    }

    def init(self, cr):
        self._packed = []

    def _insertlog(self, ids, changes={}, note={}):
        newID=False
        
        op_type, op_note=["unknown",""]
        for bomObject in self.browse( getListIDs(ids)):
            if note:
                op_type="{type}".format(type=note['type'])
                op_note="{reason}".format(reason=note['reason'])
            elif changes:
                op_type='change value'
                op_note=self.env['plm.logging'].getchanges( bomObject, changes)
            if op_note:
                values={
                        'name': bomObject.product_id.name,
                        'revision': "{major}".format(major=bomObject.product_id.engineering_revision),
                        'type': self._name,
                        'op_type': op_type,
                        'op_note': op_note,
                        'op_date': datetime.now(),
                        'userid': self._uid,
                        }
                
                objectItem=self.env['plm.logging'].create(values)
                if objectItem:
                    newID=objectItem
        return newID

    def _getinbomidnullsrc(self, pid):
        counted = []
        bomLType=self.env['mrp.bom.line']
        for obj in bomLType.search( [('product_id', '=', pid), ('bom_id', '!=', False),
                                     ('type', 'in', ['ebom', 'normal', 'spbom'])]):
            if not obj.bom_id in counted:
                counted.append(obj.bom_id)
        return counted

    def _getinbom(self, pid, sid):
        counted = []
        bomLType=self.env['mrp.bom.line']
        for obj in bomLType.search( [('product_id', '=', pid), ('bom_id', '!=', False), ('source_id', '=', sid),
                                    ('type', 'in', ['ebom', 'normal', 'spbom'])]):
            if not obj.bom_id in counted:
                counted.append(obj.bom_id)
        return counted

    def _getbomidnullsrc(self, pid):
        
        templId=self.env['product.product'].getTemplateItem( pid)
        return self.search( [('product_tmpl_id', '=', templId.id), ('type', 'in', ['ebom', 'normal', 'spbom'])])
    
    def _getbomid(self, pid, sid):
        
        return self._getidbom( pid, sid)

    def _getidbom(self, pid, sid):
        
        templId=self.env['product.product'].getTemplateItem( pid)
        return self.search( [('product_tmpl_id', '=', templId.id), ('type', 'in', ['ebom', 'normal', 'spbom'])])

    def _getpackdatas(self, relDatas):
        prtDatas = {}
        tmpids = getListedDatas(relDatas)
        if len(tmpids) < 1:
            return prtDatas
        compType = self.env['product.product']
        tmpDatas = compType.read( tmpids)
        for tmpData in tmpDatas:
            for keyData in tmpData.keys():
                if tmpData[keyData]==None:
                    del tmpData[keyData]
            prtDatas[str(tmpData['id'])] = tmpData
        return prtDatas

    def _getpackreldatas(self, relDatas, prtDatas):
        relids = {}
        relationDatas = {}
        tmpids = getListedDatas(relDatas)
        if len(tmpids) < 1:
            return prtDatas
        for keyData in prtDatas.keys():
            tmpData = prtDatas[keyData]
            if len(tmpData['bom_ids']) > 0:
                relids[keyData] = tmpData['bom_ids'][0]

        if len(relids) < 1:
            return relationDatas
        setobj = self.env['mrp.bom']
        for keyData in relids.keys():
            relationDatas[keyData] = setobj.read( relids[keyData])
        return relationDatas

    def _bomid(self, pid, sid=None):
        
        if not sid:
            return self._getbomidnullsrc( pid)
        else:
            return self._getbomid( pid, sid)

    def _inbomid(self, pid, sid=None):
        
        if not sid:
            return self._getinbomidnullsrc( pid)
        else:
            return self._getinbom( pid, sid)

    @api.model
    def GetWhereUsed(self, ids):
        """
            Return a list of all fathers of a Part (all levels)
        """
        self._packed = []
        
        relDatas = []
        if len(ids) < 1:
            return None
        sid = False
        if len(ids) > 1:
            sid = ids[1]
        oid = ids[0]
        relDatas.append(oid)
        relDatas.append(self._implodebom( self._inbomid( oid, sid)))
        prtDatas = self._getpackdatas( relDatas)
        return (relDatas, prtDatas, self._getpackreldatas( relDatas, prtDatas))

    @api.model
    def GetExplose(self, ids):
        """
            Returns a list of all children in a Bom (all levels)
        """
        self._packed = []
        
        relDatas = [ids[0], self._explodebom( self._bomid( ids[0]), False)]
        prtDatas = self._getpackdatas( relDatas)
        return (relDatas, prtDatas, self._getpackreldatas( relDatas, prtDatas))

    def _explodebom(self, bomObjects, check=True):
        """
            Explodes a BoM entity in a structured list ( check=False : all levels, check=True : one level )
        """
        output=[]
        
        for bomObject in bomObjects:
            for bom_line in bomObject.bom_line_ids:
                if check and (bom_line.product_id.id in self._packed):
                    continue
                innerids=self._explodebom( self._bomid( bom_line.product_id.id), check)
                self._packed.append(bom_line.product_id.id)
                output.append([bom_line.product_id.id, innerids])
        return(output)

    def explodebom(self, bomObjects, check=True):
        """
            Explodes a BoM entity in a flat list ( check=False : all levels, check=True : one level )
        """
        output=[]
        
        for bomObject in bomObjects:
            for bom_line in bomObject.bom_line_ids:
                if bom_line.product_id.id in self._packed:
                    continue
                if check:
                    continue
                innerids=self.explodebom( self._bomid( bom_line.product_id.id), check)
                self._packed.append(bom_line.product_id.id)
                output.append(bom_line.product_id.id)
                output.extend(innerids)
        return(output)

    @api.model
    def GetExploseSum(self, ids):
        """
            Return a list of all children in a Bom taken once (all levels)
        """
        self._packed = []
        
        relDatas = [ids[0], self._explodebom( self._bomid( ids[0]), True)]
        prtDatas = self._getpackdatas( relDatas)
        return (relDatas, prtDatas, self._getpackreldatas( relDatas, prtDatas))

    def _implodebom(self, bomObjects):
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
            
            innerids=self._implodebom( self._inbomid( bomObject.product_id.id))
            parentIDs.append((bomObject.product_id.id,innerids))
        return (parentIDs)

    def implodebom(self, bomObjects):
        """
            Executes implosion for a a BoM object, returning a flat list.
        """
        parentIDs=[]
        for bomObject in bomObjects:
            if not bomObject.product_id:
                continue
            
            innerids=self.implodebom( self._inbomid( bomObject.product_id.id))
            parentIDs.append(bomObject.product_id.id)
            parentIDs.extend(innerids)
        return (parentIDs)

    @api.model
    def GetWhereUsedSum(self, ids):
        """
            Return a list of all fathers of a Part (all levels)
        """
        
        self._packed = []
        relDatas = []
        if len(ids) < 1:
            return None
        sid = False
        if len(ids) > 1:
            sid = ids[1]
        oid = ids[0]
        relDatas.append(oid)
        relDatas.append(self._implodebom( self._inbomid( oid, sid)))
        prtDatas = self._getpackdatas( relDatas)
        return (relDatas, prtDatas, self._getpackreldatas( relDatas, prtDatas))

    @api.model
    def SaveStructure(self, relations=[], level=0, currlevel=0):
        """
            Save EBom relations
        """
        ret=False
        listedParent=[]
        bomLType=self.env['mrp.bom.line']
        modelFields=self.env['plm.config.settings'].GetFieldsModel(bomLType._name)

        def cleanStructure(sourceID=None):
            """
                Cleans relations having sourceID (in mrp.bom.line)
            """
            bomIDs=[]
            bl_to_delete = bomLType
            if not sourceID==None:
                for bomLine in bomLType.search([('source_id','=',sourceID)]):
                    bomIDs.append(bomLine.bom_id)
                    bl_to_delete |= bomLine
                bl_to_delete.unlink()                           # Cleans mrp.bom.lines
            for bomID in getCleanList(bomIDs):
                if not bomID.bom_line_ids:
                    bomID.unlink()                              # Cleans mrp.bom
                    

        def toCleanRelations(relations):
            """
                Processes relations  
            """
            listedSource = []
            for _, _, _, _, sourceID, _ in relations:
                if not(sourceID in listedSource):
                    cleanStructure(sourceID)
                    listedSource.append(sourceID)
            return False

        def toCompute(parentName, relations):
            """
                Processes relations  
            """
            bomID=False
            subRelations=[(a, b, c, d, e, f) for a, b, c, d, e, f in relations if a == parentName]
            if len(subRelations)>0: # no relation to save 
                parentName, parentID, tmpChildName, tmpChildID, sourceID, tempRelArgs=subRelations[0]
                if not parentID in listedParent:
                    listedParent.append(parentID)
                    bomID=getParent(parentName, parentID, kindBom='ebom')
                    if bomID:
                        for rel in subRelations:
                            parentName, parentID, childName, childID, sourceID, relArgs=rel
                            if parentName == childName:
                                logging.error('toCompute : Father (%s) refers to himself' %(str(parentName)))
                            else:
                                if saveChild(childName, childID, sourceID, bomID, kindBom='ebom', args=relArgs):
                                    tmpBomId=toCompute(childName, relations)
                        self.RebaseProductWeight( bomID, self.RebaseBomWeight( bomID))
            return bomID

        def getParent(name, partID=None, kindBom='ebom'):
            """
                Gets the father of relation ( parent side in mrp.bom )
            """
            ret=False
            if partID:
                try:
                    objTempl=self.env['product.product'].getTemplateItem(partID)
                    res={
                         'type': kindBom,
                         'product_id': partID,
                         'product_tmpl_id': objTempl.id,
                         }
                                             
                    criteria=[('product_tmpl_id','=',res['product_tmpl_id']),
                              ('type','=',res['type'])]
                    ids=self.search(criteria)
                    if ids:
                        ret=ids[0].id                   # Gets Existing one
                    else:
                        objectItem=self.create(res)     # Creates a new one
                        if objectItem:
                            ret=objectItem.id
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
                    objectItem=bomLType.with_context({'internal_process':True}).create(res)
                    if objectItem:
                        ret=objectItem
                except Exception as msg:
                    logging.error("[saveChild] :  Unable to create a relation for part '{name}' with source ({src})."\
                                  .format(name=name, src=sourceID))
                    logging.error("Exception raised was : {msg}.".format(msg=msg))
            return ret
        
        if relations: # no relation to save 
            parentName, parentID, _, _, _, _=relations[0]
            toCleanRelations(relations)
            if not toCompute(parentName, relations):
                ret=True
        return ret

    @api.model
    def IsChild(self, ids, typebom=None):
        """
            Checks if a Product is child in a BoM relation.
        """
        ret=False
        
        for idd in getListIDs(ids):
            criteria=[('product_id', '=', idd)]
            if typebom:
                criteria.append(('type', '=', typebom))
            if self.env['mrp.bom.line'].search(criteria):
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

    @api.model
    def RebaseProductWeight(self, parentBomID, weight=0.0):
        """
            Evaluates net weight for assembly, based on product ID
        """
        
        for bomObj in self.browse( getListIDs(parentBomID)):
            if bomObj.product_id.engineering_writable:
                bomObj.product_id.write( {'weight': weight} )

    @api.model
    def RebaseBomWeight(self, bomID):
        """
            Evaluates net weight for assembly, based on BoM ID
        """
        
        weight = 0.0
        for bomId in self.browse( getListIDs(bomID)):
            if bomId.bom_line_ids:
                weight = self._sumBomWeight(bomId)
                super(plm_relation, bomId).write( {'weight': weight} )
        return weight

    def checkwrite(self, bomIDs):
        """
            Avoids to save an edited Engineering Bom
        """
        ret=False
        productType=self.env['product.product']
        
        options=self.env['plm.config.settings'].GetOptions()

        for bomObject in self.browse( getListIDs(bomIDs)):
            prodItem=productType.getFromTemplateID(bomObject.product_tmpl_id.id)
            if prodItem:
                if not options.get('opt_editbom', False):
                    if not isDraft(productType, prodItem.id):
                        ret=True
                        break
                if not options.get('opt_editreleasedbom', False):
                    if isAnyReleased(productType, prodItem.id):
                        ret=True
                        break
                if isObsoleted(productType, prodItem.id):
                    ret=True
                    break
        return ret
    
    def checkcreation(self, vals, fatherIDs=[]):
        ret={}
        thisID=vals.get('product_id',False)
        if thisID:
            self._packed=[]
            exploded=self.explodebom( self._bomid( thisID), False)
            imploded=self.implodebom( self._inbomid( thisID))
            checklist1=list(set(exploded).intersection(fatherIDs))
            if not(thisID in fatherIDs) and not checklist1 and not(thisID in imploded):
                newIDs=getCleanList(fatherIDs)
                newIDs.append(thisID)
                bomLines=vals.get('bom_line_ids',[])
                if bomLines:
                    theseLines=[]                
                    for status, value, bom_line in bomLines:
                        thisLine=self.checkcreation( bom_line, newIDs)
                        if thisLine:
                            theseLines.append([status, value, thisLine])
                    vals['bom_line_ids']=theseLines
                ret=vals
            else:
                logging.warning("[mrp.bom::checkcreation] : Discharged relation creating circular reference.")
        return ret

    def validatecreation(self, fatherID, vals):
        fatherIDs=[fatherID]
        bomLines=vals.get('bom_line_ids',[])
        if bomLines:
            theseLines=[]                
            for operation, productID, bom_line in bomLines:
                thisLine=self.checkcreation( bom_line, fatherIDs)
                if thisLine:
                    theseLines.append([operation, productID, thisLine])
            vals['bom_line_ids']=theseLines
        ret=vals
        return ret

    def validatechanges(self, bomID, vals):
        ret={}
        for father in self.browse( getListIDs(bomID)):
            fatherIDs=[father.product_id.id]
            bomLines=vals.get('bom_line_ids',[])
            if bomLines:
                theseLines=[]                
                for operation, productID, bom_line in bomLines:
                    if operation==0:
                        thisLine=self.checkcreation( bom_line, fatherIDs)
                        if thisLine:
                            theseLines.append([operation, productID, thisLine])
                    else:
                        theseLines.append([operation, productID, bom_line])
                vals['bom_line_ids']=theseLines
            ret=vals
        return ret

    def logcreate(self, productID, vals):
        for product in self.env['product.product'].browse( getListIDs(productID)):
            values={
                    'name': product.name,
                    'revision': product.engineering_revision,
                    'type': self._name,
                    'op_type': 'creation',
                    'op_note': 'Create new entity on database',
                    'op_date': datetime.now(),
                    'userid': self._uid,
                    }
            self.env['plm.logging'].create( values)
  
#   Overridden methods for this entity
    @api.model
    def create(self, vals):
        ret=False
        if vals:
            productID=vals.get('product_id',False)
            if not productID:
                templID=vals.get('product_tmpl_id',False)
                prodItem=self.env['product.product'].getFromTemplateID( templID)
                if prodItem:
                    productID=prodItem.id
            result=self.validatecreation(productID, vals)
            if result:
                try:
                    self.logcreate(productID, vals)
                    ret=super(plm_relation,self).create(result)
                except Exception as ex:
                    raise Exception(" (%r). It has tried to create with values : (%r)."%(ex, result))
        return ret

    @api.multi
    def write(self, vals):
        """
            Avoids to save an edited Engineering Bom
        """
        ret=False
        ids=self._ids
        if vals:
            check=self._context.get('internal_writing', False)
            bomIDs=getListIDs(ids)
            if not check and self.checkwrite( bomIDs):
                raise osv.except_osv(_('Writing check'), 
                                     _("Current Bill of Material of product isn't modifiable."))

            self._insertlog( bomIDs, changes=vals)
            result=self.validatechanges(bomIDs, vals)
            ret=super(plm_relation, self.browse(bomIDs)).write(result)
            self.RebaseBomWeight( bomIDs)
        return ret

    @api.multi
    def copy(self, default=None):
        """
            Return new object copied (removing SourceID)
        """
        oid=self.id
        compType = self.env['product.product']
        
        note={
                'type': 'copy object',
                'reason': "Copied a new BoM for the product.",
             }
        self._insertlog( oid, note=note)
        newOid = super(plm_relation, self).copy(default)
        if newOid:
            for bom_line in newOid.bom_line_ids:
                lateRevIdC=compType.GetLatestIds( [(bom_line.product_id.engineering_code, False, False)] )  # Get Latest revision of each Part
                bom_line.write( { 'product_id': lateRevIdC[0],} )
        return newOid

    @api.multi
    def unlink(self):
        ret=False
        ids=self._ids
        processIds=[]
        check=self._context.get('internal_writing', False)
        if not check:
            isAdmin = isAdministrator(self)

            for bomID in self.browse(getListIDs(ids)):
                if not self.IsChild(bomID.product_id.id, bomID.type):
                    checkApply=False
                    if isAnyReleased(self.env['product.product'],  bomID.product_id.id):
                        if isAdmin:
                            checkApply=True
                    elif isDraft(self.env['product.product'],  bomID.product_id.id):
                        checkApply=True

                    if not checkApply:
                        continue            # Apply unlink only if have respected rules.
                    processIds.append(bomID)
        else:
            processIds=self.browse(getListIDs(ids))
        note={
                'type': 'unlink object',
                'reason': "Removed entity from database.",
             }
        for processId in processIds:
            self._insertlog(processId.id, note=note)
            ret=ret | super(plm_relation, processId).unlink()
        return ret

plm_relation()


class plm_material(models.Model):
    _name = "plm.material"
    _description = "Materials"

    name         = fields.Char     (string=_('Designation'),    size=128, required=True)
    description  = fields.Char     (string=_('Description'),    size=128)
    sequence     = fields.Integer  (string=_('Sequence'),       help=_("Gives the sequence order when displaying a list of product categories."))

    _sql_constraints = [
        ('name_uniq', 'unique(name)', _('Raw Material has to be unique !')),
    ]


class plm_finishing(models.Model):
    _name = "plm.finishing"
    _description = "Surface Finishing"

    name         = fields.Char     (string=_('Designation'),    size=128, required=True)
    description  = fields.Char     (string=_('Description'),    size=128)
    sequence     = fields.Integer  (string=_('Sequence'),       help=_("Gives the sequence order when displaying a list of product categories."))

    _sql_constraints = [
        ('name_uniq', 'unique(name)', _('Raw Material has to be unique !')),
    ]


class plm_codelist(models.Model):
    _name = "plm.codelist"
    _description = "Code List"
    
    name        = fields.Char      (                string=_('Part Number'),   size=128,   help=_("Choose the Part Number rule."))
    description = fields.Char      (                string=_('Description'),   size=128,   help=_("Description of Part Number Rule."))
    sequence_id = fields.Many2one  ('ir.sequence',  string=_('Sequence'),                  help=_("This is the sequence object related to this P/N rule."))


class plm_temporary(models.AbstractModel):
    _name = "plm.temporary"
    _description = "Temporary Class"

    name    =   fields.Char(_('Temp'), size=128)

    @api.multi
    def action_create_normalBom(self, context={}):
        """
            Create a new Spare BoM if doesn't exist (action callable from views)
        """
        ret=False
        
        if 'active_ids' in context:
            self.env['product.product'].action_create_normalBom_WF(context['active_ids'])
            ret={
                'name': _('Bill of Materials'),
                'view_type': 'form',
                "view_mode": 'tree,form',
                'res_model': 'mrp.bom',
                'type': 'ir.actions.act_window',
                'domain': "[('product_id','in', [" + ','.join(map(str, context['active_ids'])) + "])]",
                }
        return ret
    
    @api.model
    def action_NewDocRevision(self, ids):
        """
            Call for NewRevision method
        """
        ret=False
        revised=[]
        
        active_ids=self._context.get('active_ids', [])
        active_model=self._context.get('active_model', None)
        if active_ids and active_model:
            objectType=self.env[active_model]
            for thisId in active_ids:
                if isAnyReleased(objectType, thisId):
                    newID, newIndex=objectType.NewRevision( (getListIDs(thisId),"","") )
                    #TODO: To be implemented management by server options.
#                     objectType.processedIds=[]
#                     objectType._copyProductBom( thisId, newID)
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

    @api.model
    def action_NewRevision(self, ids):
        """
            Call for NewRevision method
        """
        ret=False
        revised=[]
        
        active_ids=self._context.get('active_ids', [])
        active_model=self._context.get('active_model', None)
        if active_ids and active_model:
            objectType=self.env[active_model]
            for thisId in active_ids:
                if isAnyReleased(objectType, thisId):
                    newID, newIndex=objectType.NewRevision( getListIDs(thisId))
                    #TODO: To be implemented management by server options.
#                     objectType.processedIds=[]
#                     objectType._copyProductBom( thisId, newID)
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
     