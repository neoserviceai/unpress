// Copyright (c) 2026, Neoservice
// License: AGPL-3.0

frappe.ui.form.on("WP Migration", {
	refresh(frm) {
		if (frm.is_new()) {
			frm.set_intro(__("Enter the WordPress site URL, save, then run the analysis."));
			return;
		}

		frm.add_custom_button(__("1. Analyze site"), () => {
			frm.call("probe", {}, () => frm.reload_doc());
		});

		if (frm.doc.wxr_file) {
			frm.add_custom_button(__("2. Import into Builder"), () => {
				frappe.confirm(
					__("Import the attached export into Builder Pages? Existing pages with the same route will be updated."),
					() => {
						frappe.show_alert({ message: __("Import running..."), indicator: "blue" });
						frm.call("start_import", {}, () => {
							frm.reload_doc();
							frappe.show_alert({ message: __("Import finished"), indicator: "green" });
						});
					}
				);
			});
		} else if (frm.doc.status === "Probed") {
			frm.set_intro(
				__("Attach the WXR export file (WordPress: Tools → Export → All content) to enable the import.")
			);
		}

		if (frm.doc.status === "Imported" && frm.doc.report) {
			try {
				const report = JSON.parse(frm.doc.report);
				(report.pages || []).slice(0, 15).forEach((p) => {
					frm.add_custom_button(
						`${p.title} (${p.action})`,
						() => window.open(p.editor, "_blank"),
						__("Open in Builder")
					);
				});
			} catch (e) {
				// report not parseable — nothing to add
			}
		}
	},
});
