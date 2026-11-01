// Copyright (c) 2025, Frappe Technologies Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on("Website Header Footer Config", {
	refresh(frm) {
		frm.trigger("update_preview");
	},

	header_layout(frm) {
		frm.trigger("update_preview");
	},

	search_type(frm) {
		frm.trigger("update_preview");
	},

	show_user(frm) {
		frm.trigger("update_preview");
	},

	show_wishlist(frm) {
		frm.trigger("update_preview");
	},

	show_cart(frm) {
		frm.trigger("update_preview");
	},

	show_cta(frm) {
		frm.trigger("update_preview");
	},

	cta_text(frm) {
		frm.trigger("update_preview");
	},

	logo_type(frm) {
		frm.trigger("update_preview");
	},

	logo_text(frm) {
		frm.trigger("update_preview");
	},

	header_bg_color(frm) {
		frm.trigger("update_preview");
	},

	header_text_color(frm) {
		frm.trigger("update_preview");
	},

	update_preview(frm) {
		const layout = frm.doc.header_layout || "Logo | Menu Center | Icons";
		const searchType = frm.doc.search_type || "None";
		const bgColor = frm.doc.header_bg_color || "#1a1a1a";
		const textColor = frm.doc.header_text_color || "#ffffff";
		const preview = generate_preview(layout, searchType, frm.doc, bgColor, textColor);

		const previewContainer = frm.get_field("header_preview").$wrapper;
		previewContainer.html(`
			<div style="padding: 15px; background: var(--subtle-fg); border-radius: 8px; margin-top: 10px;">
				<div style="font-size: 11px; color: var(--text-muted); margin-bottom: 8px; text-transform: uppercase; letter-spacing: 0.5px;">
					${__("Header Preview")}
				</div>
				<div style="border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08);">
					${preview}
				</div>
			</div>
		`);
	}
});

function generate_preview(layout, searchType, doc, bgColor, textColor) {
	const logoText = doc.logo_text || "My Site";
	const ctaText = doc.cta_text || "Contact";

	// Derive muted color from text color (with transparency)
	const textMuted = textColor + "cc";
	const hoverBg = textColor + "15";
	const borderColor = textColor + "20";

	// Build icons HTML based on checkboxes
	let iconsHtml = "";

	// Search (icon or bar based on search_type)
	if (searchType === "Icon (overlay)") {
		iconsHtml += `<span style="padding: 6px; cursor: pointer; color: ${textMuted};" title="${__("Search")}">
			<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<circle cx="11" cy="11" r="8"></circle>
				<line x1="21" y1="21" x2="16.65" y2="16.65"></line>
			</svg>
		</span>`;
	} else if (searchType === "Search Bar (inline)") {
		iconsHtml += `<div style="display: flex; align-items: center; background: ${hoverBg}; border: 1px solid ${borderColor}; padding: 6px 12px; border-radius: 8px; gap: 8px; min-width: 160px;">
			<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="${textMuted}" stroke-width="2">
				<circle cx="11" cy="11" r="8"></circle>
				<line x1="21" y1="21" x2="16.65" y2="16.65"></line>
			</svg>
			<span style="color: ${textMuted}; font-size: 12px;">${__("Search")}...</span>
		</div>`;
	}

	// User icon
	if (doc.show_user) {
		iconsHtml += `<span style="padding: 6px; cursor: pointer; color: ${textMuted};" title="${__("User")}">
			<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
				<circle cx="12" cy="7" r="4"></circle>
			</svg>
		</span>`;
	}

	// Wishlist icon
	if (doc.show_wishlist) {
		iconsHtml += `<span style="padding: 6px; cursor: pointer; color: ${textMuted};" title="${__("Wishlist")}">
			<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path>
			</svg>
		</span>`;
	}

	// Cart icon
	if (doc.show_cart) {
		iconsHtml += `<span style="padding: 6px; cursor: pointer; position: relative; color: ${textMuted};" title="${__("Cart")}">
			<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
				<circle cx="9" cy="21" r="1"></circle>
				<circle cx="20" cy="21" r="1"></circle>
				<path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path>
			</svg>
			<span style="position: absolute; top: 0; right: 0; background: ${textColor}; color: ${bgColor}; font-size: 9px; width: 14px; height: 14px; border-radius: 50%; display: flex; align-items: center; justify-content: center;">2</span>
		</span>`;
	}

	const iconsContainer = iconsHtml
		? `<div style="display: flex; align-items: center; gap: 4px;">${iconsHtml}</div>`
		: "";

	// CTA button
	const ctaHtml = doc.show_cta
		? `<button style="background: ${textColor}; color: ${bgColor}; border: none; padding: 8px 16px; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; margin-left: 8px;">${ctaText}</button>`
		: "";

	// Menu placeholder
	const menuHtml = `<nav style="display: flex; gap: 24px; color: ${textMuted}; font-size: 14px; font-weight: 500;">
		<span style="cursor: pointer;">Accueil</span>
		<span style="cursor: pointer;">Produits</span>
		<span style="cursor: pointer;">Contact</span>
	</nav>`;

	// Logo
	const logoHtml = `<div style="font-weight: 700; font-size: 18px; color: ${textColor};">${logoText}</div>`;

	// Main header content
	let mainHeaderHtml = "";

	if (layout === "Menu Left | Logo Center | Icons") {
		// Layout B: [Menu] [Logo centered] [Icons/CTA]
		mainHeaderHtml = `
			<div style="display: flex; align-items: center; justify-content: space-between; padding: 16px 24px; background: ${bgColor};">
				<div style="flex: 1;">${menuHtml}</div>
				<div style="flex: 0 0 auto; text-align: center;">${logoHtml}</div>
				<div style="flex: 1; display: flex; justify-content: flex-end; align-items: center; gap: 8px;">
					${iconsContainer}
					${ctaHtml}
				</div>
			</div>
		`;
	} else if (layout === "Logo | Menu Right | Icons") {
		// Layout A with menu right: [Logo] [Menu aligned right] [Icons/CTA]
		mainHeaderHtml = `
			<div style="display: flex; align-items: center; justify-content: space-between; padding: 16px 24px; background: ${bgColor};">
				<div style="flex: 0 0 auto;">${logoHtml}</div>
				<div style="flex: 1; display: flex; justify-content: flex-end; padding-right: 24px;">${menuHtml}</div>
				<div style="display: flex; align-items: center; gap: 8px;">
					${iconsContainer}
					${ctaHtml}
				</div>
			</div>
		`;
	} else {
		// Layout A with menu center: [Logo] [Menu centered] [Icons/CTA]
		mainHeaderHtml = `
			<div style="display: flex; align-items: center; justify-content: space-between; padding: 16px 24px; background: ${bgColor};">
				<div style="flex: 0 0 auto;">${logoHtml}</div>
				<div style="flex: 1; display: flex; justify-content: center;">${menuHtml}</div>
				<div style="display: flex; align-items: center; gap: 8px;">
					${iconsContainer}
					${ctaHtml}
				</div>
			</div>
		`;
	}

	// Full width search bar at bottom - always dark style
	let searchBarBottomHtml = "";
	if (searchType === "Search Bar (full width bottom)") {
		searchBarBottomHtml = `
			<div style="border-top: 1px solid rgba(255,255,255,0.1); padding: 12px 24px; background: #1a1a1a;">
				<div style="display: flex; align-items: center; background: rgba(255,255,255,0.1); border: 1px solid rgba(255,255,255,0.1); padding: 10px 16px; border-radius: 8px; gap: 10px;">
					<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.6)" stroke-width="2">
						<circle cx="11" cy="11" r="8"></circle>
						<line x1="21" y1="21" x2="16.65" y2="16.65"></line>
					</svg>
					<span style="color: rgba(255,255,255,0.5); font-size: 14px;">${__("Search for products")}...</span>
				</div>
			</div>
		`;
	}

	return mainHeaderHtml + searchBarBottomHtml;
}
