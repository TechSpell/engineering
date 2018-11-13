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

from openerp        import models, fields
from openerp.tools import drop_view_if_exists

class report_plm_document_file(models.Model):
    _name = "report.plm_document.file"
    _description = "Files details by Directory"
    _auto = False

    year        =   fields.Char('Year', size=64,readonly=True)
    month       =   fields.Char('Month', size=24,readonly=True)
    nbr         =   fields.Integer('# of Files', readonly=True)
    file_size   =   fields.Integer('File Size [kB]', readonly=True)

    _order = "month"

    def init(self, cr):
        drop_view_if_exists(cr, 'report_plm_document_file')
        cr.execute("""
            create or replace view report_plm_document_file as (
                select min(f.id) as id,
                        EXTRACT(YEAR FROM f.create_date) as year,
                        min(to_char(f.create_date, 'MM')||'-'||to_char(f.create_date,'Month')) as month,
                        count(*) as nbr,
                        sum(f.file_size)/1024 as file_size
                from plm_document f
                group by EXTRACT(MONTH FROM f.create_date), EXTRACT(YEAR FROM f.create_date)
              )
        """)

report_plm_document_file()

class report_plm_document_user(models.Model):
    _name = "report.plm_document.user"
    _description = "Files details by Users"
    _auto = False

    year            =   fields.Char('Year', size=64,readonly=True)
    month           =   fields.Selection([('01','January'), ('02','February'), ('03','March'), ('04','April'), ('05','May'), ('06','June'),
                                  ('07','July'), ('08','August'), ('09','September'), ('10','October'), ('11','November'), ('12','December')],'Month',readonly=True)
    day             =   fields.Char('Day', size=64,readonly=True)
    user_id         =   fields.Integer('Owner', readonly=True)
    user            =   fields.Char('User',size=64,readonly=True)
    name            =   fields.Char('Document', size=64,readonly=True)
    docname         =   fields.Char('Name', size=64,readonly=True)
    directory       =   fields.Char('Directory',size=64,readonly=True)
    revision        =   fields.Char('Revision', size=64,readonly=True)
    datas_fname     =   fields.Char('File',size=64,readonly=True)
    create_date     =   fields.Datetime('Date Created', readonly=True)
    change_date     =   fields.Datetime('Modified Date', readonly=True)
    change_user     =   fields.Char('Modified by',size=64,readonly=True)
    file_size       =   fields.Integer('File Size [kB]', readonly=True)
    nbr             =   fields.Integer('# of Files', readonly=True)
    type            =   fields.Char('Directory Type',size=64,readonly=True)

    def init(self, cr):
        drop_view_if_exists(cr, 'report_plm_document_user')
        cr.execute("""
            CREATE OR REPLACE VIEW report_plm_document_user as (
                 SELECT
                     min(f.id) as id,
                     to_char(f.create_date, 'YYYY') as year,
                     to_char(f.create_date, 'MM') as month,
                     to_char(f.create_date, 'DD') as day,
                     f.create_uid as user_id,
                     f.write_uid as change_id,
                     u.login as user,
                     v.login as change_user,
                     count(*) as nbr,
                     f.name as name,
                     f.name as docname,
                     f.revisionid::text as revision,
                     f.datas_fname as datas_fname,
                     f.create_date as create_date,
                     f.file_size/1024 as file_size,
                     f.write_date as change_date,
                     f.preview as preview
                 FROM plm_document f
                     inner join res_users u on (f.create_uid=u.id)
                     inner join res_users v on (f.write_uid=v.id)
                 group by to_char(f.create_date, 'YYYY'), to_char(f.create_date, 'MM'),to_char(f.create_date, 'DD'),f.create_date,f.create_uid,f.write_uid,f.name,f.revisionid::text,f.file_size,u.login,v.login,f.write_date,f.preview,f.datas_fname
             )
        """)

report_plm_document_user()



class report_plm_files_partner(models.Model):
    _name = "report.plm_files.partner"
    _description = "Files details by Partners"
    _auto = False

    name        =   fields.Char('Year',size=64,required=False, readonly=True)
    file_size   =   fields.Integer('File Size [kB]', readonly=True)
    nbr         =   fields.Integer('# of Files', readonly=True)
    partner     =   fields.Char('Partner',size=64,readonly=True)
    month       =   fields.Selection([('01','January'), ('02','February'), ('03','March'), ('04','April'), ('05','May'), ('06','June'),
                                  ('07','July'), ('08','August'), ('09','September'), ('10','October'), ('11','November'), ('12','December')],'Month',readonly=True)

#     def init(self, cr):
#         tools.drop_view_if_exists(cr, 'report_plm_files_partner')
#         cr.execute("""
#             CREATE VIEW report_plm_files_partner as (
#                 SELECT min(f.id) AS id,
#                        COUNT(*) AS nbr,
#                        to_char(date_trunc('month', f.create_date),'YYYY') AS name,
#                        to_char(date_trunc('month', f.create_date),'MM') AS month,
#                        SUM(f.file_size)/1024 AS file_size,
#                        p.name AS partner
# 
#                 FROM plm_document f
#                   LEFT JOIN res_partner p ON (f.partner_id=p.id)
#                 WHERE f.datas_fname IS NOT NULL
#                 GROUP BY p.name, date_trunc('month', f.create_date)
#              )
#          """)
report_plm_files_partner()



class report_plm_document_wall(models.Model):
    _name = "report.plm_document.wall"
    _description = "Users that did not inserted documents since one month"
    _auto = False

    name        =   fields.Date('Month', readonly=True)
    user_id     =   fields.Many2one('res.users', 'Owner',readonly=True)
    user        =   fields.Char('User',size=64,readonly=True)
    month       =   fields.Char('Month', size=24,readonly=True)
    last        =   fields.Datetime('Last Posted Time', readonly=True)


#     def init(self, cr):
#         tools.drop_view_if_exists(cr, 'report_document_wall')
#         cr.execute("""
#             create or replace view report_document_wall as (
#                select max(f.id) as id,
#                to_char(min(f.create_date),'YYYY-MM-DD HH24:MI:SS') as last,
#                f.user_id as user_id, f.user_id as user,
#                to_char(f.create_date,'Month') as month
#                from plm_document f
#                where f.create_date in (
#                    select max(i.create_date)
#                    from ir_attachment i
#                    inner join res_users u on (i.user_id=u.id)
#                    group by i.user_id) group by f.user_id,f.create_date
#                    having (CURRENT_DATE - to_date(to_char(f.create_date,'YYYY-MM-DD'),'YYYY-MM-DD')) > 30
#              )
#         """)
    def init(self, cr):
        drop_view_if_exists(cr, 'report_plm_document_wall')
        cr.execute("""
            create or replace view report_plm_document_wall as (
               select max(f.id) as id,
               to_char(min(f.create_date),'YYYY-MM-DD HH24:MI:SS') as last,
               to_char(f.create_date,'Month') as month,
               f.create_uid as user
               from plm_document f
               where f.create_date in (
                   select max(i.create_date)
                   from ir_attachment i
                   inner join res_users u on (i.create_uid=u.id)
                   group by i.create_uid) group by f.create_uid,f.create_date
                   having (CURRENT_DATE - to_date(to_char(f.create_date,'YYYY-MM-DD'),'YYYY-MM-DD')) > 30
             )
        """)
report_plm_document_wall()


class report_plm_checkout_board(models.Model):
    _name = "report.plm_checkout.board"
    _description = "Checked-Out Documents"
    _auto = False

    year            =   fields.Char('Year', size=64,readonly=True)
    month           =   fields.Selection([('01','January'), ('02','February'), ('03','March'), ('04','April'), ('05','May'), ('06','June'),
                                  ('07','July'), ('08','August'), ('09','September'), ('10','October'), ('11','November'), ('12','December')],'Month',readonly=True)
    day             =   fields.Char('Day', size=64,readonly=True)
    user_id         =   fields.Integer('Owner', readonly=True)
    user            =   fields.Char('User',size=64,readonly=True)
    name            =   fields.Char('Document', size=64,readonly=True)
    docname         =   fields.Char('Name', size=64,readonly=True)
    directory       =   fields.Char('PWS Directory',size=128,readonly=True)
    revision        =   fields.Char('Revision', size=64,readonly=True)
    hostname        =   fields.Char('Hostname',size=64,readonly=True)
    create_date     =   fields.Datetime('Date Created', readonly=True)
    change_date     =   fields.Datetime('Modified Date', readonly=True)
    change_user     =   fields.Char('Modified by',size=64,readonly=True)
    nbr             =   fields.Integer('# of Files', readonly=True)

    def init(self, cr):
        drop_view_if_exists(cr, 'report_plm_checkout_board')
        cr.execute("""
            CREATE OR REPLACE VIEW report_plm_checkout_board as (
                 SELECT
                     min(f.id) as id,
                     to_char(f.create_date, 'YYYY') as year,
                     to_char(f.create_date, 'MM') as month,
                     to_char(f.create_date, 'DD') as day,
                     f.create_date as create_date,
                     f.create_uid as user_id,
                     f.write_uid as change_user,
                     f.write_date as change_date,
                     f.hostpws as directory,
                     f.hostname as hostname,
                     u.login as user,
                     v.name as name,
                     v.name as docname,
                     v.revisionid::text as revision,
                     count(*) as nbr
                 FROM plm_checkout f
                     INNER JOIN res_users u on (f.create_uid=u.id)
                     INNER JOIN plm_document v on (f.documentid=v.id)
                 GROUP BY to_char(f.create_date, 'YYYY'), to_char(f.create_date, 'MM'),to_char(f.create_date, 'DD'),f.create_date,f.create_uid,f.write_date,f.write_uid,v.name,v.revisionid::text,u.login,f.hostpws,f.hostname
             )
        """)

report_plm_checkout_board()

