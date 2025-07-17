from datetime import timedelta

from odoo.exceptions import ValidationError
from odoo import models, fields, api

class CurrentStockReportWizard(models.TransientModel):
    _name = 'current.stock.report.wizard'
    _description = 'Current Stock Report Wizard'

    start_date = fields.Date(string='Start Date', required=True, default=lambda self: fields.Date.to_string(fields.Date.today() - timedelta(days=30)))
    end_date = fields.Date(string='End Date', required=True, default=fields.Date.context_today)

    product_category_ids = fields.Many2many(
        string="Product Categories",
        comodel_name='product.category',
        relation='current_stock_product_catg_rel',
    )

    product_tag_ids = fields.Many2many(
        string="Product Template Tags",
        comodel_name='product.tag',
        relation='current_stock_product_tag_rel',
    )
    exclusive_loc_ids = fields.Many2many(
        'stock.location',
        string='Exclusive Locations',
        domain=[('usage', '=', 'internal'), ('active', '=', True)],
        relation='current_stock_exclusive_location_rel'
    )
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.end_date < record.start_date:
                raise ValidationError('End Date must be greater than Start Date.')
            if (record.end_date - record.start_date).days > 365:
                raise ValidationError('The duration between Start Date and End Date should not exceed one year.')

    def generate_report_htm(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        report_url = f"{base_url}/web/current_stock_report?start_date={self.start_date}&end_date={self.end_date}" \
                     f"&display_type=htm&category_ids={self.product_category_ids.ids}" \
                     f"&tag_ids={self.product_tag_ids.ids}&exclusive_loc_ids={self.exclusive_loc_ids.ids}"

        return {
            'type': 'ir.actions.act_url',
            'url': report_url,
            'target': 'new'
        }
