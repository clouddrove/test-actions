from .odoo_push import odoo_push_cmd
from .sync_client import sync_client_cmd, sync_undo_cmd, dump_census_sheet_cmd
from .update_data import update_data_cmd

__ALL__ = [
    odoo_push_cmd,
    sync_client_cmd,
    sync_undo_cmd,
    dump_census_sheet_cmd,
    update_data_cmd,
]