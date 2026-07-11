{
    'name': "Current Stock Report",
    'summary': "Current Stock Report",
    'description': """
        Current Stock Report showing opening and closing balances with receipts and Issues 
    """,
    "license": "LGPL-3",
    'author': "Sybaz",
    'website': "https://sybaz.com.pk/",
    'category': 'Inventory/Inventory',
    'version': '18.0.1.0.1',
    'depends': ['stock'],

    'data': [
        'security/ir.model.access.csv',
        'wizard/current_stock_report_wizard.xml',
        'views/current_stock_report_template.xml',
        'views/current_stock_report_template_pdf.xml',
    ],
    'images': ['static/description/main_screenshot.png'],
    'application': False,
    'installable': True,
    'auto_install': False,
    'price': 15,
    'currency': 'USD',
}
