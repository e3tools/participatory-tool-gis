// Copyright (c) 2024, Steve Nyaga and contributors
// For license information, please see license.txt

frappe.ui.form.on("Shape File", {
	refresh(frm) { 
        if(frm.doc.field_mappings){
            frm.trigger('resetGridTitles');
        }
	},
    resetGridTitles: function(frm){ 
		var grid = frm.get_field('items').grid; 
		grid.header_row.columns_list.forEach(function(column) { 
            let fld = frm.doc.field_mappings.filter(el => el.table_field == column.df.fieldname);
            if(fld.length > 0){
                column.df.label = fld[0].attribute;
            } 
		});
		grid.refresh();
	},
});
