import ast

from odoo import http
from odoo.http import request
import xlsxwriter
from io import BytesIO
from datetime import datetime

class CurrentStockReportController(http.Controller):
    @http.route('/web/current_stock_report', type="http", auth="user", website=True, csrf=False)
    def account_current_stock_report(self, start_date, end_date, display_type, category_ids, tag_ids, exclusive_loc_ids, **kwargs):
        data = self._get_data(start_date, end_date, category_ids, tag_ids, exclusive_loc_ids)
        disp_start_date = datetime.strptime(start_date, '%Y-%m-%d').strftime('%d-%m-%Y')
        disp_end_date = datetime.strptime(end_date, '%Y-%m-%d').strftime('%d-%m-%Y')

        if display_type == 'htm':
            return request.render('sb_current_stock_report.current_stock_report_template', {
                'data': data,
                'start_date': start_date,
                'end_date': end_date,
                'disp_start_date': disp_start_date,
                'disp_end_date': disp_end_date,
                'category_ids': category_ids,
                'tag_ids': tag_ids,
                'company_name': request.env.user.company_id.name
            })
        elif display_type == 'xls':
            file_content = self._create_excel_file(data, start_date, end_date)
            file_name = f"current_stock_report_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"

            return request.make_response(
                file_content,
                headers=[
                    ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                    ('Content-Disposition', f'attachment; filename={file_name}')
                ]
            )
        else:
            datas = {
                'det_data': data, 'start_date': disp_start_date, 'end_date': disp_end_date, 'company_name': request.env.user.company_id.name
            }
            pdf = request.env['ir.actions.report'].sudo()._render_qweb_pdf('sb_current_stock_report.action_current_stock_report',  data=datas)[0]

            pdfhttpheaders = [
                ('Content-Type', 'application/pdf'),
                ('Content-Length', len(pdf)),
            ]
            return request.make_response(pdf, headers=pdfhttpheaders)


    def _get_data(self, start_date, end_date, category_ids, tag_ids, exclusive_loc_ids):
        return self._get_current_stock_data(start_date, end_date, category_ids, tag_ids, exclusive_loc_ids)

    def _get_current_stock_data(self, start_date, end_date, category_ids, tag_ids, exclusive_loc_ids):
        company_id = request.env.company.id
        user_lang = request.env.user.lang
        # en_US = {user_lang}
        query = """
            select pc.complete_name as categ_name, pt.name as product_name, pt.default_code as internal_ref, 
            (select STRING_AGG(ptag.name->>'en_US', ', ') AS tag_names from product_tag_product_template_rel pt_rel, product_tag ptag 
            where pt.id = pt_rel.product_template_id and pt_rel.product_tag_id = ptag.id) as tag_names,
            sum(case when sml.date < %s and slu.usage in ('internal','transit') then -sml.quantity else 0 end+case when (sml.date < %s and slu.usage not in ('internal','transit')) then sml.quantity else 0 end) as open_qty,
            sum(case when sml.date >= %s and slu.usage not in ('internal','transit') and dlu.usage in ('internal','transit') then sml.quantity else 0 end) as rcvd_qty,
            sum(case when sml.date >= %s and slu.usage in ('internal','transit') and dlu.usage not in ('internal','transit') then sml.quantity else 0 end) as issu_qty
            from stock_move_line sml, stock_move as sm, product_product pp, product_template pt, product_category pc, stock_location slu, stock_location dlu 
            where sml.move_id=sm.id and pp.product_tmpl_id=pt.id and sml.product_id=pp.id and pt.categ_id=pc.id and sml.location_id=slu.id and sml.location_dest_id = dlu.id and slu.usage != dlu.usage 
            and sml.state='done' and sml.date<=%s AND sml.company_id = %s
        """
        start_date = start_date + " 00:00:00"
        end_date = end_date + " 23:59:59"
        params = [start_date, start_date, start_date, start_date, end_date, company_id]

        exclusive_loc_ids = exclusive_loc_ids.strip('[]\'').replace(' ', '')
        if exclusive_loc_ids:
            query += """
            AND sml.location_dest_id not in (""" + exclusive_loc_ids + """)
            """

        category_ids = category_ids.strip('[]\'').replace(' ', '')
        if category_ids:
            query += """
            AND pt.categ_id in (""" + category_ids + """)
            """

        tag_ids = ast.literal_eval(tag_ids)
        domain = []
        # Add tag condition if tag_ids is not empty
        if tag_ids:
            domain.append(('product_tag_ids', 'in', tag_ids))

        product_ids = request.env['product.product'].search(domain)
        if product_ids:
            product_ids_str = ','.join(map(str, product_ids.ids))
            query += """
            AND sml.product_id in (""" + product_ids_str + """)
            """

        query += " GROUP BY pc.complete_name, pt.id, pt.default_code ORDER BY pc.complete_name, pt.name"

        request.env.cr.execute(query, tuple(params))
        result = request.env.cr.dictfetchall()

        user_lang = request.env.user.lang
        report_data = []
        for line in result:
            closing_balance = line['open_qty'] + line['rcvd_qty'] - line['issu_qty']
            report_data.append({
                'categ_name': line['categ_name'],
                'product_ref': line['internal_ref'],
                'product_name': line['product_name'][user_lang],
                'tag_names': line['tag_names'],
                'open_qty_raw': line['open_qty'],
                'rcvd_qty_raw': line['rcvd_qty'],
                'issu_qty_raw': line['issu_qty'],
                'clos_qty_raw': closing_balance,
                'open_qty_fmt': self.format_number_value(line['open_qty']),
                'rcvd_qty_fmt': self.format_number_value(line['rcvd_qty']),
                'issu_qty_fmt': self.format_number_value(line['issu_qty']),
                'clos_qty_fmt': self.format_number_value(closing_balance)
            })

        return report_data

    def format_number_value(self, balance):
        # Format negative values with parentheses and keep precision to 2 decimal places
        if balance < 0:
            return '({:,.4f})'.format(abs(balance))
        else:
            return '{:,.4f}'.format(balance)

    def _create_excel_file(self, data, start_date, end_date):
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Current Stock Report')

        decimal_format = workbook.add_format({'num_format': '#,##0.0000;(#,##0.0000)'})
        bold = workbook.add_format({'bold': True})
        format0 = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter'
        })
        format1 = workbook.add_format({
            'bold': True,
            'border': 1
        })
        format2 = workbook.add_format({
            'bold': True,
            'align': 'right',
            'border': 1
        })
        format3 = workbook.add_format({
            'bold': True,
            'border': 1,
            'num_format': '#,##0.0000;(#,##0.0000)'
        })
        format4 = workbook.add_format({
            'bold': True,
            'top': 1,
            'num_format': '#,##0.0000;(#,##0.0000)'
        })

        c = 0
        worksheet.set_column(c, c, 40)
        c += 1
        worksheet.set_column(c, c, 15)
        c += 1
        worksheet.set_column(c, c, 15)
        c += 1
        worksheet.set_column(c, c, 15)
        c += 1
        worksheet.set_column(c, c, 15)
        c += 1
        worksheet.set_column(c, c, 15)
        c += 1
        worksheet.set_column(c, c, 15)

        # Get the company name
        company_name = request.env.user.company_id.name

        row = 0
        # Write the company name to the first row
        worksheet.merge_range(row, 0, row, 5, company_name, format0)

        row = row + 1
        worksheet.merge_range(row, 0, row, 5, 'Current Stock Report', format0)
        headers = ['Opening Balance', 'Received', 'Issued', 'Closing Balance']

        row = row + 1
        start_date_str = datetime.strptime(start_date, "%Y-%m-%d")
        end_date_str = datetime.strptime(end_date, "%Y-%m-%d")
        worksheet.write(row, 0, "Date From: "+start_date_str.strftime('%d-%m-%Y'), bold)
        worksheet.write(row, 4, "Date To: "+end_date_str.strftime('%d-%m-%Y'), bold)

        # Write the header starting from the second row
        row = row + 1
        worksheet.write(row, 0, 'Title', format1)
        worksheet.write(row, 1, 'ID', format1)
        worksheet.write(row, 2, 'Tags', format1)
        for col_num, header in enumerate(headers):
            worksheet.write(row, col_num+3, header, format2)

        # Write the data
        row = row + 1
        row_num = row
        current_category = ""
        for line in data[0:]:
            if line['categ_name'] != current_category:
                if row_num != row:
                    ct_opening = sum(line['open_qty_raw'] for line in data if line['categ_name'] == current_category)
                    ct_received = sum(line['rcvd_qty_raw'] for line in data if line['categ_name'] == current_category)
                    ct_issued = sum(line['issu_qty_raw'] for line in data if line['categ_name'] == current_category)
                    ct_closing = sum(line['clos_qty_raw'] for line in data if line['categ_name'] == current_category)
                    worksheet.write(row_num, 0, "")
                    worksheet.write(row_num, 1, "")
                    worksheet.write(row_num, 2, "Category Total", format4)
                    worksheet.write(row_num, 3, ct_opening, format4)
                    worksheet.write(row_num, 4, ct_received, format4)
                    worksheet.write(row_num, 5, ct_issued, format4)
                    worksheet.write(row_num, 6, ct_closing, format4)
                    row_num = row_num + 1

                current_category = line['categ_name']
                worksheet.write(row_num, 0, current_category, bold)
                row_num = row_num + 1

            worksheet.write(row_num, 0, line['product_name'])
            worksheet.write(row_num, 1, line['product_ref'])
            worksheet.write(row_num, 2, line['tag_names'])
            worksheet.write(row_num, 3, line['open_qty_raw'], decimal_format)
            worksheet.write(row_num, 4, line['rcvd_qty_raw'], decimal_format)
            worksheet.write(row_num, 5, line['issu_qty_raw'], decimal_format)
            worksheet.write(row_num, 6, line['clos_qty_raw'], decimal_format)
            row_num = row_num + 1

        ct_opening = sum(line['open_qty_raw'] for line in data if line['categ_name'] == current_category)
        ct_received = sum(line['rcvd_qty_raw'] for line in data if line['categ_name'] == current_category)
        ct_issued = sum(line['issu_qty_raw'] for line in data if line['categ_name'] == current_category)
        ct_closing = sum(line['clos_qty_raw'] for line in data if line['categ_name'] == current_category)
        worksheet.write(row_num, 0, "")
        worksheet.write(row_num, 1, "")
        worksheet.write(row_num, 2, "Category Total", format4)
        worksheet.write(row_num, 3, ct_opening, format4)
        worksheet.write(row_num, 4, ct_received, format4)
        worksheet.write(row_num, 5, ct_issued, format4)
        worksheet.write(row_num, 6, ct_closing, format4)
        row_num = row_num + 1

        row_num = row_num + 1
        gt_opening = sum(line['open_qty_raw'] for line in data)
        gt_received = sum(line['rcvd_qty_raw'] for line in data)
        gt_issued = sum(line['issu_qty_raw'] for line in data)
        gt_closing = sum(line['clos_qty_raw'] for line in data)
        worksheet.write(row_num, 0, "")
        worksheet.write(row_num, 1, "")
        worksheet.write(row_num, 2, "Grand Total", format2)
        worksheet.write(row_num, 3, gt_opening, format3)
        worksheet.write(row_num, 4, gt_received, format3)
        worksheet.write(row_num, 5, gt_issued, format3)
        worksheet.write(row_num, 6, gt_closing, format3)

        workbook.close()
        output.seek(0)
        return output.read()

