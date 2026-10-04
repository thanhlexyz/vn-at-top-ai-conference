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
// (a cell such as "11 +1" comes after 11 and before 12), text sorts A to Z, and empty cells ("–") always go last. Total rows stay
// at the bottom. Group headings that span several columns do not sort.
(function () {
	// "11 +1" is 11 official and 1 unofficial: it sorts after 11 and before 12, so the official number comes first
	// and the unofficial one breaks ties
	function number(text) {
		var t = text.replace(/,/g, "");
		var m = t.match(/-?\d+(\.\d+)?/);
		if (!m) return null;
		var extra = t.slice(m.index + m[0].length).match(/\+\s*(\d+)/);
		return parseFloat(m[0]) + (extra ? parseInt(extra[1], 10) / 1000 : 0);
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

	function sortBy(table, column, cell) {
		var body = table.tBodies[0];
		var rows = Array.prototype.filter.call(body.rows, function (tr) { return !tr.classList.contains("total"); });
		var totals = Array.prototype.filter.call(body.rows, function (tr) { return tr.classList.contains("total"); });
		var values = rows.map(function (tr) {
			var td = tr.cells[column], text = td ? td.textContent.trim() : "";
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
		podium(table, numeric ? column : null);
	}

	// Cups for the top three values of a .podium table, in the order shown: gold, silver, bronze. Sorted by a
	// number column, tied rows share a cup and the next value takes the next cup (one gold and two silvers are
	// followed by a bronze); zero never gets a cup, and sorted by text there are none.
	var CUP = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 3h10v2h3v3a4 4 0 0 1-4 4h-.3A5 5 0 0 1 13 14.9V18h3v2H8v-2h3v-3.1A5 5 0 0 1 8.3 12H8a4 4 0 0 1-4-4V5h3V3zm0 4H6v1a2 2 0 0 0 1 1.7V7zm10 0v2.7A2 2 0 0 0 18 8V7h-1z"/></svg>';
	var PLACES = ["gold", "silver", "bronze"];
	function podium(table, column) {
		if (!table.classList.contains("podium")) return;
		var rows = Array.prototype.filter.call(table.tBodies[0].rows, function (tr) { return !tr.classList.contains("total"); });
		var place = -1, last = null;
		rows.forEach(function (tr, k) {
			var slot = tr.querySelector(".cup");
			if (!slot) return;
			var key = column === undefined ? k : column === null ? null : number(tr.cells[column].textContent);
			if (key === null && column !== undefined) { place = 99; }
			else if (k === 0 || key !== last) { place += 1; }   // ties share a cup; the next value takes the next one
			last = key;
			slot.className = "cup";
			slot.innerHTML = "";
			slot.removeAttribute("title");
			if (place < 3 && !(column !== undefined && key === 0)) {   // a zero wins nothing
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

	document.querySelectorAll("table").forEach(function (table) {
		if (!table.tHead || !table.tBodies[0] || table.tBodies[0].rows.length < 3) return;
		leafHeadings(table.tHead).forEach(function (pair) {
			var cell = pair[0], column = pair[1];
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
	document.querySelectorAll("svg.net").forEach(function (svg) {
		function clear() {
			svg.classList.remove("focus");
			svg.querySelectorAll(".hl").forEach(function (el) { el.classList.remove("hl"); });
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
