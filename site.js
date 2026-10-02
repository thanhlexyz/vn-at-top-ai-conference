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
// (a cell such as "11 +1" counts as 11), text sorts A to Z, and empty cells ("–") always go last. Total rows stay
// at the bottom. Group headings that span several columns do not sort.
(function () {
	function number(text) {
		var m = text.replace(/,/g, "").match(/-?\d+(\.\d+)?/);
		return m ? parseFloat(m[0]) : null;
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
	}

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
