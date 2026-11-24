// Small helpers for the tables; the site works without them.

// Keyboard scrolling, vim style: h / l or the left and right arrows scroll the wide table nearest the middle of
// the screen sideways; j / k scroll the page down and up. Keys are ignored while typing in a form field or with
// a modifier key held, so browser shortcuts keep working.
(function () {
	var STEP_X = 160, STEP_Y = 80;

	function wideTable() {
		var best = null, bestDistance = Infinity, middle = window.innerHeight / 2;
		document.querySelectorAll(".scroll").forEach(function (box) {
			if (box.scrollWidth <= box.clientWidth) return;   // nothing to scroll
			var r = box.getBoundingClientRect();
			if (r.bottom < 0 || r.top > window.innerHeight) return;   // not on screen
			var d = middle < r.top ? r.top - middle : middle > r.bottom ? middle - r.bottom : 0;
			if (d < bestDistance) { best = box; bestDistance = d; }
		});
		return best;
	}

	document.addEventListener("keydown", function (e) {
		if (e.ctrlKey || e.metaKey || e.altKey) return;
		var t = e.target;
		if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
		var dx = 0, dy = 0;
		switch (e.key) {
			case "h": case "ArrowLeft": dx = -STEP_X; break;
			case "l": case "ArrowRight": dx = STEP_X; break;
			case "j": dy = STEP_Y; break;
			case "k": dy = -STEP_Y; break;
			default: return;
		}
		if (dx) {
			var box = wideTable();
			if (!box) return;
			box.scrollBy({ left: dx, behavior: "smooth" });
		} else {
			window.scrollBy({ top: dy, behavior: "smooth" });
		}
		e.preventDefault();
	});
})();

// Sorting: click a column heading to sort the table by it; click again to reverse. Numbers sort largest first
// (a cell such as "11 +1" counts as 12, after a plain 12), text sorts A to Z, and empty cells ("–") always go last. Total rows stay
// at the bottom. Group headings that span several columns do not sort.
(function () {
	// "11 +1" is 11 official and 1 unofficial papers: it sorts by the total, 12, and among equal totals the one
	// with more official papers comes first
	function number(text) {
		var t = text.replace(/,/g, "");
		var m = t.match(/-?\d+(\.\d+)?/);
		if (!m) return null;
		var extra = t.slice(m.index + m[0].length).match(/\+\s*(\d+)/);
		var official = parseFloat(m[0]);
		return extra ? official + parseInt(extra[1], 10) + official / 1000 : official + official / 1000;
	}

	// which column each heading cell stands for, taking rowspan and colspan into account
	function leafHeadings(thead) {
		var grid = [], leaves = [];
		Array.prototype.forEach.call(thead.rows, function (row, r) {
			grid[r] = grid[r] || [];
			var c = 0;
			Array.prototype.forEach.call(row.cells, function (cell) {
				while (grid[r][c]) c++;
				var rs = cell.rowSpan || 1, cs = cell.colSpan || 1;
				for (var i = 0; i < rs; i++) for (var j = 0; j < cs; j++) {
					grid[r + i] = grid[r + i] || [];
					grid[r + i][c + j] = cell;
				}
				if (cs === 1 && r + rs === thead.rows.length) leaves.push([cell, c]);
				c += cs;
			});
		});
		return leaves;
	}

	// rows hidden by the front page's row button take no number and no cup
	function hiddenRow(table, tr) {
		return table.classList.contains("rows-collapsed") && tr.classList.contains("more-row");
	}
	function renumber(table) {
		var k = 0;
		Array.prototype.forEach.call(table.tBodies[0].rows, function (tr) {
			var n = tr.querySelector("td.rank .n");   // the # column numbers the rows in the order shown
			if (!n || tr.classList.contains("total") || hiddenRow(table, tr)) return;
			n.textContent = ++k;
		});
	}

	function sortBy(table, column, cell) {
		var body = table.tBodies[0];
		var rows = Array.prototype.filter.call(body.rows, function (tr) { return !tr.classList.contains("total"); });
		var totals = Array.prototype.filter.call(body.rows, function (tr) { return tr.classList.contains("total"); });
		var values = rows.map(function (tr) {
			var td = tr.cells[column], text = td ? td.textContent.trim() : "";
			// a cell marked data-last (an estimate with nothing to estimate from) goes last, like an empty one
			if (td && td.hasAttribute("data-last")) text = "";
			return { tr: tr, text: text, num: number(text) };
		});
		var numeric = values.filter(function (v) { return v.text && v.text !== "–"; }).every(function (v) { return v.num !== null; });
		var previous = cell.getAttribute("aria-sort");
		var order = previous ? (previous === "descending" ? "ascending" : "descending") : (numeric ? "descending" : "ascending");
		var sign = order === "ascending" ? 1 : -1;
		values.sort(function (a, b) {
			var ea = !a.text || a.text === "–", eb = !b.text || b.text === "–";
			if (ea !== eb) return ea ? 1 : -1;
			if (numeric) return sign * ((a.num || 0) - (b.num || 0));
			return sign * a.text.localeCompare(b.text);
		});
		table.querySelectorAll("th[aria-sort]").forEach(function (th) { th.removeAttribute("aria-sort"); });
		cell.setAttribute("aria-sort", order);
		values.forEach(function (v) { body.appendChild(v.tr); });
		totals.forEach(function (tr) { body.appendChild(tr); });
		renumber(table);
		podium(table, numeric && !cell.hasAttribute("data-nocup") ? column : null, order === "ascending");
		if (table.paginate) table.paginate(0, false);   // a paged table starts again from its first page
	}

	// Cups for the top three values of a .podium table, in the order shown: gold, silver, bronze. Sorted by a
	// number column, tied rows share a cup and the next value takes the next cup (one gold and two silvers are
	// followed by a bronze); sorted largest first a zero gets no cup, and sorted by text there are none. A column
	// marked data-nocup (a figure where first place means nothing good) never gets cups.
	var CUP = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h10v2h3v3a4 4 0 0 1-4 4h-.3A5 5 0 0 1 13 14.9V18h3v2H8v-2h3v-3.1A5 5 0 0 1 8.3 12H8a4 4 0 0 1-4-4V5h3V3zm0 4H6v1a2 2 0 0 0 1 1.7V7zm10 0v2.7A2 2 0 0 0 18 8V7h-1z"/></svg>';
	var PLACES = ["gold", "silver", "bronze"];
	function podium(table, column, ascending) {
		if (!table.classList.contains("podium")) return;
		table.lastPodium = [column, ascending];   // the row button draws the cups again with the same column
		var rows = Array.prototype.filter.call(table.tBodies[0].rows, function (tr) { return !tr.classList.contains("total"); });
		var place = -1, last = null, k = -1;
		rows.forEach(function (tr) {
			var slot = tr.querySelector(".cup");
			if (!slot) return;
			if (hiddenRow(table, tr)) { slot.className = "cup"; slot.innerHTML = ""; slot.removeAttribute("title"); return; }
			k += 1;
			var cell = column === undefined || column === null ? null : tr.cells[column];
			var key = column === undefined ? k : !cell || cell.hasAttribute("data-last") ? null : number(cell.textContent);
			// largest first, a zero wins nothing and takes no place; smallest first, a zero is the best value
			var nothing = column !== undefined && key === 0 && !ascending;
			if (key === null && column !== undefined) { place = 99; }
			else if (!nothing && (place < 0 || key !== last)) { place += 1; }   // ties share a cup; the next value takes the next one
			if (!nothing) last = key;
			slot.className = "cup";
			slot.innerHTML = "";
			slot.removeAttribute("title");
			if (place >= 0 && place < 3 && !nothing) {
				slot.classList.add(PLACES[place]);
				slot.innerHTML = CUP;
				slot.title = "#" + (place + 1);
			}
		});
	}
	// before any sorting the rows are in order of total accepted papers, the column marked data-podium
	document.querySelectorAll("table.podium").forEach(function (table) {
		var start = leafHeadings(table.tHead).filter(function (pair) { return pair[0].hasAttribute("data-podium"); })[0];
		podium(table, start ? start[1] : undefined);
	});

	// The front page table starts without its detail columns (headings marked data-extra); the button above it
	// shows them again. Cells are marked by the column of their heading, so sorting and cups are unaffected.
	document.querySelectorAll("table[data-collapsible]").forEach(function (table) {
		var columns = leafHeadings(table.tHead).filter(function (pair) { return pair[0].hasAttribute("data-extra"); })
			.map(function (pair) { return pair[1]; });
		Array.prototype.forEach.call(table.tBodies[0].rows, function (tr) {
			columns.forEach(function (c) { if (tr.cells[c]) tr.cells[c].classList.add("xcol"); });
		});
		var button = (table.id && document.querySelector('button.more-columns[aria-controls="' + table.id + '"]'))
			|| document.querySelector("button.more-columns");
		if (!button) return;
		// the label says how many columns it shows; the tooltip names them
		var show = (columns.length === 1 && button.dataset.showOne ? button.dataset.showOne : button.dataset.show)
			.replace("{n}", columns.length);
		// the tooltip names the top-level headings only: a group such as Co-authors, not its sub-columns
		var names = Array.prototype.map.call(table.tHead.rows[0].querySelectorAll("th[data-extra]"), function (th) {
			return th.textContent.replace(/\s+/g, " ").trim();
		}).filter(function (n) { return n; });
		button.textContent = show;
		if (names.length) button.title = button.dataset.names.replace("{names}", names.join(", "));
		button.addEventListener("click", function () {
			var hidden = table.classList.toggle("collapsed");
			button.textContent = hidden ? show : button.dataset.hide;
			button.setAttribute("aria-expanded", hidden ? "false" : "true");
			window.dispatchEvent(new Event("resize"));   // the pinned columns are measured again
		});
	});

	// The front page table starts with the professors who have an accepted paper; the button under it shows the
	// rest (rows marked more-row). Without JavaScript every row shows (a noscript rule) and the button stays hidden.
	document.querySelectorAll("table[data-rows-collapsible]").forEach(function (table) {
		var button = table.id && document.querySelector('button.more-rows[aria-controls="' + table.id + '"]');
		if (!button) return;
		button.hidden = false;
		button.addEventListener("click", function () {
			var hidden = table.classList.toggle("rows-collapsed");
			button.textContent = hidden ? button.dataset.show : button.dataset.hide;
			button.setAttribute("aria-expanded", hidden ? "false" : "true");
			renumber(table);
			if (table.lastPodium) podium(table, table.lastPodium[0], table.lastPodium[1]);
			window.dispatchEvent(new Event("resize"));   // the pinned columns are measured again
		});
	});

	// Long tables (data-page-size) show one page of rows at a time, with page links in the nav.pager after them
	// (aria-controls names the table). Sorting sorts every row, then shows the first page again. The page itself
	// hides the rows after the first page (class off-page), so the first view draws only that many.
	document.querySelectorAll("table[data-page-size]").forEach(function (table) {
		var size = parseInt(table.dataset.pageSize, 10), body = table.tBodies[0];
		var nav = table.id && document.querySelector('nav.pager[aria-controls="' + table.id + '"]');
		if (!size || !nav) return;
		function rows() { return Array.prototype.filter.call(body.rows, function (tr) { return !tr.classList.contains("total"); }); }
		function link(label, page, current, disabled) {
			var b = document.createElement("button");
			b.type = "button";
			b.textContent = label;
			if (current) b.setAttribute("aria-current", "page");
			if (disabled) b.disabled = true;
			b.addEventListener("click", function () { show(page, true); });
			return b;
		}
		function show(page, scroll) {
			var all = rows(), pages = Math.max(1, Math.ceil(all.length / size));
			page = Math.max(0, Math.min(page, pages - 1));
			all.forEach(function (tr, k) { tr.classList.toggle("off-page", Math.floor(k / size) !== page); });
			nav.innerHTML = "";
			nav.hidden = pages < 2;
			nav.appendChild(link(nav.dataset.prev, page - 1, false, page === 0));
			for (var p = 0; p < pages; p++) nav.appendChild(link(String(p + 1), p, p === page, false));
			nav.appendChild(link(nav.dataset.next, page + 1, false, page === pages - 1));
			if (scroll) table.scrollIntoView({ block: "start" });
			window.dispatchEvent(new Event("resize"));   // the pinned columns are measured again
		}
		table.paginate = show;
		show(0, false);
	});

	document.querySelectorAll("table").forEach(function (table) {
		if (!table.tHead || !table.tBodies[0] || table.tBodies[0].rows.length < 3) return;
		leafHeadings(table.tHead).forEach(function (pair) {
			var cell = pair[0], column = pair[1];
			if (cell.hasAttribute("data-nosort")) return;
			cell.classList.add("sortable");
			cell.tabIndex = 0;
			cell.title = (cell.title ? cell.title + ". " : "") + "Click to sort";
			cell.addEventListener("click", function () { sortBy(table, column, cell); });
			cell.addEventListener("keydown", function (e) {
				if (e.key === "Enter" || e.key === " ") { e.preventDefault(); sortBy(table, column, cell); }
			});
		});
	});
})();

// "On this page": the link of the section being read is marked (class current, aria-current), from the last
// heading above a line near the top of the window; at the end of the page, the last section.
(function () {
	var links = Array.prototype.slice.call(document.querySelectorAll('.toc nav a[href^="#"]'));
	var items = links.map(function (a) { return { a: a, h: document.getElementById(decodeURIComponent(a.hash.slice(1))) }; })
		.filter(function (i) { return i.h; });
	if (!items.length) return;
	function mark() {   // a dozen headings: cheap enough to run on every scroll event
		var line = 100, current = items[0];   // just below the top: the heading a link jumps to wins over the ones after it
		items.forEach(function (i) { if (i.h.getBoundingClientRect().top <= line) current = i; });
		if (window.innerHeight + window.scrollY >= document.documentElement.scrollHeight - 2) current = items[items.length - 1];
		items.forEach(function (i) {
			var on = i === current;
			i.a.classList.toggle("current", on);
			if (on) i.a.setAttribute("aria-current", "location"); else i.a.removeAttribute("aria-current");
		});
	}
	window.addEventListener("scroll", mark, { passive: true });
	window.addEventListener("resize", mark);
	mark();
})();

// Day / night: the button next to the language switch flips the colours and remembers the choice in this
// browser. Without a stored choice the page follows the system setting (prefers-color-scheme in style.css).
(function () {
	var button = document.querySelector("nav .theme");
	if (!button) return;
	var root = document.documentElement;
	var media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;
	function current() { return root.dataset.theme || (media && media.matches ? "dark" : "light"); }
	function show() { button.textContent = current() === "dark" ? "☀️" : "🌙"; }
	button.addEventListener("click", function () {
		var next = current() === "dark" ? "light" : "dark";
		root.dataset.theme = next;
		try { localStorage.setItem("theme", next); } catch (e) {}
		show();
	});
	if (media && media.addEventListener) media.addEventListener("change", show);
	show();
})();

// Collaboration graphs: hovering or focusing a circle highlights its links and the people or institutions it
// links to; everything else fades. The graph is complete without this.
(function () {
	var legend = document.querySelector(".legend-box");
	document.querySelectorAll("svg.net").forEach(function (svg) {
		function clear() {
			svg.classList.remove("focus");
			svg.querySelectorAll(".hl").forEach(function (el) { el.classList.remove("hl"); });
			if (legend) {
				legend.classList.remove("focus");
				legend.querySelectorAll(".hl").forEach(function (el) { el.classList.remove("hl"); });
			}
		}
		// the institutions (legend colours) of every circle that is lit: the person and the people one link away
		function lightLegend() {
			if (!legend) return;
			legend.classList.add("focus");
			svg.querySelectorAll(".node.hl").forEach(function (n) {
				legend.querySelectorAll("li[data-color]").forEach(function (li) {
					if (li.dataset.color === n.dataset.color) li.classList.add("hl");
				});
			});
		}
		function focus(id) {
			clear();
			svg.classList.add("focus");
			svg.querySelectorAll('.node[data-id="' + id + '"]').forEach(function (n) { n.classList.add("hl"); });
			svg.querySelectorAll(".edge, .ew").forEach(function (e) {
				var other = e.dataset.a === id ? e.dataset.b : e.dataset.b === id ? e.dataset.a : null;
				if (other === null) return;
				e.classList.add("hl");
				svg.querySelectorAll('.node[data-id="' + other + '"]').forEach(function (n) { n.classList.add("hl"); });
			});
			lightLegend();
		}
		svg.querySelectorAll(".node").forEach(function (n) {
			n.addEventListener("mouseenter", function () { focus(n.dataset.id); });
			n.addEventListener("focus", function () { focus(n.dataset.id); });
			n.addEventListener("mouseleave", clear);
			n.addEventListener("blur", clear);
		});
	});
})();

// Pinned tables: the first column is as wide as its longest name; the second sticks right after it.
(function () {
	function measure() {
		document.querySelectorAll(".scroll.pinned").forEach(function (box) {
			box.classList.add("measured");
			var first = box.querySelector("td.pin0, th.pin0");   // the # column, where there is one
			box.style.setProperty("--pin0w", (first ? first.getBoundingClientRect().width : 0) + "px");
			var cell = box.querySelector("td.pin1, th.pin1");
			if (cell) box.style.setProperty("--pin1w", cell.getBoundingClientRect().width + "px");
		});
	}
	measure();
	window.addEventListener("resize", measure);
	if (document.fonts && document.fonts.ready) document.fonts.ready.then(measure);
})();

// Feedback by e-mail: the same form, opened in the visitor's own mail app with the title as subject and the
// details as body. Nothing is sent until they press send there.
(function () {
	var button = document.querySelector("form.feedback .fb-mail");
	if (!button) return;
	button.addEventListener("click", function () {
		var form = button.form;
		if (!form.reportValidity()) return;
		location.href = "mailto:" + button.dataset.to + "?subject=" + encodeURIComponent(form.elements.title.value) +
			"&body=" + encodeURIComponent(form.elements.body.value + "\n\n" + location.href);
	});
})();

// Phones: the page menu is one strip that scrolls sideways; start it at the current page.
(function () {
	var strip = document.querySelector("nav .links"), current = strip && strip.querySelector("a.current");
	if (strip && current && strip.scrollWidth > strip.clientWidth) {
		strip.scrollLeft = Math.max(0, current.offsetLeft - strip.offsetLeft - 16);
	}
})();
